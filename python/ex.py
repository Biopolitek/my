import os
import zlib
import re
import fitz  # PyMuPDF
from psd_tools import PSDImage
import tkinter as tk
from tkinter import filedialog, messagebox

class DesignExporter:
    def __init__(self, root):
        self.root = root
        self.root.title("Design Asset Engine v8.0 (Lossless & Fonts)")
        self.root.geometry("500x550")
        self.root.configure(bg="#1a1a1a")
        
        # Стили интерфейса
        btn_params = {"font": ("Arial", 10, "bold"), "fg": "white", "width": 42, "pady": 10}
        tk.Label(root, text="UNIVERSAL ASSET ENGINE", fg="#00ffcc", bg="#1a1a1a", pady=25, font=("Arial", 14, "bold")).pack()

        # Основные кнопки
        tk.Button(root, text="PSD: РЕСУРСЫ + CSS + ШРИФТЫ", bg="#006cbe", command=self.run_psd, **btn_params).pack(pady=5)
        tk.Button(root, text="PDF: SVG СТРАНИЦЫ + ВШИТЫЕ ШРИФТЫ", bg="#cc3300", command=self.run_pdf, **btn_params).pack(pady=5)
        tk.Button(root, text="FIGMA: ГЛУБОКИЙ БИНАРНЫЙ СКАН", bg="#8533ff", command=self.run_figma_local, **btn_params).pack(pady=5)
        
        # Фильтры
        tk.Frame(root, height=1, bg="#333333").pack(fill="x", padx=50, pady=25)
        tk.Label(root, text="БЫСТРЫЙ ЭКСПОРТ ИЗ PSD:", fg="gray", bg="#1a1a1a").pack()
        
        filter_frame = tk.Frame(root, bg="#1a1a1a")
        filter_frame.pack(pady=10)
        tk.Button(filter_frame, text="ТОЛЬКО PNG", bg="#333", command=lambda: self.run_psd(only="png"), font=("Arial", 9), width=18).grid(row=0, column=0, padx=5)
        tk.Button(filter_frame, text="ТОЛЬКО JPG", bg="#333", command=lambda: self.run_psd(only="jpg"), font=("Arial", 9), width=18).grid(row=0, column=1, padx=5)

    def clean(self, name):
        return "".join(c for c in name if c.isalnum() or c in (' ', '_', '-')).strip()

    # 1. PSD Логика (Ассеты + CSS + Названия шрифтов)
    def run_psd(self, only=None):
        path = filedialog.askopenfilename(filetypes=[("Photoshop", "*.psd")])
        if not path: return
        out = os.path.join(os.path.dirname(path), f"ASSETS_PSD_{self.clean(os.path.basename(path))}")
        os.makedirs(out, exist_ok=True)

        try:
            psd = PSDImage.open(path)
            font_list = set()

            with open(os.path.join(out, "styles_and_fonts.css"), "w", encoding="utf-8") as f:
                for layer in psd.descendants():
                    if layer.kind == 'type':
                        # Извлечение названия шрифта для поиска
                        try:
                            fname = layer.engine_dict['StyleRun']['RunArray'][0]['StyleSheet']['Style']['FontCaps'] 
                            # Упрощенное получение имени из ресурсов
                            font_list.add(str(layer.resource_dict.get('FontName', 'Unknown Font')))
                        except: pass
                        f.write(f".{self.clean(layer.name)} {{ font-size: {layer.size}px; font-family: '{layer.resource_dict.get('FontName')}'; }}\n")

            # Сохранение шрифтового отчета
            if font_list:
                with open(os.path.join(out, "fonts_needed.txt"), "w") as f:
                    f.write("\n".join(font_list))

            # Экспорт графики
            for layer in psd.descendants():
                if layer.size == (0, 0) or layer.is_group(): continue
                ext = only if only else "png"
                img = layer.topil() or layer.composite()
                
                fname = f"{self.clean(layer.name)}_{layer.layer_id}.{ext}"
                if ext == "jpg":
                    if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                    img.save(os.path.join(out, fname), "JPEG", quality=95)
                else:
                    img.save(os.path.join(out, fname), "PNG", compress_level=0)

            messagebox.showinfo("PSD", "Готово! Стили и ассеты извлечены.")
        except Exception as e: messagebox.showerror("Error", str(e))

    # 2. PDF Логика (SVG + Бинарные Шрифты)
    def run_pdf(self):
        path = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if not path: return
        out = os.path.join(os.path.dirname(path), f"ASSETS_PDF_{self.clean(os.path.basename(path))}")
        os.makedirs(out, exist_ok=True)
        os.makedirs(os.path.join(out, "fonts"), exist_ok=True)

        try:
            doc = fitz.open(path)
            f_count = 0
            for i, page in enumerate(doc):
                # SVG страницы
                with open(os.path.join(out, f"page_{i+1}.svg"), "w", encoding="utf-8") as f:
                    f.write(page.get_svg_image())
                
                # Извлечение встроенных шрифтов (TTF/OTF/CFF)
                for font in page.get_fonts():
                    xref = font[0]
                    try:
                        f_name, f_ext, _, _, f_data = doc.extract_font(xref)
                        if f_data:
                            with open(os.path.join(out, "fonts", f"{f_name}.{f_ext}"), "wb") as f_font:
                                f_font.write(f_data)
                            f_count += 1
                    except: pass
            doc.close()
            messagebox.showinfo("PDF", f"SVG и {f_count} шрифтов извлечены.")
        except Exception as e: messagebox.showerror("Error", str(e))

    # 3. FIGMA Логика (Бинарный скан ресурсов)
    def run_figma_local(self):
        path = filedialog.askopenfilename(filetypes=[("Figma", "*.fig")])
        if not path: return
        out = os.path.join(os.path.dirname(path), f"ASSETS_FIG_{self.clean(os.path.basename(path))}")
        os.makedirs(out, exist_ok=True)

        try:
            with open(path, "rb") as f:
                data = f.read()

            img_count = 0
            for ext, pat in {"png": rb"\x89PNG\r\n\x1a\n.*?IEND\xaeB`\x82", "jpg": rb"\xff\xd8\xff.*?\xff\xd9"}.items():
                for m in re.finditer(pat, data, re.DOTALL):
                    with open(os.path.join(out, f"asset_{img_count}.{ext}"), "wb") as f_img:
                        f_img.write(m.group())
                    img_count += 1
            
            messagebox.showinfo("Figma", f"Извлечено оригинальных изображений: {img_count}")
        except Exception as e: messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = DesignExporter(root)
    root.mainloop()
