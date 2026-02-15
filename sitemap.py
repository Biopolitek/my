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
import tkinterweb as tkweb

# Зависимости: pip install customtkinter tkinterweb pillow easyocr

try:
    import easyocr
    HAS_OCR = True
    # Инициализация OCR (RU/EN). В 2026 использует GPU через CUDA при наличии
    READER = easyocr.Reader(['ru', 'en']) 
except Exception as e:
    HAS_OCR = False
    READER = None
    print(f"OCR Init Error: {e}")

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class SplashScreen(ctk.CTk):
    def __init__(self, main_app_class):
        super().__init__()
        self.main_app_class = main_app_class
        self.overrideredirect(True)
        w, h = 500, 300
        self.geometry(f"{w}x{h}+{(self.winfo_screenwidth()-w)//2}+{(self.winfo_screenheight()-h)//2}")
        
        ctk.CTkLabel(self, text="ASSET MAPPER 2026", font=("Arial", 24, "bold")).pack(expand=True)
        ctk.CTkLabel(self, text="Загрузка системы анализа...", font=("Arial", 12)).pack(pady=20)
        self.after(1500, self.start_main_app)

    def start_main_app(self):
        main_app = self.main_app_class()
        self.destroy()
        main_app.mainloop()

class AssetMapperApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Asset Mapper & OCR 2026")
        self.geometry("1200x900")
        
        # Настройки путей 2026
        self.base_output_dir = Path("E:/dev/dist/sites")
        self.source_dir = Path("E:/dev/dist/exports")
        
        self.project_files_map = {} 
        self.current_project_files = [] 
        self.current_file_index = -1
        self.stop_monitor = False

        os.makedirs(self.base_output_dir, exist_ok=True)
        os.makedirs(self.source_dir, exist_ok=True)
            
        self.setup_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        threading.Thread(target=self.update_temp_loop, daemon=True).start()

    def setup_ui(self):
        # Левая панель
        self.control_frame = ctk.CTkFrame(self, width=300, corner_radius=0)
        self.control_frame.pack(side="left", fill="y")
        
        ctk.CTkLabel(self.control_frame, text="Asset Analyzer", font=("Arial", 18, "bold")).pack(pady=15)
        
        self.btn_run = ctk.CTkButton(self.control_frame, text="АНАЛИЗИРОВАТЬ EXPORTS", command=self.process_files, height=45, fg_color="#3700b3")
        self.btn_run.pack(pady=10, padx=15, fill="x")

        self.project_combo = ctk.CTkComboBox(self.control_frame, values=["Нет данных"], command=self.on_project_select)
        self.project_combo.pack(pady=5, padx=15, fill="x")
        
        self.btn_read_ocr = ctk.CTkButton(self.control_frame, text="ЗАПУСТИТЬ ПАКЕТНЫЙ OCR", command=self.read_project_elements, state="disabled")
        self.btn_read_ocr.pack(pady=10, padx=15, fill="x")
        
        self.btn_open = ctk.CTkButton(self.control_frame, text="ОТКРЫТЬ ПАПКУ САЙТОВ", command=self.open_report_folder, state="disabled", fg_color="#03dac6", text_color="black")
        self.btn_open.pack(pady=5, padx=15, fill="x")

        self.textbox = ctk.CTkTextbox(self.control_frame, font=("Consolas", 11))
        self.textbox.pack(pady=10, padx=15, fill="both", expand=True)

        # Правая панель (Просмотр)
        self.browser_frame = ctk.CTkFrame(self)
        self.browser_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        self.webview = tkweb.HtmlFrame(self.browser_frame)
        self.webview.pack(fill="both", expand=True)

        self.nav_frame = ctk.CTkFrame(self.browser_frame, fg_color="transparent")
        self.nav_frame.pack(fill="x", pady=5)
        
        self.btn_back = ctk.CTkButton(self.nav_frame, text="<", command=lambda: self.navigate_file(-1), width=40)
        self.btn_back.pack(side="left", padx=5)
        
        self.nav_label = ctk.CTkLabel(self.nav_frame, text="Выберите проект")
        self.nav_label.pack(side="left", expand=True)
        
        self.btn_forward = ctk.CTkButton(self.nav_frame, text=">", command=lambda: self.navigate_file(1), width=40)
        self.btn_forward.pack(side="right", padx=5)
        
        self.temp_label = ctk.CTkLabel(self.browser_frame, text="--°C", font=("Consolas", 16, "bold"), text_color="#ff5555")
        self.temp_label.place(relx=1.0, rely=0.0, anchor="ne", x=-15, y=15)

    def update_temp_loop(self):
        ps_cmd = "$t = (Get-CimInstance -Namespace root/wmi -ClassName MsAcpi_ThermalZoneTemperature).CurrentTemperature; if($t){($t/10-273.15)}else{'N/A'}"
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        while not self.stop_monitor:
            try:
                output = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps_cmd], startupinfo=startupinfo, creationflags=subprocess.CREATE_NO_WINDOW).decode('cp866').strip()
                if output and "N/A" not in output:
                    val = float(output.replace(',', '.'))
                    self.temp_label.configure(text=f"{val:.1f}°C")
            except: pass
            time.sleep(3.0)

    def process_files(self):
        self.textbox.delete("1.0", "end")
        unique_projects = set()
        self.project_files_map = {}
        exclude = re.compile(r'\(Copy\)|_layer', re.IGNORECASE)

        for ext in ['*.svg', '*.css', '*.png']:
            for fp in self.source_dir.glob(ext):
                clean = exclude.sub('', fp.stem)
                # Логика 2026: обрезаем по КРАЙНЕМУ знаку подчеркивания
                proj = clean.rsplit('_', 1)[0].strip() if "_" in clean else clean.strip()
                if not proj: proj = "Default"
                
                unique_projects.add(proj)
                self.project_files_map.setdefault(proj, []).append(str(fp.resolve()))

        if unique_projects:
            sorted_projs = sorted(list(unique_projects))
            self.project_combo.configure(values=sorted_projs)
            self.project_combo.set(sorted_projs[0])
            self.on_project_select(sorted_projs[0])
            self.btn_open.configure(state="normal")
            self.textbox.insert("end", f"✅ Найдено проектов: {len(sorted_projs)}\n")
        else:
            self.textbox.insert("end", "❌ Файлы не найдены\n")

    def on_project_select(self, project_name):
        self.current_project_files = []
        all_paths = self.project_files_map.get(project_name, [])
        
        for fpath in all_paths:
            if Path(fpath).suffix.lower() in ['.png', '.svg']:
                self.current_project_files.append(fpath)
        
        self.current_project_files.sort()
        self.current_file_index = -1
        
        # Разблокировка OCR при выборе любого проекта
        if HAS_OCR and project_name != "Нет данных":
            self.btn_read_ocr.configure(state="normal", fg_color="#6200ee")
        
        if self.current_project_files:
            self.navigate_file(1)
        else:
            self.webview.load_html("<body style='background:#222;'></body>")
            self.nav_label.configure(text="Нет ассетов")

    def navigate_file(self, direction):
        new_index = self.current_file_index + direction
        if 0 <= new_index < len(self.current_project_files):
            self.current_file_index = new_index
            f_path = self.current_project_files[self.current_file_index]
            self.webview.load_file(f_path)
            self.nav_label.configure(text=f"{self.current_file_index+1}/{len(self.current_project_files)}")
            self.btn_back.configure(state="normal" if self.current_file_index > 0 else "disabled")
            self.btn_forward.configure(state="normal" if self.current_file_index < len(self.current_project_files)-1 else "disabled")

    def read_project_elements(self):
        project_name = self.project_combo.get()
        png_list = [f for f in self.project_files_map.get(project_name, []) if f.lower().endswith('.png')]
        
        if not png_list:
            self.textbox.insert("end", "В проекте нет PNG файлов для OCR\n")
            return

        self.textbox.insert("end", f"\n--- Пакетный OCR: {project_name} ---\n")
        
        def ocr_thread():
            report_items = []
            for path in png_list:
                fname = Path(path).name
                self.after(0, lambda n=fname: self.textbox.insert("end", f"Обработка {n}...\n"))
                try:
                    res = READER.readtext(path)
                    found_text = " | ".join([t for (_, t, p) in res if p > 0.2])
                    report_items.append({"name": fname, "text": found_text or "[Ничего]"})
                except Exception as e:
                    report_items.append({"name": fname, "text": f"Ошибка: {e}"})
            
            self.save_ocr_report(project_name, report_items)
            self.after(0, lambda: self.textbox.insert("end", "✅ OCR отчет создан в папке проекта!\n"))

        threading.Thread(target=ocr_thread, daemon=True).start()

    def save_ocr_report(self, project_name, data):
        p_dir = self.base_output_dir / project_name
        p_dir.mkdir(parents=True, exist_ok=True)
        
        rows = "".join([f"<tr><td>{i['name']}</td><td>{i['text']}</td></tr>" for i in data])
        html = f"<html><head><meta charset='utf-8'><style>body{{background:#0a0a0a;color:#00ff41;font-family:monospace;padding:20px;}} table{{width:100%;border-collapse:collapse;}} td,th{{padding:10px;border:1px solid #333;}} th{{color:#bb86fc;}}</style></head><body><h2>OCR: {project_name}</h2><table><tr><th>Файл</th><th>Текст</th></tr>{rows}</table></body></html>"
        
        report_path = p_dir / "ocr_report.html"
        report_path.write_text(html, encoding="utf-8")
        self.after(0, lambda: self.webview.load_file(str(report_path.resolve())))

    def open_report_folder(self):
        webbrowser.open(str(self.base_output_dir.resolve()))

    def on_closing(self):
        self.stop_monitor = True
        self.destroy()

if __name__ == "__main__":
    app = SplashScreen(AssetMapperApp)
    app.mainloop()