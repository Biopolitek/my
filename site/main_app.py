import sys, os, re, hashlib, io, json, zipfile, shutil, webbrowser, traceback
from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

# [DEPENDENCIES]
try:
    import zstandard as zstd, fitz
    from PIL import Image
    from psd_tools import PSDImage
except ImportError:
    sys.exit("FATAL: pip install PySide6 Pillow psd-tools pymupdf zstandard")

WRITE_LOCK = QMutex()

class DeepAssetOrchestrator:
    def __init__(self, root, project_name, upscale=2):
        self.root = root
        self.assets_base = os.path.join(self.root, "assets")
        self.upscale = upscale
        self.registry = {}  
        self.recognized_fonts = set()
        self.dirs = {"img": "images", "css": "css", "logs": "logs", "meta": "meta", "fonts": "fonts"}
        self._init_fs()

    def _init_fs(self):
        if os.path.exists(self.root): shutil.rmtree(self.root)
        for sub in self.dirs.values():
            os.makedirs(os.path.join(self.assets_base, sub), exist_ok=True)

    def process_resource(self, raw_data, name, is_img=False, metadata=None):
        """Zero-Loss: сохранение CSS/SVG + распознавание шрифтов"""
        try:
            ext = Path(name).suffix.lower()
            
            # Распознавание шрифтов в CSS
            if ext == ".css":
                css_text = raw_data.decode('utf-8', errors='ignore')
                found = re.findall(r'font-family:\s*["\']?(.*?)["\']?;', css_text)
                for f in found: self.recognized_fonts.add(f.split(',')[0].strip())

            # Обработка изображений ( Upscale только для растра )
            if is_img and ext in ['.png', '.jpg', '.jpeg', '.webp']:
                img = Image.open(io.BytesIO(raw_data)).convert("RGBA")
                new_size = (int(img.width * self.upscale), int(img.height * self.upscale))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                tmp = io.BytesIO()
                img.save(tmp, format="WEBP", lossless=True)
                raw_data = tmp.getvalue()
                ext = ".webp"

            h = hashlib.md5(raw_data if isinstance(raw_data, bytes) else raw_data.encode()).hexdigest()[:16]
            
            # Категоризация
            if ext == ".css": cat = "css"
            elif ext == ".svg": cat = "img" # SVG идет в images как вектор
            elif ext in ['.ttf', '.woff', '.woff2', '.otf']: cat = "fonts"
            elif is_img: cat = "img"
            else: cat = "meta"
            
            fn = f"res_{h}{ext}"
            rel_path = f"assets/{self.dirs[cat]}/{fn}"
            abs_path = os.path.join(self.assets_base, self.dirs[cat], fn)

            if h not in self.registry:
                with QMutexLocker(WRITE_LOCK):
                    mode = "wb" if isinstance(raw_data, bytes) else "w"
                    with open(abs_path, mode) as f: f.write(raw_data)
                self.registry[h] = rel_path
            
            return rel_path
        except:
            return ""

    def finalize(self):
        """Сохранение манифеста шрифтов и аудит"""
        font_manifest = os.path.join(self.assets_base, "meta", "fonts_recognized.json")
        with open(font_manifest, "w", encoding="utf-8") as f:
            json.dump({"detected_families": list(self.recognized_fonts)}, f, indent=4)

class SynthesisWorker(QThread):
    progress = Signal(int); finished = Signal()

    def __init__(self, tasks, project_name):
        super().__init__()
        self.tasks = tasks
        self.root = os.path.join(os.getcwd(), "exports", re.sub(r'\W+', '_', project_name))
        self.orc = DeepAssetOrchestrator(self.root, project_name)

    def run(self):
        try:
            html_pages = []
            for idx, (path, name, scale, is_idx) in enumerate(self.tasks):
                data = self.dispatch_logic(path, scale)
                filename = "index.html" if is_idx else f"page_{idx}.html"
                html_pages.append(filename)
                self.assemble_web(data, filename)
                self.progress.emit(int(((idx+1)/len(self.tasks))*100))
            self.orc.finalize()
            webbrowser.open(self.root)
        except: print(traceback.format_exc())
        finally: self.finished.emit()

    def dispatch_logic(self, path, scale):
        ext = Path(path).suffix.lower()
        objs = []; is_psd = False
        
        # FIG - обязательное сохранение CSS/SVG/PNG/JPG
        if ext == '.fig' and zipfile.is_zipfile(path):
            with zipfile.ZipFile(path, 'r') as z:
                for n in z.namelist():
                    fext = Path(n).suffix.lower()
                    if fext in ['.png', '.jpg', '.svg', '.css']:
                        raw = z.read(n)
                        self.orc.process_resource(raw, n, is_img=(fext in ['.png', '.jpg']))

        # PSD - извлечение слоев + CSS
        elif ext in ['.psd', '.psb']:
            is_psd = True; psd = PSDImage.open(path); css = []
            for i, layer in enumerate(psd.descendants()):
                if hasattr(layer, 'composite') and layer.width > 0:
                    buf = io.BytesIO(); layer.composite().save(buf, format="PNG")
                    src = self.orc.process_resource(buf.getvalue(), f"l_{i}.png", is_img=True)
                    if layer.is_visible():
                        cls = f"layer-{i}"
                        css.append(f".{cls} {{ position:absolute; left:{layer.left}px; top:{layer.top}px; width:{layer.width}px; z-index:{i}; }}")
                        objs.append({"src": src, "cls": cls})
            self.orc.process_resource("\n".join(css).encode(), "psd_layers.css")

        # PDF - рендер + вложения (CSS/SVG)
        elif ext == '.pdf':
            doc = fitz.open(path)
            for pg_idx, pg in enumerate(doc):
                pix = pg.get_pixmap(matrix=fitz.Matrix(scale*2, scale*2))
                src = self.orc.process_resource(pix.tobytes("png"), f"pg_{pg_idx}.png", is_img=True)
                objs.append({"src": src, "x": 0, "y": pg_idx*pix.height, "w": pix.width})
                # Вложения PDF (могут содержать CSS/SVG)
                for i in range(doc.embfile_count()):
                    name = doc.embfile_info(i)["name"]
                    self.orc.process_resource(doc.embfile_get(i), name, is_img=name.endswith(('.png','.jpg','.svg')))

        # Прямые файлы
        elif ext in ['.png', '.jpg', '.svg']:
            with open(path, 'rb') as f:
                src = self.orc.process_resource(f.read(), os.path.basename(path), is_img=(ext != '.svg'))
                objs.append({"src": src, "x": 0, "y": 0})

        return {"objs": objs, "is_psd": is_psd}

    def assemble_web(self, data, filename):
        nodes = ""
        for o in data['objs']:
            style = "" if "cls" in o else f"style='position:absolute; left:{o.get('x',0)}px; top:{o.get('y',0)}px; width:{o.get('w','auto')}px;'"
            nodes += f'\n<img src="{o["src"]}" class="{o.get("cls","")}" {style} alt="asset">'
        
        css_link = '<link rel="stylesheet" href="assets/css/psd_layers.css">' if data.get("is_psd") else ""
        html = f"<!DOCTYPE html><html><head><meta charset='utf-8'>{css_link}</head><body style='margin:0; background:#000;'>{nodes}</body></html>"
        with open(os.path.join(self.orc.root, filename), "w", encoding="utf-8") as f: f.write(html)

class ChimeraV15(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chimera OS v15.0 [Strict Sync]"); self.resize(900, 500)
        self.setStyleSheet("background:#0d1117; color:#c9d1d9; font-family: 'Segoe UI';")
        cen = QWidget(); self.setCentralWidget(cen); l = QVBoxLayout(cen)
        self.prj = QLineEdit("Final_Synthesis"); l.addWidget(self.prj)
        self.table = QTableWidget(0, 3); self.table.setHorizontalHeaderLabels(["PATH", "SCALE", "INDEX"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        l.addWidget(self.table)
        
        # СТРОГИЙ ФИЛЬТР
        btn_add = QPushButton("+ ДОБАВИТЬ (PNG, PSD, JPG, SVG, FIG, PDF)")
        btn_add.clicked.connect(self.add)
        btn_run = QPushButton("🚀 ЗАПУСК"); btn_run.clicked.connect(self.start)
        l.addWidget(btn_add); l.addWidget(btn_run); self.pb = QProgressBar(); l.addWidget(self.pb)

    def add(self):
        # Ограничение фильтра
        files, _ = QFileDialog.getOpenFileNames(self, "Select Sources", "", "Layouts (*.png *.psd *.jpg *.svg *.fig *.pdf)")
        for f in files:
            r = self.table.rowCount(); self.table.insertRow(r)
            it = QTableWidgetItem(f); it.setData(Qt.UserRole, f); self.table.setItem(r, 0, it)
            s = QDoubleSpinBox(); s.setValue(1.0); self.table.setCellWidget(r, 1, s)
            rb = QRadioButton(); self.table.setCellWidget(r, 2, rb)
            if r == 0: rb.setChecked(True)

    def start(self):
        tasks = []
        for r in range(self.table.rowCount()):
            tasks.append((self.table.item(r,0).data(Qt.UserRole), self.table.item(r,0).text(), self.table.cellWidget(r,1).value(), self.table.cellWidget(r,2).isChecked()))
        self.worker = SynthesisWorker(tasks, self.prj.text())
        self.worker.progress.connect(self.pb.setValue)
        self.worker.start()

if __name__ == "__main__":
    app = QApplication(sys.argv); win = ChimeraV15(); win.show(); sys.exit(app.exec())
