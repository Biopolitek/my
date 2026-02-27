import sys
import os
import xml.etree.ElementTree as ET
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                             QWidget, QFileDialog, QLabel, QMessageBox)

class SvgSmartExtractor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SVG Counter & Extractor 2026")
        self.setFixedSize(450, 200)

        self.source_svg_path = None
        self.elements = []

        layout = QVBoxLayout()
        
        self.status_label = QLabel("1. Выберите файл для анализа")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.status_label)

        self.btn_open = QPushButton("Выбрать SVG")
        self.btn_open.setHeight = 40
        self.btn_open.clicked.connect(self.select_file)
        layout.addWidget(self.btn_open)

        self.btn_save = QPushButton("Сохранить элементы")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.save_elements)
        layout.addWidget(self.btn_save)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Открыть SVG", "", "SVG Files (*.svg)")
        if file_path:
            self.source_svg_path = file_path
            self.parse_svg(file_path)

    def parse_svg(self, path):
        try:
            # Читаем файл целиком
            tree = ET.parse(path)
            root = tree.getroot()

            # Список графических тегов для поиска
            # Мы используем поиск без учета Namespace (локальное имя)
            target_tags = {'path', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'image', 'text'}
            
            self.elements = []
            
            # Рекурсивный обход всех элементов
            for elem in root.iter():
                # Извлекаем чистое имя тега (без {url}...)
                tag_local_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                
                if tag_local_name in target_tags:
                    self.elements.append(elem)

            count = len(self.elements)
            self.status_label.setText(f"Найдено графических элементов: {count}")
            
            if count > 0:
                self.btn_save.setEnabled(True)
            else:
                QMessageBox.warning(self, "Внимание", "В файле не найдено известных графических тегов.")
                self.btn_save.setEnabled(False)
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при разборе XML: {e}")

    def save_elements(self):
        if not self.elements:
            return

        output_dir = QFileDialog.getExistingDirectory(self, "Выберите папку")
        if not output_dir:
            return

        try:
            # Берем viewBox из оригинала, чтобы элементы не "улетели" за границы
            root_attr = ET.parse(self.source_svg_path).getroot().attrib
            viewbox = root_attr.get('viewBox', '0 0 500 500')
            width = root_attr.get('width', '500')
            height = root_attr.get('height', '500')

            for i, elem in enumerate(self.elements):
                # Создаем чистую SVG оболочку
                new_root = ET.Element('svg', {
                    'xmlns': 'http://www.w3.org',
                    'viewBox': viewbox,
                    'width': width,
                    'height': height
                })
                new_root.append(elem)
                
                new_tree = ET.ElementTree(new_root)
                tag_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                filename = f"{i+1}_{tag_name}.svg"
                
                new_tree.write(os.path.join(output_dir, filename), encoding='utf-8', xml_declaration=True)

            QMessageBox.information(self, "Готово", f"Успешно сохранено {len(self.elements)} файлов.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить файлы: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SvgSmartExtractor()
    window.show()
    sys.exit(app.exec())