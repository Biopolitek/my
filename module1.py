import os
import time
import sqlite3
import subprocess
import multiprocessing
import shutil
import sys
from pathlib import Path
from threading import Thread
import customtkinter as ctk

# --- ИСПРАВЛЕНИЕ ОШИБКИ PYINSTALLER/MULTIPROCESSING ---
def redirect_multiprocessing_streams():
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w')

# ГЛОБАЛЬНЫЕ НАСТРОЙКИ
PATH_RESOURCES = Path(r"E:\dev\dist\exports")
PATH_SITES_ROOT = Path(r"E:\dev\dist\sites")
DB_PATH = "assets_state.db"

class EnterpriseEngineV140(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Enterprise Asset Guard v1.4.0 - ULTIMATE")
        self.geometry("850x700")
        
        self._setup_db()
        self.available_projects = self._scan_available_projects()
        self.project_name_var = ctk.StringVar(value=self.available_projects[0] if self.available_projects else "New_Project_Name")
        
        self._init_ui()
        self._start_temp_monitor()

    def _setup_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("CREATE TABLE IF NOT EXISTS queue (id INTEGER PRIMARY KEY, path TEXT, status TEXT)")

    def _scan_available_projects(self):
        """Сканирует папку ресурсов и предлагает названия проектов на основе подпапок/имен файлов"""
        projects = set()
        if PATH_RESOURCES.exists():
            # Пример эвристики: берем имена папок первого уровня или уникальные префиксы файлов
            for item in PATH_RESOURCES.iterdir():
                if item.is_dir():
                    projects.add(item.name)
        
        return sorted(list(projects if projects else ["Default_Project"]))

    def _init_ui(self):
        ctk.CTkLabel(self, text="СИСТЕМА СБОРКИ ЛЮБОЙ СЛОЖНОСТИ", font=("Arial", 22, "bold")).pack(pady=20)
        
        # Фрейм для выбора проекта (Маска/Выбор)
        proj_frame = ctk.CTkFrame(self)
        proj_frame.pack(pady=10)

        # Поле ввода (Маска)
        ctk.CTkEntry(proj_frame, textvariable=self.project_name_var, width=250).pack(side="left", padx=10)
        
        # Выпадающий список доступных проектов (для быстрого выбора маски)
        self.project_option_menu = ctk.CTkOptionMenu(proj_frame, values=self.available_projects, variable=self.project_name_var)
        self.project_option_menu.pack(side="left", padx=10)

        # Монитор состояния
        self.monitor_frame = ctk.CTkFrame(self)
        self.monitor_frame.pack(pady=10, fill="x", padx=30)
        
        self.lbl_status = ctk.CTkLabel(self.monitor_frame, text="Статус: Ожидание")
        self.lbl_status.pack(side="left", padx=20)
        self.lbl_temp = ctk.CTkLabel(self.monitor_frame, text="CPU: ") 
        self.lbl_temp.pack(side="right", padx=20)

        # Консоль вывода
        self.console = ctk.CTkTextbox(self, width=750, height=300)
        self.console.pack(pady=10)

        # Кнопка "Поехали!"
        self.btn_start = ctk.CTkButton(self, text="Поехали!", fg_color="green", command=self.start_pipeline)
        self.btn_start.pack(pady=20)

    def _get_cpu_temp(self):
        try:
            cmd = "powershell (Get-CimInstance MSAcpi_ThermalZoneTemperature -Namespace root/wmi).CurrentTemperature"
            res = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().strip()
            return (int(res) / 10.0) - 273.15
        except: return 0.0

    def _start_temp_monitor(self):
        def update_temp():
            while True:
                temp = self._get_cpu_temp()
                color = "red" if temp > 80 else "white"
                self.lbl_temp.after(0, lambda t=temp, c=color: self.lbl_temp.configure(text=f"CPU: {t:.1f}°C", text_color=c))
                time.sleep(1)
        Thread(target=update_temp, daemon=True).start()

    def start_pipeline(self):
        project_name = self.project_name_var.get()
        if project_name in ["", "New_Project_Name", "Default_Project"] and project_name not in self.available_projects:
            self.console.insert("end", ">>> Ошибка: Укажите имя проекта или выберите маску из списка.\n")
            return

        self.btn_start.configure(state="disabled")
        self.lbl_status.configure(text="Статус: Сборка...")
        
        # Определяем ресурсы для передачи в worker на основе маски
        resources_to_process = self._get_filtered_resources(project_name)
        
        # Передаем список файлов через очередь или как аргумент (для multiprocessing проще через менеджер или явно)
        # Для простоты передадим только пути, worker их обработает
        resource_paths = [str(f) for f in resources_to_process]

        mp_manager = multiprocessing.Manager()
        shared_resource_list = mp_manager.list(resource_paths)

        p = multiprocessing.Process(target=engine_worker, args=(project_name, shared_resource_list))
        p.start()
        self.console.insert("end", f">>> Конвейер запущен для проекта: {project_name} ({len(resource_paths)} файлов).\n")

    def _get_filtered_resources(self, project_mask):
        """Фильтрует файлы в папке exports по имени проекта/маске"""
        all_files = list(PATH_RESOURCES.rglob("*.*"))
        
        # Если маска - это имя папки, берем все из этой папки
        filtered = [f for f in all_files if project_mask in str(f) or project_mask in f.parts]
        
        # Если фильтр пустой, берем все, но предупреждаем
        if not filtered:
            self.console.insert("end", f">>> Внимание: Маска '{project_mask}' не найдена. Обработка всех ресурсов.\n")
            return all_files
        
        return filtered

# ==========================================================
# ЯДРО СБОРКИ (ENGINE WORKER)
# ==========================================================
def engine_worker(project_name, resource_paths_shared):
    redirect_multiprocessing_streams() # !!! Вызов исправления !!!

    target_path = PATH_SITES_ROOT / project_name
    target_path.mkdir(parents=True, exist_ok=True)
    
    files = [Path(p) for p in resource_paths_shared]
    sem = multiprocessing.Semaphore(4) 
    
    for f in files:
        while get_static_temp() > 84.0: 
            time.sleep(2) 
        
        multiprocessing.Process(target=process_task, args=(f, target_path, sem)).start()

# ... process_task и get_static_temp остаются без изменений ...
def process_task(file, target, sem):
    redirect_multiprocessing_streams() # !!! Вызов исправления !!!
    with sem:
        tmp_file = target / ".tmp" / file.name
        tmp_file.parent.mkdir(exist_ok=True)
        shutil.copy2(file, tmp_file)
        os.replace(tmp_file, target / file.name)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE queue SET status='PROCESSED' WHERE path=?", (str(file),))

def get_static_temp():
    try:
        cmd = "powershell (Get-CimInstance MSAcpi_ThermalZoneTemperature -Namespace root/wmi).CurrentTemperature"
        res = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().strip()
        return (int(res) / 10.0) - 273.15
    except: return 40.0

if __name__ == "__main__":
    multiprocessing.freeze_support()
    EnterpriseEngineV140().mainloop()