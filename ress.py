import os
import sys
import json
import zipfile
import shutil
import hashlib
import base64
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk

# Библиотеки форматов
import fitz  # PyMuPDF
from psd_tools import PSDImage
from PIL import Image
import matplotlib.font_manager as fm

class FinalUltimateExtractor:
    def __init__(self, input_file, output_root="projects_export"):
        # Исправлено: принудительное приведение к строке для Path
        self.input_file = Path(str(input_file))
        self.proj_dir = Path(output_root) / self.input_file.stem
        self.assets_dir = self.proj_dir / "assets"
        self.fonts_dir = self.proj_dir / "fonts"
        self.map_data = {
            "metadata": {"source": self.input_file.name, "scale": 1.0},
            "pages": []
        }
        self.asset_hashes = {}
        self.css_rules = [
            "body { margin: 0; background: #1a1a1a; font-family: sans-serif; }",
            ".page-canvas { position: relative; background: #fff; margin: 50px auto; overflow: hidden; box-shadow: 0 0 50px #000; }",
            ".element { position: absolute; background-size: contain; background-repeat: no-repeat; }"
        ]
        
        for d in [self.assets_dir, self.fonts_dir]: d.mkdir(parents=True, exist_ok=True)

    def get_magic_ext(self, data):
        sigs = {b'\x89PNG': 'png', b'\xff\xd8': 'jpg', b'OTTO': 'otf', b'\x00\x01\x00\x00': 'ttf', b'%PDF': 'pdf'}
        for sig, ext in sigs.items():
            if data.startswith(sig): return ext
        return None

    def collect_system_font(self, font_name):
        if not font_name: return "sans-serif"
        try:
            prop = fm.FontProperties(family=font_name)
            path = fm.findfont(prop)
            if path and os.path.exists(path):
                fname = os.path.basename(path)
                shutil.copy(path, self.fonts_dir)
                rule = f"@font-face {{ font-family: '{font_name}'; src: url('fonts/{fname}'); }}"
                if rule not in self.css_rules: self.css_rules.append(rule)
                return font_name
        except: pass
        return "sans-serif"

    def save_resource(self, pil_img, prefix="obj"):
        if pil_img.mode != 'RGBA': pil_img = pil_img.convert('RGBA')
        h = hashlib.md5(pil_img.tobytes()).hexdigest()
        if h in self.asset_hashes: return self.asset_hashes[h]
        
        fname = f"{prefix}_{len(self.asset_hashes)}.png"
        pil_img.save(self.assets_dir / fname, "PNG")
        self.asset_hashes[h] = f"assets/{fname}"
        return f"assets/{fname}"

    def process_psd(self):
        psd = PSDImage.open(self.input_file)
        artboards = [l for l in psd if l.is_group() and getattr(l, 'kind', '') == 'artboard']
        targets = artboards if artboards else [psd]

        for p_idx, target in enumerate(targets):
            scale = 2.0 if target.width > 2000 else 1.0
            page = {"name": getattr(target, 'name', f"Page_{p_idx}"), "w": target.width/scale, "h": target.height/scale, "elements": []}
            
            for i, layer in enumerate(target.descendants()):
                if layer.is_group() or layer.width == 0: continue
                
                rect = {"x": layer.left/scale, "y": layer.top/scale, "w": layer.width/scale, "h": layer.height/scale}
                f_family = "sans-serif"
                if hasattr(layer, 'text') and layer.text:
                    try:
                        raw_f = layer.resource_dict.get('FontSet', [{}]).get('Name', 'Arial')
                        f_family = self.collect_system_font(raw_f)
                    except: pass

                try:
                    asset_path = self.save_resource(layer.composite(), "psd")
                    page["elements"].append({
                        "id": i, "name": layer.name, "file": asset_path, "rect": rect, "z": i * 5, 
                        "font": f_family, 
                        "constraints": "center" if abs(layer.left + layer.width/2 - target.width/2) < 20 else "left"
                    })
                except: continue
            self.map_data["pages"].append(page)

    def process_pdf(self):
        doc = fitz.open(self.input_file)
        for i, page in enumerate(doc):
            svg_name = f"vector_page_{i}.svg"
            with open(self.assets_dir / svg_name, "w", encoding="utf-8") as f:
                f.write(page.get_svgimage())
            
            for f_info in page.get_fonts():
                try:
                    f_data = doc.extract_font(f_info)
                    if f_data:
                        f_ext = f_data[1]
                        with open(self.fonts_dir / f"font_{f_info[0]}.{f_ext}", "wb") as f: f.write(f_data[3])
                except: pass
            self.map_data["pages"].append({"name": f"PDF_P{i}", "w": page.rect.width, "h": page.rect.height, "svg": f"assets/{svg_name}", "elements": []})

    def process_fig(self):
        with zipfile.ZipFile(self.input_file, 'r') as z:
            for n in z.namelist():
                data = z.read(n)
                ext = self.get_magic_ext(data)
                if ext:
                    dest = self.fonts_dir if ext in ['otf', 'ttf'] else self.assets_dir
                    with open(dest / f"{Path(n).name}", "wb") as f: f.write(data)
        self.map_data["pages"].append({"name": "Figma_Canvas", "elements": [], "w": 1920, "h": 1080})

    def finalize_project(self):
        html = ["<!DOCTYPE html><html><head><meta charset='utf-8'><link rel='stylesheet' href='style.css'></head><body>"]
        for pg in self.map_data["pages"]:
            html.append(f"<div class='page-canvas' style='width:{pg.get('w', 1920)}px; height:{pg.get('h', 1080)}px;'>")
            if pg.get("svg"):
                html.append(f"<img src='{pg['svg']}' style='width:100%; height:100%;'>")
            else:
                for el in pg.get("elements", []):
                    r = el['rect']
                    st = f"left:{r['x']}px; top:{r['y']}px; width:{r['w']}px; height:{r['h']}px; z-index:{el['z']}; background-image:url({el['file']});"
                    if el.get('font'): st += f" font-family:'{el['font']}';"
                    html.append(f"<div class='element' style='{st}'></div>")
            html.append("</div>")
        html.append("</body></html>")
        
        with open(self.proj_dir / "index.html", "w", encoding="utf-8") as f: f.write("\n".join(html))
        with open(self.proj_dir / "map.json", "w", encoding="utf-8") as f: json.dump(self.map_data, f, indent=4, ensure_ascii=False)
        with open(self.proj_dir / "style.css", "w", encoding="utf-8") as f: f.write("\n".join(list(set(self.css_rules))))

    def run(self):
        ext = self.input_file.suffix.lower()
        if ext == '.psd': self.process_psd()
        elif ext == '.pdf': self.process_pdf()
        elif ext in ['.fig', '.zip']: self.process_fig()
        self.finalize_project()
        try: os.startfile(self.proj_dir)
        except: pass

class UI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("TemplateMaster Ultra v2.2")
        self.geometry("500x350")
        ctk.set_appearance_mode("dark")
        ctk.CTkLabel(self, text="UNIVERSAL TEMPLATE MASTER", font=("Arial", 20, "bold")).pack(pady=30)
        self.btn = ctk.CTkButton(self, text="ВЫБРАТЬ ФАЙЛ", height=60, width=280, command=self.start)
        self.btn.pack(pady=20)

    def start(self):
        f = filedialog.askopenfilename()
        if f:
            self.btn.configure(state="disabled", text="ЭКСПОРТ...")
            try:
                engine = FinalUltimateExtractor(f)
                engine.run()
                messagebox.showinfo("OK", "Экспорт завершен!")
            except Exception as e:
                messagebox.showerror("Error", str(e))
            finally:
                self.btn.configure(state="normal", text="ВЫБРАТЬ ФАЙЛ")

if __name__ == "__main__":
    # Исправленная логика CLI
    if len(sys.argv) > 1:
        # Извлекаем путь как строку из списка аргументов
        input_param = sys.argv[1]
        if os.path.exists(input_param):
            engine = FinalUltimateExtractor(input_param)
            engine.run()
        else:
            print(f"File not found: {input_param}")
    else:
        app = UI()
        app.mainloop()
