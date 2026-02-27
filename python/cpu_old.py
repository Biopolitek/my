import subprocess
import time
import sys

def get_temp_final():
    try:
        # Прямой опрос через устаревший, но всё еще работающий в 2026 wmic
        # Он часто обходит ограничения новых счетчиков PowerShell
        cmd = "wmic /namespace:\\\\root\\wmi PATH MSAcpi_ThermalZoneTemperature get CurrentTemperature"
        result = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode()
        
        # Очищаем вывод от лишних букв и берем только цифры
        digits = "".join(filter(str.isdigit, result))
        if digits:
            # Конвертация: (Kelvin * 10) -> Celsius
            temp_c = (int(digits) / 10.0) - 273.15
            return round(temp_c, 1)
        return None
    except:
        return None

def main():
    print("--- Глубокий мониторинг CPU (WMIC Mode) ---")
    try:
        while True:
            temp = get_temp_final()
            if temp:
                sys.stdout.write(f"\r[SYSTEM MONITOR] CPU: {temp} C    ")
            else:
                sys.stdout.write("\r[!] Ошибка: Запустите EXE от имени АДМИНИСТРАТОРА ")
            sys.stdout.flush()
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nОстановлено.")

if __name__ == "__main__":
    main()