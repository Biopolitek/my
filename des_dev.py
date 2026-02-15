import os, sys, json, threading, zipfile, shutil, hashlib
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from psd_tools import PSDImage
import fitz  # PyMuPDF
from PIL import Image
import matplotlib.font_manager as fm

class PixelPerfect_Fullstack_Engine:
    def __init__(self, progress_callback):
        self.output_dir = Path("web_project")
        self.assets_dir = self.output_dir / "assets"
        self.hashes = {}
        self.manifest = {"canvas": {"w": 0, "h": 0}, "components": [], "fonts": {}}
        self.update_progress = progress_callback

    def setup_project(self):
        if self.output_dir.exists(): shutil.rmtree(self.output_dir)
        for d in ["images", "fonts", "css"]:
            (self.assets_dir / d).mkdir(parents=True, exist_ok=True)

    def save_layer_img(self, img, i, prefix="res"):
        if img.mode in ('CMYK', 'LAB'): img = img.convert('RGB')
        if img.mode == 'P': img = img.convert('RGBA')
        f_hash = hashlib.md5(img.tobytes()).hexdigest()
        if f_hash in self.hashes: return self.hashes[f_hash]
        name = f"{prefix}_{i}_{f_hash[:6]}.webp"
        path = self.assets_dir / "images" / name
        img.save(path, "WEBP", lossless=True)
        ref = f"assets/images/{name}"
        self.hashes[f_hash] = ref
        return ref

    def collect_font(self, font_name):
        try:
            f_path = fm.findfont(fm.FontProperties(family=font_name))
            if f_path and "DejaVu" not in f_path:
                target = self.assets_dir / "fonts" / Path(f_path).name
                if not target.exists(): shutil.copy(f_path, target)
                self.manifest["fonts"][font_name] = f"assets/fonts/{Path(f_path).name}"
        except: pass

    def process_files(self, paths):
        self.setup_project()
        total_tasks = len(paths)
        
        for file_idx, path in enumerate(paths):
            ext = Path(path).suffix.lower()
            if ext == '.psd':
                psd = PSDImage.open(path)
                self.manifest["canvas"]["w"] = max(self.manifest["canvas"]["w"], psd.width)
                self.manifest["canvas"]["h"] = max(self.manifest["canvas"]["h"], psd.height)
                layers = list(psd.descendants())
                for i, layer in enumerate(layers):
                    if not layer.is_group() and layer.width > 0:
                        img = layer.composite() if hasattr(layer, 'composite') else layer.topil()
                        if img:
                            src = self.save_layer_img(img, i, "psd")
                            comp = {"id": i, "type": "raster" if layer.kind != 'type' else "text",
                                    "src": src, "x": layer.left, "y": layer.top, "w": layer.width, "h": layer.height,
                                    "z": i, "opacity": round(layer.opacity/255, 2)}
                            if layer.kind == 'type':
                                comp.update({"text": layer.text, "font": getattr(layer, 'font_name', 'Arial'), 
                                             "size": getattr(layer, 'size', 16), "color": str(getattr(layer, 'color', '#000'))})
                                self.collect_font(comp["font"])
                            self.manifest["components"].append(comp)
                    # Прогресс внутри файла
                    step = (file_idx / total_tasks) + ((i / len(layers)) / total_tasks)
                    self.update_progress(step)

            elif ext == '.pdf':
                doc = fitz.open(path)
                y_off = 0
                for i, page in enumerate(doc):
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    src = self.save_layer_img(img, i, "pdf")
                    self.manifest["components"].append({
                        "id": f"pdf_{i}", "type": "page", "src": src, "x": 0, "y": y_off, "w": pix.width, "h": pix.height, "z": i
                    })
                    y_off += pix.height
                    self.update_progress((file_idx + (i+1)/len(doc)) / total_tasks)
                self.manifest["canvas"]["h"] = max(self.manifest["canvas"]["h"], y_off)

        self.build_final()
        self.update_progress(1.0)

    def build_final(self):
        css = ["body { background: #121212; margin: 0; }",
               ".canvas { position: relative; background: #fff; margin: 0 auto; overflow: hidden; }",
               ".layer { position: absolute; display: block; }",
               ".text { position: absolute; white-space: pre-wrap; display: flex; align-items: center; }"]
        for f, p in self.manifest["fonts"].items():
            css.append(f"@font-face {{ font-family: '{f}'; src: url('../fonts/{Path(p).name}'); }}")

        html = ["<!DOCTYPE html><html><head><link rel='stylesheet' href='assets/css/style.css'></head><body>",
                f"<div class='canvas' style='width:{self.manifest['canvas']['w']}px; height:{self.manifest['canvas']['h']}px;'>"]
        for c in sorted(self.manifest["components"], key=lambda x: x["z"]):
            style = f"left:{c['x']}px; top:{c['y']}px; width:{c['w']}px; height:{c['h']}px; z-index:{c['z']}; opacity:{c.get('opacity',1)};"
            if c["type"] == "text":
                style += f" font-family:'{c.get('font')}'; font-size:{c.get('size')}px; color:{c.get('color')};"
                html.append(f"<div class='text' style='{style}'>{c.get('text','')}</div>")
            else:
                html.append(f"<img src='{c['src']}' class='layer' style='{style}'>")
        html.append("</div></body></html>")
        
        with open(self.output_dir / "index.html", "w", encoding="utf-8") as f: f.write("".join(html))
        with open(self.assets_dir / "css" / "style.css", "w", encoding="utf-8") as f: f.write("\n".join(css))
        with open(self.output_dir / "site_map.json", "w", encoding="utf-8") as f: json.dump(self.manifest, f, indent=4)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AssetEngine 2026")
        self.geometry("500x300")
        self.engine = PixelPerfect_Fullstack_Engine(self.set_progress)
        self.files = []
        
        ctk.CTkLabel(self, text="PIXEL PERFECT BUILDER", font=("Arial", 20, "bold")).pack(pady=20)
        self.btn_sel = ctk.CTkButton(self, text="ВЫБРАТЬ ШАБЛОНЫ", command=self.select)
        self.btn_sel.pack(pady=10)
        self.progress = ctk.CTkProgressBar(self, width=400)
        self.progress.pack(pady=20)
        self.progress.set(0)
        self.btn_go = ctk.CTkButton(self, text="СБОРКА", command=self.run, state="disabled", fg_color="green")
        self.btn_go.pack(pady=10)

    def set_progress(self, val):
        self.progress.set(val)
        self.update_idletasks()

    def select(self):
        self.files = filedialog.askopenfilenames(filetypes=[("Design", "*.psd *.pdf *.fig *.png")])
        if self.files: self.btn_go.configure(state="normal")

    def run(self):
        self.btn_go.configure(state="disabled")
        threading.Thread(target=lambda: [self.engine.process_files(self.files), messagebox.showinfo("Ready", "Сайт готов!")], daemon=True).start()

if __name__ == "__main__":
    App().mainloop()