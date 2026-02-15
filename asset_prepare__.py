import os
import sys
import zipfile
import gc
import shutil
import re
import io
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout,
                             QWidget, QFileDialog, QLabel, QTextEdit, QMessageBox)
from PyQt6.QtCore import QThread, pyqtSignal, QWaitCondition, QMutex, Qt
from PIL import Image
import fitz  # PyMuPDF
from psd_tools import PSDImage
import matplotlib.font_manager as fm

# --- СИСТЕМА УПРАВЛЕНИЯ ПОТОКОМ ---
class WorkerControl:
    def __init__(self):
        self.mutex = QMutex()
        self.condition = QWaitCondition()
        self.is_paused = False

    def check_pause(self):
        self.mutex.lock()
        if self.is_paused:
            self.condition.wait(self.mutex)
        self.mutex.unlock()

    def pause(self):
        self.mutex.lock()
        self.is_paused = True
        self.mutex.unlock()

    def resume(self):
        self.mutex.lock()
        self.is_paused = False
        self.condition.wakeAll()
        self.mutex.unlock()

# --- ЯДРО ЭКСПОРТА (v3.6.2 Master Bridge) ---
class ExportWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)

    def __init__(self, template_path, export_dir, control):
        super().__init__()
        self.template_path = template_path
        self.export_dir = export_dir
        self.control = control
        self.data = {"pages": {}, "fonts": set(), "interactivity": []}

    def run(self):
        ext = Path(self.template_path).suffix.lower()
        try:
            if ext == '.psd': self.process_psd()
            elif ext == '.pdf': self.process_pdf()
            elif ext == '.fig': self.process_fig()
            self.progress.emit("--- ЭКСПОРТ РЕСУРСОВ ЗАВЕРШЕН ---")
        except Exception as e:
            self.progress.emit(f"КРИТИЧЕСКАЯ ОШИБКА: {str(e)}")
        finally:
            self.finished.emit(self.data)

    def sanitize(self, text):
        return re.sub(r'[^a-zA-Z0-9_-]', '_', str(text))

    def save_smart_asset(self, raw_data, folder, base_name):
        try:
            img = Image.open(io.BytesIO(raw_data))
            # Фикс для 2026: принудительное приведение формата к строке
            fmt = str(img.format).lower()
            ext = 'jpg' if 'jpeg' in fmt else fmt
            # Очистка расширения от лишних символов, если пришел кортеж
            ext = re.sub(r'[^a-z0-9]', '', ext)
            
            file_name = f"{base_name}.{ext}"
            path = os.path.join(self.export_dir, folder, file_name)
            with open(path, "wb") as f: f.write(raw_data)
            return file_name
        except: return None

    def process_psd(self):
        self.progress.emit("Анализ PSD слоев и стилей...")
        psd = PSDImage.open(self.template_path)
        page_key = "psd_layout"
        self.data["pages"][page_key] = {"css": [], "html": []}
        z_idx = 100

        for layer in psd.descendants():
            self.control.check_pause()
            if layer.is_group(): continue
            z_idx += 1
            c_name = self.sanitize(layer.name)
            
            self.data["pages"][page_key]["css"].append(
                f".{c_name} {{ position: absolute; left: {layer.left}px; top: {layer.top}px; "
                f"width: {layer.width}px; height: {layer.height}px; z-index: {z_idx}; opacity: {layer.opacity/255:.2f}; }}"
            )

            if layer.kind == 'type':
                self.data["pages"][page_key]["html"].append(f"<div class='{c_name}'>{layer.text}</div>")
                if hasattr(layer, 'resource_dict'):
                    fonts = layer.resource_dict.get('FontSet', [])
                    for f in fonts: self.data["fonts"].add(str(f.get('Name', 'Unknown')))
            
            elif layer.width > 0:
                out_io = io.BytesIO()
                layer.topil().save(out_io, format="PNG")
                self.save_smart_asset(out_io.getvalue(), 'assets/images', c_name)
            
            if z_idx % 25 == 0: gc.collect()

    def process_pdf(self):
        self.progress.emit("Глубокий разбор PDF и экспорт SVG...")
        doc = fitz.open(self.template_path)
        for i, page in enumerate(doc):
            self.control.check_pause()
            page_key = f"page_{i}"
            self.data["pages"][page_key] = {"css": [], "html": []}
            
            # Рендер эталона
            pix = page.get_pixmap(dpi=150)
            pix.save(os.path.join(self.export_dir, 'data/reference', f"ref_p{i}.png"))
            
            # SVG Векторы
            svg_data = page.get_svg_image() if hasattr(page, 'get_svg_image') else page.get_svgimage()
            with open(os.path.join(self.export_dir, 'assets/vectors', f"p{i}.svg"), "w", encoding="utf-8") as f:
                f.write(svg_data)
            
            # Извлечение изображений
            img_list = page.get_images(full=True)
            for img_idx, img_info in enumerate(img_list):
                try:
                    xref = img_info[0] # Исправлено получение xref
                    base = doc.extract_image(xref)
                    self.save_smart_asset(base["image"], 'assets/images', f"p{i}_i{img_idx}")
                except: continue
            gc.collect()

    def process_fig(self):
        self.progress.emit("Извлечение ресурсов из .fig...")
        master_svg = ["<?xml version='1.0' encoding='utf-8'?><svg xmlns='http://www.w3.org' viewBox='0 0 1920 1080'>"]
        with zipfile.ZipFile(self.template_path, 'r') as z:
            for info in z.infolist():
                self.control.check_pause()
                if info.filename.startswith('images/') and not info.is_dir():
                    self.save_smart_asset(z.read(info.filename), 'assets/images', Path(info.filename).stem)
                if any(x in info.filename for x in ['data', 'canvas']):
                    try:
                        content = z.read(info.filename).decode('utf-8', errors='ignore')
                        paths = re.findall(r'([Mm][^"\'<>]+[Zz])', content)
                        for idx, p_data in enumerate(paths):
                            master_svg.append(f'<path id="vec_{idx}" d="{p_data}" fill="currentColor" opacity="0.5"/>')
                    except: continue
        master_svg.append("</svg>")
        with open(os.path.join(self.export_dir, 'assets/vectors', "fig_master.svg"), "w", encoding="utf-8") as f:
            f.write("\n".join(master_svg))

# --- ОСНОВНОЕ ОКНО ---
class MasterBridgeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pixel-Perfect Master Bridge v3.6.2")
        self.setMinimumSize(1000, 700)
        self.template_path = None
        self.export_dir = None
        self.control = WorkerControl()
        self.init_ui()

    def init_ui(self):
        w = QWidget(); l = QVBoxLayout()
        self.log_box = QTextEdit(); self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("background:#121212; color:#00FF41; font-family:Consolas;")
        
        btns = QHBoxLayout()
        self.btn_run = QPushButton("🚀 СТАРТ ЭКСПОРТ")
        self.btn_pause = QPushButton("⏸ ПАУЗА")
        btns.addWidget(self.btn_run); btns.addWidget(self.btn_pause)
        
        btn_sel = QPushButton("📁 ВЫБРАТЬ ШАБЛОН (.FIG, .PSD, .PDF)")
        btn_sel.setFixedHeight(40)
        btn_sel.clicked.connect(self.select)
        
        l.addWidget(QLabel(" MASTER BRIDGE v3.6.2 | PIXEL-PERFECT 2026"))
        l.addWidget(btn_sel); l.addLayout(btns); l.addWidget(self.log_box)
        w.setLayout(l); self.setCentralWidget(w)
        
        self.btn_run.clicked.connect(self.run_task)
        self.btn_pause.clicked.connect(self.toggle_pause)

    def log(self, t):
        self.log_box.append(f">> {str(t)}")

    def select(self):
        p, _ = QFileDialog.getOpenFileName(self, "Open", "", "Design (*.psd *.fig *.pdf)")
        if p: self.template_path = p; self.log(f"Файл выбран: {p}")

    def run_task(self):
        if not self.template_path: return
        self.export_dir = QFileDialog.getExistingDirectory(self, "Куда экспортировать?")
        if not self.export_dir: return
        
        for d in ['assets/images', 'assets/vectors', 'assets/fonts', 'data/reference']:
            os.makedirs(os.path.join(self.export_dir, d), exist_ok=True)

        self.worker = ExportWorker(self.template_path, self.export_dir, self.control)
        self.worker.progress.connect(self.log)
        self.worker.finished.connect(self.finalize)
        self.worker.start()

    def toggle_pause(self):
        if self.control.is_paused:
            self.control.resume(); self.btn_pause.setText("⏸ ПАУЗА")
        else:
            self.control.pause(); self.btn_pause.setText("▶ ВОЗОБНОВИТЬ")

    def finalize(self, data):
        self.log("Генерация карт активов...")
        try:
            map_path = os.path.join(self.export_dir, "map_assets.txt")
            with open(map_path, "w", encoding="utf-8") as f_map:
                f_map.write("=== PIXEL-PERFECT MASTER MAP v3.6.2 ===\n")
                for p_idx, p_data in data["pages"].items():
                    # CSS
                    with open(os.path.join(self.export_dir, f'data/styles_{p_idx}.css'), "w", encoding="utf-8") as fc:
                        fc.write("\n".join(p_data["css"]))
                    # HTML
                    with open(os.path.join(self.export_dir, f'data/index_{p_idx}.html'), "w", encoding="utf-8") as fh:
                        fh.write(f"<html><head><meta charset='utf-8'><link rel='stylesheet' href='styles_{p_idx}.css'></head><body>\n")
                        fh.write("\n".join(p_data["html"]) + "\n</body></html>")

            # Вызов внешнего анализатора
            app_path = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
            analyst_exe = os.path.join(app_path, "Asset-Analise.exe")

            if os.path.exists(analyst_exe):
                subprocess.Popen([analyst_exe, self.export_dir, self.template_path])
                self.log(f"Анализатор запущен.")
            else:
                self.log("ОШИБКА: Asset-Analise.exe не найден.")

            QMessageBox.information(self, "Завершено", "Экспорт ресурсов выполнен успешно.")
        except Exception as e:
            self.log(f"Ошибка финализации: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv); app.setStyle("Fusion")
    ex = MasterBridgeApp(); ex.show(); sys.exit(app.exec())