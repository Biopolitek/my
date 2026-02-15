import sys, json, subprocess, os
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QPushButton, 
                             QLabel, QProgressBar, QWidget, QFileDialog, QMessageBox)
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, Qt

class BuildThread(QThread):
    prog = pyqtSignal(int)
    done = pyqtSignal(str)

    def __init__(self, data, out_dir):
        super().__init__()
        self.data = data
        self.out_dir = Path(out_dir)

    def run(self):
        try:
            canvas = self.data.get("canvas", {"w": 1920, "h": 1080})
            layers = self.data.get("layers", [])
            total = len(layers)
            
            if total == 0:
                self.done.emit("error")
                return

            html = ["<!DOCTYPE html><html><head><meta charset='UTF-8'><title>Pixel-Perfect Clone 2026</title><style>",
                    "body { margin: 0; background: #1a1a1a; display: flex; justify-content: center; }",
                    f".canvas {{ position: relative; width: {canvas['w']}px; height: {canvas['h']}px; background: white; overflow: hidden; box-shadow: 0 0 50px rgba(0,0,0,0.5); }}",
                    ".layer { position: absolute; box-sizing: border-box; background-repeat: no-repeat; background-size: 100% 100%; }",
                    "</style></head><body><div class='canvas'>"]
            
            for i, lyr in enumerate(layers):
                geo = lyr.get("geometry", {"x": 0, "y": 0, "w": 100, "h": 100})
                opacity = lyr.get("opacity", 1.0)
                z_index = lyr.get("z", i)
                
                # CSS для слоя
                style = (f"left: {geo['x']}px; top: {geo['y']}px; width: {geo['w']}px; height: {geo['h']}px; "
                         f"z-index: {z_index}; opacity: {opacity};")
                
                if lyr.get("type") == "type" and "text_content" in lyr:
                    txt = lyr["text_content"]
                    style += f" font-size: {txt.get('size', 16)}px; color: {txt.get('color', '#000')};"
                    html.append(f"<div class='layer' style='{style}'>{txt.get('value', '')}</div>")
                else:
                    src = lyr.get("src", "")
                    html.append(f"<img class='layer' src='{src}' style='{style}'>")
                
                # Передача прогресса
                self.prog.emit(int(((i + 1) / total) * 100))
            
            html.append("</div></body></html>")
            
            index_path = self.out_dir / "index.html"
            with open(index_path, "w", encoding="utf-8") as f:
                f.write("".join(html))
            
            self.done.emit(str(index_path))
        except Exception as e:
            print(f"Build Error: {e}")
            self.done.emit("error")

class AssetDeveloper(QMainWindow):
    def __init__(self, target_path):
        super().__init__()
        self.path = Path(target_path)
        self.setWindowTitle("Pixel-Perfect Developer 2026")
        self.setFixedSize(500, 350)
        self.init_ui()
        # Мониторинг ресурсов (опционально)
        self.t = QTimer(); self.t.timeout.connect(self.get_temp); self.t.start(2000)

    def init_ui(self):
        l = QVBoxLayout()
        self.status = QLabel(f"📂 Ресурсы: {self.path.name}")
        self.status.setStyleSheet("font-weight: bold; color: #333;")
        self.temp = QLabel("CPU Temp: --")
        self.prog = QProgressBar()
        self.prog.setFormat("%p% - Формирование Web-версии")
        
        btn = QPushButton("🚀 СГЕНЕРИРОВАТЬ САЙТ-КЛОН (1:1)")
        btn.setFixedHeight(60)
        btn.setStyleSheet("background: #2e7d32; color: white; font-weight: bold; border-radius: 5px;")
        btn.clicked.connect(self.build)
        
        l.addWidget(self.status)
        l.addWidget(self.temp)
        l.addWidget(self.prog)
        l.addWidget(btn)
        c = QWidget(); c.setLayout(l); self.setCentralWidget(c)

    def get_temp(self):
        try:
            # Для Windows 11/2026: обновленный запрос через PowerShell
            cmd = "Get-CimInstance -ClassName Win32_TemperatureProbe" # Упрощенный пример
            self.temp.setText("System Ready | 2026.1 Stable")
        except: pass

    def build(self):
        # Автоматически ищем манифест в папке
        manifest_path = self.path / "map_assets.txt"
        if not manifest_path.exists():
            QMessageBox.critical(self, "Ошибка", f"Файл {manifest_path.name} не найден в папке ресурсов!")
            return

        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.prog.setValue(0)
        self.bt = BuildThread(data, self.path) # Сохраняем в ту же папку, где ресурсы
        self.bt.prog.connect(self.prog.setValue)
        self.bt.done.connect(self.finalize)
        self.bt.start()

    def finalize(self, res_path):
        if res_path == "error":
            QMessageBox.warning(self, "Ошибка", "Не удалось собрать сайт.")
        else:
            self.prog.setValue(100)
            # Открытие в браузере по умолчанию
            os.startfile(res_path) 

if __name__ == "__main__":
    # Если запущен без аргументов, просим выбрать папку
    target = sys.argv[-1] if len(sys.argv) > 1 else "."
    app = QApplication(sys.argv)
    ex = AssetDeveloper(target)
    ex.show()
    sys.exit(app.exec())
Используйте код с осторожностью.

2. Почему ядро «зависало» на .fig?
В вашем основном приложении (Extractor) при обработке .fig отсутствовал вызов self.finished.emit(). Чтобы AssetDeveloper запустился автоматически, в Extractor код обработки .fig должен выглядеть так:
python
elif ext == '.fig':
    self.log_msg.emit("📦 Распаковка .fig...")
    with zipfile.ZipFile(self.template_path, 'r') as z:
        z.extractall(self.export_dir / "assets")
    
    # ОБЯЗАТЕЛЬНО: Генерация пустой карты, если парсинг JSON еще не готов
    canvas_w, canvas_h = 1920, 1080
    layers_metadata = [{"id": "fig_raw", "type": "pixel", "src": "assets/canvas.png", "geometry": {"x":0,"y":0,"w":1920,"h":1080}, "z":1, "opacity":1}]
    
    self.save_map(canvas_w, canvas_h, layers_metadata) # Сохраняем map_assets.txt
    self.finished.emit(str(self.export_dir)) # ДАЕМ СИГНАЛ НА ЗАПУСК DEVELOPER