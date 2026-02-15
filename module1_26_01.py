import os
import sqlite3
import psutil
import time
import threading
import shutil
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk, ImageDraw

# --- КОНФИГУРАЦИЯ ---
EXPORT_PATH = r"E:\dev\dist\exports"
SITES_PATH = r"E:\dev\dist\sites"
DB_NAME = "assets_state.db"

class AssetEngine(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Asset Engine & AI Instructor 2026 (Tkinter)")
        self.geometry("1100x850")
        
        self.current_mode = "Normal"
        self.projects_data = {}  
        self.current_project_name = None
        self.cpu_temp_value = "N/A" # Изначально температура неизвестна
        
        self._init_db()
        self._build_ui()
        self._start_thermal_monitor()

    def _init_db(self):
        conn = sqlite3.connect(DB_NAME)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE IF NOT EXISTS ai_knowledge (id INTEGER PRIMARY KEY, query TEXT, solution TEXT)")
        conn.close()

    def _build_ui(self):
        self.top_bar = tk.Frame(self, height=50, bg='#DDDDDD')
        self.top_bar.pack(fill="x", padx=10, pady=5)
        
        # Обновленная метка статуса
        self.cpu_info = tk.Label(self.top_bar, text=f"Temp: {self.cpu_temp_value}°C | Mode: Normal", font=("Arial", 14, "bold"), bg='#DDDDDD')
        self.cpu_info.pack(side="left", padx=20)
        
        self.project_select = ttk.Combobox(self.top_bar, state="readonly", width=30)
        self.project_select.bind("<<ComboboxSelected>>", self._on_project_selected)
        
        self.preview_frame = tk.Frame(self, bg='#1e1e1e')
        self.preview_frame.pack(expand=True, fill="both", padx=10, pady=10)
        self.preview_label = tk.Label(self.preview_frame, text="Ожидание сканирования...", bg='#1e1e1e', fg='white')
        self.preview_label.pack(expand=True)
        
        self.ctrl_frame = tk.Frame(self, height=100, bg='#DDDDDD')
        self.ctrl_frame.pack(fill="x", padx=10, pady=10)
        
        tk.Button(self.ctrl_frame, text="< Назад (Проект)", command=lambda: self._nav(-1)).pack(side="left", padx=10)
        tk.Button(self.ctrl_frame, text="Просканировать exports", command=self.scan_assets).pack(side="left", padx=10)
        
        self.btn_go = tk.Button(self.ctrl_frame, text="ПОЕХАЛИ! (Сборка)", fg="white", bg="#2ecc71", command=self.start_build)
        self.btn_go.pack(side="left", padx=20)
        
        tk.Button(self.ctrl_frame, text="Вперед > (Проект)", command=lambda: self._nav(1)).pack(side="left", padx=10)

    def _start_thermal_monitor(self):
        def monitor():
            while True:
                # Попытка получить реальные данные с датчика
                try:
                    t_data = psutil.sensors_temperatures()
                    if 'coretemp' in t_data:
                        self.cpu_temp_value = int(t_data['coretemp'][0].current)
                    elif t_data:
                         # Запасной вариант, если имя датчика другое (e.g., 'cpu_thermal')
                         self.cpu_temp_value = int(list(t_data.values())[0][0].current)
                    else:
                        self.cpu_temp_value = "N/A"
                except Exception:
                    self.cpu_temp_value = "N/A" # Если psutil не может прочитать данные
                
                # Логика ТЗ: Режимы нагрузки
                if self.cpu_temp_value != "N/A" and self.cpu_temp_value >= 84: 
                    self.current_mode = "COOLING"
                elif self.cpu_temp_value != "N/A" and self.cpu_temp_value >= 80:
                    self.current_mode = "AI-Throttling"
                else:
                    self.current_mode = "Normal"
                
                # Обновление строки статуса
                self.cpu_info.config(text=f"Temp: {self.cpu_temp_value}°C | Mode: {self.current_mode}")
                time.sleep(1)
        threading.Thread(target=monitor, daemon=True).start()

    def scan_assets(self):
        if not os.path.exists(EXPORT_PATH): os.makedirs(EXPORT_PATH)
        files = [f for f in os.listdir(EXPORT_PATH) if os.path.isfile(os.path.join(EXPORT_PATH, f))]
        self.projects_data = {}
        
        for f in files:
            if "_" in f:
                idx = f.rfind("_")
                p_name = f[:idx]
            else:
                p_name = "DefaultProject"
                
            if p_name not in self.projects_data:
                self.projects_data[p_name] = []
            self.projects_data[p_name].append(f)
            
        names = list(self.projects_data.keys())
        if names:
            self.project_select['values'] = names
            self.project_select.current(0) 
            self.project_select.pack(side="right", padx=20) 
            self.current_project_name = self.project_select.get()
            self._render_preview()

    def _on_project_selected(self, event):
        self.current_project_name = event.widget.get() 
        self._render_preview()

    def _render_preview(self):
        if not self.current_project_name: return
        
        img = Image.new('RGB', (800, 450), color='#FFFFFF')
        draw = ImageDraw.Draw(img)
        
        draw.rectangle((0, 0, 800, 450), fill="#ecf0f1")
        draw.rectangle((0, 0, 800, 60), fill="#2c3e50")
        draw.text((20, 20), f"Header: {self.current_project_name}", fill="white")

        draw.rectangle((20, 80, 780, 400), fill="#ffffff", outline="#bdc3c7")
        draw.text((40, 100), "Основной контент (Генерируется AI)", fill="#7f8c8d")
        
        draw.rectangle((450, 150, 750, 350), fill="#95a5a6", outline="#7f8c8d")
        draw.text((460, 240), "JXL/AVIF Asset Preview", fill="white")

        draw.rectangle((0, 410, 800, 450), fill="#bdc3c7")
        draw.text((20, 415), "Footer 2026", fill="#7f8c8d")

        ctk_img = ImageTk.PhotoImage(img)
        self.preview_label.config(image=ctk_img) 
        self.preview_label.image = ctk_img

    def _nav(self, step):
        if not self.projects_data: return
        names = list(self.projects_data.keys())
        try:
            curr_idx = names.index(self.current_project_name)
            new_idx = (curr_idx + step) % len(names)
            
            self.project_select.current(new_idx)
            self.current_project_name = names[new_idx]
            self._render_preview()
        except ValueError:
            pass

    def start_build(self):
        if self.current_mode == "COOLING":
            messagebox.showerror("Ошибка сборки", "Система перегрета (>= 84°C), сборка остановлена.")
            return
            
        if self.current_project_name in [None, ""]:
            messagebox.showwarning("Ошибка", "Сначала просканируйте ресурсы и выберите проект.")
            return

        target_dir = os.path.join(SITES_PATH, self.current_project_name)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        for file_name in self.projects_data[self.current_project_name]:
            source_path = os.path.join(EXPORT_PATH, file_name)
            shutil.copy(source_path, target_dir)
            print(f"Копирование: {file_name} -> {target_dir}")

        messagebox.showinfo("Сборка завершена", f"Сайт проекта '{self.current_project_name}' собран в папке:\n{target_dir}")

if __name__ == "__main__":
    app = AssetEngine()
    app.mainloop()
