import os
import re
import threading
import time
import webbrowser
import sys
import subprocess
from pathlib import Path
from PIL import Image
import customtkinter as ctk

# Настройки интерфейса 2026
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class SplashScreen(ctk.CTk):
    def __init__(self, main_app_class):
        super().__init__()
        self.main_app_class = main_app_class
        self.overrideredirect(True)
        
        image_path = resource_path("splash-screen.jpg")
        w, h = 500, 350
        self.geometry(f"{w}x{h}")
        
        try:
            raw_img = Image.open(image_path)
            splash_image = ctk.CTkImage(light_image=raw_img, dark_image=raw_img, size=(500, 300))
            self.image_label = ctk.CTkLabel(self, image=splash_image, text="")
            self.image_label.pack(fill="both", expand=True)
        except:
            self.image_label = ctk.CTkLabel(self, text="ЗАГРУЗКА...", font=("Arial", 24, "bold"))
            self.image_label.pack(expand=True)
            
        self.label_status = ctk.CTkLabel(self, text="Инициализация систем мониторинга 2026...", font=("Arial", 12))
        self.label_status.pack(pady=5)
        
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"+{int(x)}+{int(y)}")
        self.after(2500, self.start_main_app)

    def start_main_app(self):
        main_app = self.main_app_class()
        self.destroy()
        main_app.mainloop()

class AssetMapperApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Asset Mapper & CPU Monitor 2026")
        self.geometry("850x750")
        
        base_folder = os.path.dirname(sys.executable if hasattr(sys, '_MEIPASS') else __file__)
        self.source_dir = os.path.join(base_folder, "exports")
        
        if not os.path.exists(self.source_dir):
            os.makedirs(self.source_dir)
            
        self.output_file = "layout_map.html"
        self.setup_ui()
        self.stop_monitor = False
        threading.Thread(target=self.update_temp_loop, daemon=True).start()

    def setup_ui(self):
        # Панель мониторинга
        self.monitor_frame = ctk.CTkFrame(self)
        self.monitor_frame.pack(fill="x", padx=20, pady=10)
        
        self.temp_label = ctk.CTkLabel(
            self.monitor_frame, 
            text="градус --,-", 
            font=("Consolas", 26, "bold"), 
            text_color="#ff5555"
        )
        self.temp_label.pack(side="right", padx=25, pady=15)
        
        ctk.CTkLabel(self, text="Анализатор ассетов 2026", font=("Arial", 20, "bold")).pack(pady=10)
        
        # Кнопки управления
        self.btn_run = ctk.CTkButton(self, text="Анализировать папку exports", command=self.process_files, height=45, fg_color="#3700b3")
        self.btn_run.pack(pady=10)

        # Фрейм для выпадающего списка (Combobox)
        self.filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.filter_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(self.filter_frame, text="Найденные проекты:").pack(side="left", padx=10)
        
        self.project_combo = ctk.CTkComboBox(self.filter_frame, values=["Нет данных"], width=300)
        self.project_combo.pack(side="left", padx=10)
        
        self.btn_open = ctk.CTkButton(self, text="Открыть HTML отчет", command=self.open_report, state="disabled", fg_color="green")
        self.btn_open.pack(pady=15)
        
        self.textbox = ctk.CTkTextbox(self, width=800, height=300, font=("Consolas", 12))
        self.textbox.pack(pady=10, padx=20)

    def update_temp_loop(self):
        ps_cmd = (
            "$t = (Get-CimInstance -Namespace root/wmi -ClassName MsAcpi_ThermalZoneTemperature).CurrentTemperature; "
            "if($t) { $c = ($t/10 - 273.15); '+' + ('{0:N1}' -f $c) } else { 'N/A' }"
        )
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0 
        
        while not self.stop_monitor:
            try:
                output = subprocess.check_output(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stderr=subprocess.DEVNULL
                ).decode('cp866').strip()
                
                if output and output != "N/A":
                    self.temp_label.configure(text=f"градус {output}")
                else:
                    self.temp_label.configure(text="градус N/A", text_color="orange")
            except:
                self.temp_label.configure(text="ошибка", text_color="red")
            time.sleep(2.0)

    def process_files(self):
        base_path = Path(self.source_dir)
        files_data = []
        unique_projects = set() # Множество для уникальных имен
        
        exclude_patterns = re.compile(r'\(Copy\)|_layer', re.IGNORECASE)
        
        for ext in ['*.svg', '*.css', '*.png']:
            for file_path in base_path.glob(ext):
                size = file_path.stat().st_size // 1024
                info = f"Размер: {size} KB"
                
                stem = file_path.stem
                clean_name = exclude_patterns.sub('', stem)
                
                if "_" in clean_name:
                    project_name = clean_name.rsplit('_', 1)[0]
                else:
                    project_name = clean_name
                
                project_name = project_name.strip()
                if not project_name: project_name = "Default"
                
                unique_projects.add(project_name)

                if file_path.suffix == '.css':
                    try:
                        content = file_path.read_text(encoding='utf-8', errors='ignore')
                        colors = len(re.findall(r'#(?:[0-9a-fA-F]{3}){1,2}|rgba?\([^)]+\)', content))
                        info += f" | Цветов: {colors}"
                    except: pass
                
                files_data.append({
                    "project": project_name,
                    "name": file_path.name, 
                    "type": file_path.suffix.upper(), 
                    "info": info
                })

        if files_data:
            # Сортируем и обновляем Combobox
            sorted_projects = sorted(list(unique_projects))
            self.project_combo.configure(values=sorted_projects)
            self.project_combo.set(sorted_projects[0]) # Устанавливаем первый по списку
            
            self.generate_html(files_data)
            self.textbox.insert("end", f"✅ Обработано {len(files_data)} файлов. Найдено проектов: {len(sorted_projects)}.\n")
            self.btn_open.configure(state="normal")
        else:
            self.textbox.insert("end", f"❌ Файлы не найдены в: {self.source_dir}\n")

    def generate_html(self, data):
        rows = "".join([
            f"<tr><td>{i['project']}</td><td>{i['name']}</td><td>{i['type']}</td><td>{i['info']}</td></tr>" 
            for i in data
        ])
        
        html = f"""<html><head><meta charset='UTF-8'><style>
            body {{ background:#0a0a0a; color:#eee; font-family:'Segoe UI', sans-serif; padding:40px; }}
            table {{ width:100%; border-collapse:collapse; margin-top:20px; }}
            th, td {{ padding:12px 15px; border:1px solid #333; text-align:left; }}
            th {{ background:#1a1a1a; color:#bb86fc; text-transform: uppercase; font-size: 12px; }}
            tr:nth-child(even) {{ background: #111; }}
            tr:hover {{ background: #1d1d1d; border-left: 3px solid #bb86fc; }}
            h2 {{ color: #03dac6; border-bottom: 2px solid #333; padding-bottom: 10px; }}
        </style></head><body>
            <h2>Asset Mapper 2026 Report</h2>
            <table>
                <thead><tr><th>Проект</th><th>Имя файла</th><th>Формат</th><th>Детали</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </body></html>"""
        
        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write(html)

    def open_report(self):
        webbrowser.open(f"file:///{os.path.abspath(self.output_file)}")

if __name__ == "__main__":
    app = SplashScreen(AssetMapperApp)
    app.mainloop()