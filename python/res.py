import os
import re
import zipfile
import shutil
import base64
import argparse
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image
import fitz  # PyMuPDF

class UltimateDeepUnpacker:
    def __init__(self, file_path, template_name="Default"):
        self.file_path = os.path.abspath(file_path)
        self.output_dir = os.path.join(os.getcwd(), "Export", template_name)
        self.assets_dir = os.path.join(self.output_dir, "Resources")
        # Сигнатуры для глубокого бинарного поиска (Magic Bytes)
        self.sigs = {
            'png': (rb'\x89PNG\r\n\x1a\n', rb'\x49\x45\x4e\x44\xae\x42\x60\x82'),
            'jpg': (rb'\xff\xd8\xff', rb'\xff\xd9'),
            'pdf': (rb'%PDF-', rb'%%EOF'),
            'svg': (rb'<svg', rb'</svg>'),
            'xml': (rb'<\?xml', rb'>'),
            'zip': (rb'\x50\x4b\x03\x04', rb'\x50\x4b\x05\x06')
        }
        self._prepare_env()

    def _prepare_env(self):
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
        os.makedirs(self.assets_dir, exist_ok=True)

    def run(self):
        ext = os.path.splitext(self.file_path).lower()
        print(f"[*] Deep Unpacking: {self.file_path}")
        
        # 1. Структурный анализ по форматам
        if ext == '.fig': self._process_fig()
        elif ext == '.pdf': self._process_pdf()
        elif ext == '.svg': self._process_svg()
        elif ext in ['.jpg', '.jpeg', '.png']: self._process_raster()
        
        # 2. Универсальный бинарный карвинг (поиск скрытых вложений во всём)
        self._carve_binary(self.file_path)
        return True

    def _process_fig(self):
        temp_dir = os.path.join(self.output_dir, "_tmp")
        with zipfile.ZipFile(self.file_path, 'r') as z:
            z.extractall(temp_dir)
        for root, _, files in os.walk(temp_dir):
            for f in files:
                p = os.path.join(root, f)
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.svg')):
                    shutil.copy2(p, os.path.join(self.assets_dir, f"fig_asset_{f}"))
                self._carve_binary(p) # Сканируем бинарный canvas.fig
        shutil.rmtree(temp_dir)

    def _process_pdf(self):
        doc = fitz.open(self.file_path)
        for i, page in enumerate(doc):
            # Векторный слепок страницы
            with open(os.path.join(self.assets_dir, f"page_{i+1}.svg"), "w", encoding="utf-8") as f:
                f.write(page.get_svg_image())
            # Оригинальные изображения объектов
            for img in page.get_images(full=True):
                base = doc.extract_image(img)
                with open(os.path.join(self.assets_dir, f"p{i+1}_raw.{base['ext']}"), "wb") as f:
                    f.write(base["image"])
        doc.close()

    def _process_svg(self):
        shutil.copy2(self.file_path, os.path.join(self.output_dir, "vector_source.svg"))
        with open(self.file_path, "r", encoding="utf-8", errors='ignore') as f:
            data = f.read()
            # Извлекаем встроенный Base64 растр
            b64_found = re.findall(r'data:image/[^;]+;base64,([^"]+)', data)
            for i, b in enumerate(b64_found):
                with open(os.path.join(self.assets_dir, f"svg_embedded_{i}.png"), "wb") as out:
                    out.write(base64.b64decode(b))

    def _process_raster(self):
        img = Image.open(self.file_path)
        img.save(os.path.join(self.assets_dir, "original_flat.png"))
        # Если есть метаданные (EXIF/XMP), они будут найдены карвингом как XML

    def _carve_binary(self, f_path):
        """Поиск скрытых файлов внутри байтового потока"""
        with open(f_path, "rb") as f:
            data = f.read()
        for fmt, (start, end) in self.sigs.items():
            for i, match in enumerate(re.finditer(start, data)):
                s_pos = match.start()
                if end:
                    e_match = re.search(end, data[s_pos:])
                    if e_match:
                        e_pos = s_pos + e_match.end()
                        self._save(data[s_pos:e_pos], fmt, f_path, i)

    def _save(self, data, fmt, src, idx):
        fname = f"deep_{idx}_{os.path.basename(src)}.{fmt}"
        # Исключаем сохранение самого себя (если размер совпадает)
        if len(data) != os.path.getsize(self.file_path):
            with open(os.path.join(self.assets_dir, fname), "wb") as f:
                f.write(data)

def run_gui():
    root = tk.Tk()
    root.title("Universal Deep Unpacker (FIG, PDF, PNG, JPG, SVG)")
    def start():
        f = filedialog.askopenfilename()
        if f:
            t = os.path.basename(f).replace('.', '_')
            if UltimateDeepUnpacker(f, t).run():
                messagebox.showinfo("Готово", f"Папка Export/{t} заполнена ресурсами.")
    tk.Button(root, text="ВЫБРАТЬ ФАЙЛ", command=start, width=30, height=3, bg="#2980b9", fg="white").pack(padx=50, pady=40)
    root.mainloop()

if __name__ == "__main__":
    run_gui()
