import subprocess
import time
import sys
import os
import re
import json

# Конфигурация
PROJECT_PATH = "" # Будет взято из sys.argv

def get_cpu_temp():
    try:
        cmd = "wmic /namespace:\\\\root\\wmi PATH MSAcpi_ThermalZoneTemperature get CurrentTemperature"
        result = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode()
        digits = "".join(filter(str.isdigit, result))
        return round((int(digits) / 10.0) - 273.15, 1) if digits else None
    except: return None

def technical_audit(project_path):
    report = []
    config_path = os.path.join(project_path, "config.json")
    if not os.path.exists(config_path):
        return [f" [!] Ошибка: config.json не найден"]

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            brand_colors = [c.upper() for c in config.get('colors', {}).values()]
    except: return [" [!] Ошибка чтения конфига"]

    hex_pattern = r'#(?:[0-9a-fA-F]{3}){1,2}'
    px_pattern = r'[:\s](\d+)px'

    for root, _, files in os.walk(project_path):
        for file in files:
            if file.endswith(('.css', '.scss', '.svg', '.php', '.html')):
                try:
                    with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        found_colors = re.findall(hex_pattern, content)
                        for color in set(found_colors):
                            if color.upper() not in brand_colors:
                                report.append(f" [!] {file}: Неверный цвет {color}")
                        if file.endswith(('.css', '.scss')):
                            for val in re.findall(px_pattern, content):
                                if int(val) > 1 and int(val) % 8 != 0:
                                    report.append(f" [!] {file}: Отступ {val}px не кратен 8px")
                except: continue
    return report

def main():
    if len(sys.argv) < 2:
        print("Использование: validator_pro.exe <путь_к_проекту>")
        sys.exit(1)

    project_path = sys.argv[1]
    
    # Очистка экрана перед стартом
    os.system('cls' if os.name == 'nt' else 'clear')

    try:
        while True:
            temp = get_cpu_temp()
            audit_results = technical_audit(project_path)
            
            # 1. Возвращаем курсор в начало (0,0) для обновления верхней панели
            # \033[H - переместить курсор в начало, \033[K - очистить строку
            sys.stdout.write("\033[H") 
            
            # Рисуем статус-бар (всегда вверху)
            cpu_status = f" {temp if temp else '??'} C"
            audit_status = "OK" if not audit_results else f"{len(audit_results)} ERR"
            
            # Форматированная панель
            print(f"================================================================")
            print(f" CPU TEMP: [{cpu_status}] | STATUS: [{audit_status}] | SITE: {os.path.basename(project_path)}")
            print(f"================================================================")
            sys.stdout.write("\033[K") # Очистка строки под панелью
            
            # 2. Вывод ошибок (ниже панели)
            if audit_results:
                print(f"\n ОТЧЕТ ОБ УЗЛАХ ДЛЯ ПЕРЕДЕЛКИ (QWEN):")
                # Выводим только последние 15 ошибок, чтобы не "забивать" экран
                for line in audit_results[:15]:
                    print(line)
                    sys.stdout.write("\033[K\n")
            else:
                print(f"\n ✅ Проверка пройдена: 130% качества соблюдено.")
                sys.stdout.write("\033[J") # Очистить всё, что ниже

            time.sleep(2) # Быстрый цикл для температуры
    except KeyboardInterrupt:
        print("\nКонвейер остановлен.")

if __name__ == "__main__":
    # Включаем поддержку ANSI кодов в Windows 10/11
    if os.name == 'nt':
        os.system('') 
    main()