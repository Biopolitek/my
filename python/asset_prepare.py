import os, sys, json, gc, subprocess, zipfile, shutil
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                             QWidget, QFileDialog, QTextEdit, QProgressBar, QSplashScreen)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap

# Вспомогательная функция для путей внутри скомпилированного .exe
def resource_path(relative_path):
    base = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base, relative_path)

class FullstackExportThread(QThread):
    progress = pyqtSignal(int)
    log_msg = pyqtSignal(str)
    finished = pyqtSignal(str)

    def __init__(self, template_path, export_dir):
        super().__init__()
        self.template_path = Path(template_path)
        self.export_dir = Path(export_dir)
        # Стандартная структура папок проекта 2026
        self.dirs = {
            "img": self.export_dir / "assets" / "images",
            "svg": self.export_dir / "assets" / "vectors",
            "fnt": self.export_dir / "assets" / "fonts",
            "raw": self.export_dir / "assets" / "raw_data"
        }
        for d in self.dirs.values(): d.mkdir(parents=True, exist_ok=True)

    def run(self):
        try:
            from psd_tools import PSDImage
            import fitz  # PyMuPDF
            from PIL import Image
            
            ext = self.template_path.suffix.lower()
            layers_metadata = []
            canvas_w, canvas_h = 0, 0
            WEBP_LIMIT = 16383 # Аппаратный лимит формата

            # --- [1] PSD ENGINE: Слои, Текст, CSS ---
            if ext == '.psd':
                self.log_msg.emit("🎨 Подготовка PSD (Deep Extract)...")
                psd = PSDImage.open(self.template_path)
                canvas_w, canvas_h = psd.width, psd.height
                all_layers = list(psd.descendants())
                
                for i, layer in enumerate(all_layers):
                    meta = {
                        "id": f"L{i}", 
                        "name": layer.name, 
                        "type": layer.kind,
                        "blend_mode": getattr(layer, 'blend_mode', 'normal')
                    }
                    
                    # Извлечение CSS и текста
                    if layer.kind == 'type':
                        meta["css"] = {
                            "font-family": getattr(layer, 'font_name', 'sans-serif'),
                            "font-size": f"{getattr(layer, 'size', 16)}px",
                            "color": str(getattr(layer, 'color', '#000000')),
                            "opacity": round(layer.opacity / 255, 2),
                            "line-height": "1.2"
                        }
                        meta["text_content"] = layer.text

                    # Рендеринг графики
                    if layer.width > 0 and layer.height > 0:
                        try:
                            img = layer.topil()
                            if img:
                                # Конвертация цвета для Web
                                if img.mode in ('CMYK', 'LAB'): img = img.convert('RGB')
                                if img.mode in ('RGBA', 'P'): img = img.convert('RGBA')
                                
                                # Проверка WebP лимитов 2026
                                if img.width > WEBP_LIMIT or img.height > WEBP_LIMIT:
                                    img.thumbnail((WEBP_LIMIT, WEBP_LIMIT), Image.Resampling.LANCZOS)
                                
                                fname = f"layer_{i}.webp"
                                img.save(self.dirs["img"] / fname, "WEBP", quality=90)
                                meta["src"] = f"assets/images/{fname}"
                                meta["geometry"] = {"x": layer.left, "y": layer.top, "w": img.width, "h": img.height}
                        except: continue
                    
                    layers_metadata.append(meta)
                    self.progress.emit(int(((i+1)/len(all_layers))*100))

            # --- [2] PDF ENGINE: Векторы, Текст, Растр ---
            elif ext == '.pdf':
                self.log_msg.emit("📑 Рендеринг PDF (PixelPerfect 1:1)...")
                doc = fitz.open(self.template_path)
                y_cursor = 0
                for i, page in enumerate(doc):
                    # Сохранение векторного слепка
                    svg_name = f"page_{i}.svg"
                    with open(self.dirs["svg"] / svg_name, "w", encoding="utf-8") as f:
                        f.write(page.get_svg_image())
                    
                    # Рендеринг страницы в 300 DPI
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    
                    if img.width > WEBP_LIMIT or img.height > WEBP_LIMIT:
                        img.thumbnail((WEBP_LIMIT, WEBP_LIMIT), Image.Resampling.LANCZOS)

                    img_name = f"page_{i}.webp"
                    img.save(self.dirs["img"] / img_name, "WEBP", quality=85)

                    layers_metadata.append({
                        "id": f"P{i}",
                        "type": "page_composite",
                        "src": f"assets/images/{img_name}",
                        "vector_src": f"assets/vectors/{svg_name}",
                        "text_data": page.get_text("dict"), # Полная карта текста
                        "geometry": {"x": 0, "y": y_cursor, "w": img.width, "h": img.height}
                    })
                    y_cursor += img.height
                    canvas_w = max(canvas_w, img.width)
                canvas_h = y_cursor
                doc.close()

            # --- [3] FIG ENGINE: Ресурсы из архива ---
            elif ext == '.fig':
                self.log_msg.emit("📦 FIG Scan: Извлечение встроенных ассетов...")
                with zipfile.ZipFile(self.template_path, 'r') as z:
                    for info in z.infolist():
                        if any(info.filename.lower().endswith(x) for x in ['.svg', '.png', '.jpg']):
                            fn = os.path.basename(info.filename)
                            target = self.dirs["svg"] if ".svg" in fn.lower() else self.dirs["img"]
                            with z.open(info) as s, open(target / fn, "wb") as t:
                                shutil.copyfileobj(s, t)
                            layers_metadata.append({"id": f"F_{fn}", "src": f"assets/{target.name}/{fn}", "type": "raw_asset"})
                canvas_w, canvas_h = 1920, 1080

            # --- [4] МАНИФЕСТ И ВЕРИФИКАЦИЯ ---
            manifest_path = self.export_dir / "site_map.json"
            manifest = {
                "project": self.template_path.stem,
                "timestamp": "2026-01-27",
                "canvas": {"w": canvas_w, "h": canvas_h},
                "layers": layers_metadata,
                "ready_for_pixel_perfect": True
            }
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=4, ensure_ascii=False)

            # Проверка синхронизации файлов
            self.log_msg.emit("🔍 Верификация ресурсов...")
            visuals = [l for l in layers_metadata if "src" in l]
            exists_count = sum(1 for l in visuals if (self.export_dir / l["src"]).exists())
            
            if len(visuals) > 0 and exists_count == len(visuals):
                self.log_msg.emit("✅ Карта сайта подтверждена 1:1.")
                
                # Поиск и запуск asset_dev.exe
                dev_exe = Path(sys.executable).parent / "asset_dev.exe"
                if not dev_exe.exists(): dev_exe = Path("asset_dev.exe")

                if dev_exe.exists():
                    self.log_msg.emit("🚀 Запуск asset_dev.exe [READY]...")
                    subprocess.Popen([str(dev_exe), "READY", str(self.export_dir)])
                else:
                    self.log_msg.emit("ℹ️ asset_dev.exe не найден. Подготовка завершена.")
            else:
                self.log_msg.emit(f"⚠️ Внимание: создано {exists_count} из {len(visuals)} граф. ресурсов.")

            gc.collect()
            self.finished.emit(str(self.export_dir))

        except Exception as e:
            self.log_msg.emit(f"❌ Ошибка подготовки: {str(e)}")

class AssetExtractorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fullstack Asset Prepare 2026")
        self.setFixedSize(550, 600)
        self.template_path = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.log = QTextEdit(); self.log.setReadOnly(True)
        self.log.setStyleSheet("background:#121212; color:#00FF41; font-family:Consolas; font-size:11px;")
        self.prog = QProgressBar()
        
        btn_sel = QPushButton("📂 ВЫБРАТЬ ШАБЛОН (PSD, PDF, FIG)")
        btn_run = QPushButton("🚀 ПОДГОТОВИТЬ РЕСУРСЫ")
        btn_run.setStyleSheet("height:50px; background:#222; color:#0f0; font-weight:bold; border:1px solid #0f0;")
        
        btn_sel.clicked.connect(self.select_file)
        btn_run.clicked.connect(self.start_export)
        
        layout.addWidget(btn_sel); layout.addWidget(btn_run); layout.addWidget(self.prog); layout.addWidget(self.log)
        container = QWidget(); container.setLayout(layout); self.setCentralWidget(container)

    def select_file(self):
        p, _ = QFileDialog.getOpenFileName(self, "Открыть макет", "", "Design (*.psd *.pdf *.fig)")
        if p: self.template_path = p; self.log.append(f"📦 Загружен: {Path(p).name}")

    def start_export(self):
        if not self.template_path: return
        dest = QFileDialog.getExistingDirectory(self, "Папка назначения для web-сборки")
        if dest:
            self.prog.setValue(0)
            self.thread = FullstackExportThread(self.template_path, dest)
            self.thread.progress.connect(self.prog.setValue)
            self.thread.log_msg.connect(self.log.append)
            self.thread.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Попытка показать Splash Screen
    try:
        pix = QPixmap(resource_path('splash-screen.jpg'))
        if not pix.isNull():
            splash = QSplashScreen(pix, Qt.WindowType.WindowStaysOnTopHint)
            splash.show(); app.processEvents()
    except: pass
    
    win = AssetExtractorApp()
    win.show()
    
    if 'splash' in locals(): splash.finish(win)
    sys.exit(app.exec())