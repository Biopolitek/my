import os
import sys
import json
import zipfile
import gc
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                             QWidget, QFileDialog, QLabel, QTextEdit, QMessageBox)
from PIL import Image
import fitz  # PyMuPDF
from psd_tools import PSDImage
import matplotlib.font_manager as fm

class PixelPerfectExtractor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PixelPerfect Extractor 2026 (Enterprise Edition)")
        self.setMinimumSize(800, 600)
        
        self.template_path = None
        self.export_dir = None
        self.missing_fonts = set()
        self.layer_data = []

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        layout = QVBoxLayout()
        self.status_label = QLabel("Готов к работе с большими данными")
        layout.addWidget(self.status_label)

        for text, func in [("📁 ВЫБРАТЬ ШАБЛОН", self.select_template), 
                           ("🚀 ЭКСПОРТ РЕСУРСОВ", self.run_export),
                           ("🗺️ КАРТА АКТИВОВ", self.create_asset_map)]:
            btn = QPushButton(text)
            btn.setFixedHeight(50)
            btn.clicked.connect(func)
            layout.addWidget(btn)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("background-color: #1a1a1a; color: #00ff41; font-family: 'Courier New';")
        layout.addWidget(self.log_output)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def log(self, message):
        self.log_output.append(f">> {message}")
        QApplication.processEvents()

    def select_template(self):
        path, _ = QFileDialog.getOpenFileName(self, "Открыть макет", "", "Design (*.fig *.psd *.pdf)")
        if path:
            self.template_path = path
            self.status_label.setText(f"Файл: {os.path.basename(path)}")
            self.log(f"Файл готов к анализу: {path}")

    def run_export(self):
        if not self.template_path: return
        self.export_dir = QFileDialog.getExistingDirectory(self, "Папка сохранения")
        if not self.export_dir: return

        for p in ['assets/images', 'assets/vectors', 'assets/fonts', 'data/reference']:
            os.makedirs(os.path.join(self.export_dir, p), exist_ok=True)

        ext = Path(self.template_path).suffix.lower()
        try:
            if ext == '.psd': self.process_psd()
            elif ext == '.pdf': self.process_pdf()
            elif ext == '.fig': self.process_fig_local()
            self.log("--- ВСЕ РЕСУРСЫ ОБРАБОТАНЫ ---")
        except Exception as e:
            self.log(f"ОШИБКА ПАМЯТИ ИЛИ ДОСТУПА: {str(e)}")
        finally:
            gc.collect()

    def process_psd(self):
        self.log("Запуск итеративного парсинга PSD...")
        # Используем lazy load для экономии RAM
        psd = PSDImage.open(self.template_path)
        for layer in psd.descendants():
            if layer.kind in ['pixel', 'smartobject'] and layer.width > 0:
                if layer.width * layer.height > 50000000: # Лимит 50MP
                    self.log(f"Пропуск слишком большого слоя: {layer.name}")
                    continue
                # Извлекаем изображение только в момент сохранения
                img = layer.topil()
                img.save(os.path.join(self.export_dir, 'assets/images', f"{layer.name}.webp"), "WEBP", quality=95)
                del img
            if layer.kind == 'type':
                self.missing_fonts.add(getattr(layer, 'name', 'Generic Font'))
        gc.collect()

    def process_pdf(self):
        self.log("Анализ PDF в режиме экономии памяти...")
        doc = fitz.open(self.template_path)
        
        for i, page in enumerate(doc):
            # Рендерим эталон с разумным DPI (150-200 достаточно для QA больших страниц)
            # Если 300 вылетает, снижаем до 150 автоматически
            try:
                pix = page.get_pixmap(dpi=200)
                pix.save(os.path.join(self.export_dir, 'data/reference', f"page_{i}.png"))
                del pix
            except Exception:
                self.log(f"Стр {i}: Снижение DPI для рендеринга...")
                pix = page.get_pixmap(dpi=96)
                pix.save(os.path.join(self.export_dir, 'data/reference', f"page_{i}.png"))
                del pix

            # Потоковое извлечение картинок
            img_list = page.get_images(full=True)
            for img_index, img_obj in enumerate(img_list):
                try:
                    xref = img_obj[0]
                    base_img = doc.extract_image(xref)
                    output_path = os.path.join(self.export_dir, 'assets/images', f"p{i}_img{img_index}.{base_img['ext']}")
                    with open(output_path, "wb") as f:
                        f.write(base_img["image"])
                    self.log(f"Извлечено: p{i}_img{img_index}")
                    del base_img
                except Exception as img_err:
                    self.log(f"Ошибка объекта на стр {i}: {img_err}")
            gc.collect()

    def process_fig_local(self):
        self.log("Вскрытие .fig контейнера...")
        with zipfile.ZipFile(self.template_path, 'r') as z:
            for info in z.infolist():
                if info.filename.startswith('images/') and not info.is_dir():
                    with z.open(info.filename) as source, open(os.path.join(self.export_dir, 'assets/images', os.path.basename(info.filename)), "wb") as target:
                        shutil.copyfileobj(source, target)
        self.log("Графика FIG извлечена.")

    def create_asset_map(self):
        if not self.export_dir: return
        map_file = os.path.join(self.export_dir, "map_assets.txt")
        available_fonts = [f.name for f in fm.fontManager.ttflist]
        with open(map_file, "w", encoding="utf-8") as f:
            f.write("=== PIXEL-PERFECT ASSET MAP 2026 ===\n")
            f.write(f"Source: {self.template_path}\n\n[FONTS]\n")
            for font in self.missing_fonts:
                f.write(f"{font} : {'OK' if font in available_fonts else 'MISSING'}\n")
            f.write("\n[IMAGES]\n")
            img_dir = os.path.join(self.export_dir, 'assets/images')
            if os.path.exists(img_dir):
                for img in os.listdir(img_dir): f.write(f"file: {img}\n")
        self.log(f"Карта создана: {map_file}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = PixelPerfectExtractor()
    ex.show()
    sys.exit(app.exec())