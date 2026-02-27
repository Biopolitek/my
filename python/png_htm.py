import customtkinter as ctk
from tkinter import filedialog, messagebox
import easyocr
import os
from PIL import Image

# Настройки темы
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class WebOCRApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Web Element OCR Scanner 2026")
        self.geometry("600x450")

        # Инициализация OCR (будет загружен при первом запуске)
        # Добавлены русский и английский языки
        try:
            self.reader = easyocr.Reader(['ru', 'en'], gpu=False) 
        except Exception as e:
            print(f"Ошибка инициализации OCR: {e}")

        self.file_path = None
        self.extracted_text = ""

        # Создание интерфейса
        self.setup_ui()

    def setup_ui(self):
        # Заголовок
        self.label_title = ctk.CTkLabel(self, text="OCR Сканер PNG", font=("Arial", 24, "bold"))
        self.label_title.pack(pady=20)

        # Информационная панель
        self.info_label = ctk.CTkLabel(self, text="Шаг 1: Выберите скриншот интерфейса", text_color="gray")
        self.info_label.pack(pady=5)

        # Кнопки управления
        self.btn_select = ctk.CTkButton(self, text="📁 Выбрать PNG", command=self.select_file)
        self.btn_select.pack(pady=10)

        self.btn_ocr = ctk.CTkButton(self, text="🔍 Распознать элементы", command=self.process_ocr, state="disabled")
        self.btn_ocr.pack(pady=10)

        self.btn_save = ctk.CTkButton(self, text="💾 Сохранить результат", command=self.save_to_file, 
                                     state="disabled", fg_color="#27ae60", hover_color="#2ecc71")
        self.btn_save.pack(pady=10)

        # Статус-бар
        self.status_label = ctk.CTkLabel(self, text="Готов к работе", text_color="white")
        self.status_label.pack(side="bottom", pady=20)

    def select_file(self):
        path = filedialog.askopenfilename(
            title="Выберите изображение",
            filetypes=[("PNG Images", "*.png"), ("All files", "*.*")]
        )
        if path:
            self.file_path = path
            filename = os.path.basename(path)
            self.info_label.configure(text=f"Выбран файл: {filename}", text_color="white")
            self.btn_ocr.configure(state="normal")
            self.status_label.configure(text="Файл загружен. Нажмите 'Распознать'")

    def process_ocr(self):
        if not self.file_path:
            return

        self.status_label.configure(text="⏳ Идет распознавание... Пожалуйста, подождите")
        self.btn_ocr.configure(state="disabled")
        self.update()

        try:
            # detail=0 возвращает только текст. 
            # Если нужны координаты элементов, используйте detail=1
            results = self.reader.readtext(self.file_path, detail=0)
            
            if results:
                self.extracted_text = "\n".join(results)
                self.status_label.configure(text=f"✅ Готово! Найдено элементов: {len(results)}", text_color="lightgreen")
                self.btn_save.configure(state="normal")
            else:
                self.status_label.configure(text="Текст не обнаружен", text_color="yellow")
                
        except Exception as e:
            messagebox.showerror("Ошибка OCR", f"Произошла ошибка при анализе: {str(e)}")
            self.status_label.configure(text="Ошибка анализа", text_color="red")
        finally:
            self.btn_ocr.configure(state="normal")

    def save_to_file(self):
        if not self.extracted_text:
            return

        file_to_save = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile="web_elements_result.txt",
            filetypes=[("Text files", "*.txt")]
        )

        if file_to_save:
            try:
                with open(file_to_save, "w", encoding="utf-8") as f:
                    f.write("--- Результаты OCR сканирования ---\n")
                    f.write(self.extracted_text)
                messagebox.showinfo("Успех", f"Результаты сохранены в:\n{file_to_save}")
                self.status_label.configure(text="Файл успешно сохранен")
            except Exception as e:
                messagebox.showerror("Ошибка сохранения", f"Не удалось сохранить файл: {e}")

if __name__ == "__main__":
    app = WebOCRApp()
    app.mainloop()