import os, time, sqlite3, subprocess, multiprocessing, shutil
import customtkinter as ctk
from pathlib import Path
from multiprocessing import Process, Event, Semaphore, Queue

# ГЛОБАЛЬНЫЕ КОНСТАНТЫ
PATH_RESOURCES = Path(r"E:\dev\dist\exports")
PATH_SITES_ROOT = Path(r"E:\dev\dist\sites")
DB_PATH = "assets_state.db"

class EnterpriseEngineV140(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Enterprise Asset Guard v1.4.0 - ULTIMATE")
        self.geometry("800x650")
        self.stop_signal = Event()
        self.project_name = ctk.StringVar(value="Project_Alpha")
        self._init_ui()

    def _init_ui(self):
        ctk.CTkLabel(self, text="СИСТЕМА СБОРКИ ЛЮБОЙ СЛОЖНОСТИ", font=("Arial", 22, "bold")).pack(pady=20)
        
        # Поле проекта
        ctk.CTkEntry(self, textvariable=self.project_name, width=400).pack(pady=10)

        # Монитор состояния
        self.monitor_frame = ctk.CTkFrame(self)
        self.monitor_frame.pack(pady=10, fill="x", padx=30)
        self.lbl_status = ctk.CTkLabel(self.monitor_frame, text="Статус: Ожидание")
        self.lbl_status.pack(side="left", padx=20)
        self.lbl_temp = ctk.CTkLabel(self.monitor_frame, text="CPU: --°C")
        self.lbl_temp.pack(side="right", padx=20)

        # Консоль вывода
        self.console = ctk.CTkTextbox(self, width=700, height=250)
        self.console.pack(pady=10)

        # Управление
        self.btn_start = ctk.CTkButton(self, text="ЗАПУСТИТЬ КОНВЕЙЕР", fg_color="green", command=self.start_pipeline)
        self.btn_start.pack(pady=20)

    def start_pipeline(self):
        self.btn_start.configure(state="disabled")
        # Инициализация БД в режиме WAL для исключения блокировок
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("CREATE TABLE IF NOT EXISTS queue (id INTEGER PRIMARY KEY, path TEXT, status TEXT)")
        
        Process(target=engine_worker, args=(self.stop_signal, self.project_name.get()), daemon=True).start()

def engine_worker(stop_event, project_name):
    """Ядро сборщика: Адаптивная нагрузка"""
    target_path = PATH_SITES_ROOT / project_name
    target_path.mkdir(parents=True, exist_ok=True)
    
    # Семафор для контроля 4-х потоков
    sem = Semaphore(4)
    
    # Сканирование ресурсов любой сложности
    files = list(PATH_RESOURCES.rglob("*.*"))
    
    for idx, file in enumerate(files):
        # Проверка температуры и адаптивный троттлинг
        temp = get_temp()
        if temp > 80.0:
            time.sleep(2) # Замедляем конвейер
        if temp >= 84.0:
            stop_event.set()
            while get_temp() > 72.0: time.sleep(5)
            stop_event.clear()

        # Потоковая сборка
        Process(target=process_task, args=(file, target_path, sem)).start()

def process_task(file, target, sem):
    with sem:
        # Транзакционная сборка в .tmp
        tmp_file = target / ".tmp" / file.name
        tmp_file.parent.mkdir(exist_ok=True)
        shutil.copy2(file, tmp_file) # Имитация обработки
        os.replace(tmp_file, target / file.name)

def get_temp():
    cmd = "powershell (Get-CimInstance MSAcpi_ThermalZoneTemperature -Namespace root/wmi).CurrentTemperature"
    res = subprocess.check_output(cmd, shell=True).decode().strip()
    return (int(res) / 10.0) - 273.15

if __name__ == "__main__":
    multiprocessing.freeze_support()
    EnterpriseEngineV140().mainloop()