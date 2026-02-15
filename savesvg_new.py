import sys
import os
import base64
import xml.etree.ElementTree as ET
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                             QWidget, QFileDialog, QLabel, QMessageBox)

class SvgResourceExtractor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SVG Resource Extractor 2026")
        self.setFixedSize(450, 220)

        self.source_svg_path = None
        self.elements = []

        # Интерфейс
        layout = QVBoxLayout()
        
        self.status_label = QLabel("1. Выберите файл .svg")
        self.status_label.setStyleSheet("font-size: 13px; font-weight: bold; margin: 5px;")
        layout.addWidget(self.status_label)

        btn_open = QPushButton("Выбрать SVG")
        btn_open.setMinimumHeight(45)
        btn_open.clicked.connect(self.select_file)
        layout.addWidget(btn_open)

        self.btn_save = QPushButton("Сохранить ресурсы")
        self.btn_save.setMinimumHeight(45)
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.save_resources)
        layout.addWidget(self.btn_save)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Открыть SVG", "", "SVG Files (*.svg)")
        if path:
            self.source_svg_path = path
            self.parse_svg(path)

    def parse_svg(self, path):
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            
            # Собираем все графические элементы
            self.elements = []
            for elem in root.iter():
                tag = elem.tag.split('}')[-1]
                if tag in ['image', 'path', 'rect', 'circle', 'polygon']:
                    self.elements.append(elem)

            self.status_label.setText(f"Найдено ресурсов в файле: {len(self.elements)}")
            self.btn_save.setEnabled(len(self.elements) > 0)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка анализа файла: {e}")

    def save_resources(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку для сохранения")
        if not folder: return

        saved_count = 0
        for i, elem in enumerate(self.elements):
            tag = elem.tag.split('}')[-1]
            # Пытаемся взять оригинальное имя ресурса из атрибута id
            res_id = elem.get('id') or f"element_{i}"
            
            # Ищем данные изображения (href)
            href_data = None
            for attr, value in elem.attrib.items():
                if attr.endswith('href'): # Обработает и ns1:href, и xlink:href, и просто href
                    href_data = value
                    break

            # Если это картинка с данными base64
            if tag == 'image' and href_data and "base64," in href_data:
                try:
                    # Отсекаем заголовок, берем только контент после "base64,"
                    _, b64_content = href_data.split("base64,", 1)
                    
                    # Формируем имя файла строго .png на основе id ресурса
                    filename = f"{res_id}.png"
                    file_path = os.path.join(folder, filename)
                    
                    # Декодируем и записываем как реальную картинку
                    with open(file_path, "wb") as f:
                        f.write(base64.b64decode(b64_content))
                    
                    saved_count += 1
                    continue # Не сохраняем этот элемент как SVG, так как он уже сохранен как PNG
                except Exception as e:
                    print(f"Ошибка при извлечении PNG для {res_id}: {e}")

            # Для всех остальных элементов (path и т.д.) сохраняем как отдельный .svg
            try:
                new_root = ET.Element('svg', {'xmlns': 'http://www.w3.org'})
                new_root.append(elem)
                
                filename = f"{res_id}.svg"
                file_path = os.path.join(folder, filename)
                
                with open(file_path, "wb") as f:
                    ET.ElementTree(new_root).write(f, encoding='utf-8', xml_declaration=True)
                saved_count += 1
            except Exception as e:
                print(f"Ошибка при сохранении SVG для {res_id}: {e}")

        QMessageBox.information(self, "Готово", f"Обработано и сохранено ресурсов: {saved_count}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = SvgResourceExtractor()
    window.show()
    sys.exit(app.exec())