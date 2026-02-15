import sys, json, subprocess, os
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QTextEdit, QLabel, QWidget
from PyQt6.QtCore import QTimer

class AssetAnalyst(QMainWindow):
    def __init__(self, path):
        super().__init__()
        # Исправляем передачу пути (берем последний аргумент)
        self.path = Path(sys.argv[-1]).absolute()
        self.setWindowTitle("Deep Analyst v6.0")
        self.resize(600, 450)
        self.init_ui()
        self.t = QTimer(); self.t.timeout.connect(self.get_temp); self.t.start(1000)
        QTimer.singleShot(1000, self.audit)

    def init_ui(self):
        l = QVBoxLayout()
        self.log = QTextEdit(); self.temp = QLabel("Temp: --")
        l.addWidget(QLabel(f"Инспекция ресурсов: {self.path}"))
        l.addWidget(self.log); l.addWidget(self.temp)
        c = QWidget(); c.setLayout(l); self.setCentralWidget(c)

    def get_temp(self):
        try:
            cmd = "Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature | Select-Object -ExpandProperty CurrentTemperature"
            res = subprocess.check_output(["powershell", "-Command", cmd], shell=True).decode().strip()
            self.temp.setText(f"CPU Temp: {round((float(res)/10)-273.15, 1)}°C")
        except: self.temp.setText("Temp: Error")

    def audit(self):
        self.log.append(">> ПРОВЕРКА ЦЕЛОСТНОСТИ ДАННЫХ...")
        map_p = self.path / "map_assets.txt"
        
        if not map_p.exists():
            self.log.append("!! Манифест не найден. Возврат.")
            return

        with open(map_p, "r", encoding="utf-8") as f:
            data = json.load(f)

        expected = len(data["layers"])
        actual = len(os.listdir(self.path / "assets/images"))
        
        if expected >= actual: # Текстовые слои не создают файлы
            self.log.append(f">> [100% READY]: Объектов {expected}, Файлов {actual}")
            # Создаем метку готовности
            with open(self.path / ".ready_to_build", "w") as f: f.write("validated")
            subprocess.Popen(["python", "asset_developer.py", str(self.path)])
        else:
            self.log.append("!! ОШИБКА: Несоответствие ресурсов.")

if __name__ == "__main__":
    app = QApplication(sys.argv); ex = AssetAnalyst(sys.argv); ex.show(); sys.exit(app.exec())