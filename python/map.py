import os
import io
import json
import re
import base64
import argparse
from datetime import datetime
import fitz  # PyMuPDF
from psd_tools import PSDImage
from PIL import Image

class UniversalParser:
    def __init__(self, output_dir="dist", embed_assets=False):
        self.output_dir = output_dir
        self.assets_dir = os.path.join(output_dir, "assets")
        self.embed_assets = embed_assets
        self.report = {"metadata": {"created_at": str(datetime.now())}, "pages": []}
        self.font_list = {}
        
        if not os.path.exists(self.assets_dir):
            os.makedirs(self.assets_dir)

    def _get_base64(self, image_bytes):
        return f"data:image/png;base64,{base64.b64encode(image_bytes).decode('utf-8')}"

    def _register_font(self, family, size, color):
        family = family or "Standard"
        key = f"{family}_{size}_{color}"
        if key not in self.font_list:
            self.font_list[key] = {"family": family, "size": round(float(size), 1), "color": color, "count": 0}
        self.font_list[key]["count"] += 1

    def add_element(self, page_id, name, x, y, w, h, z, extra=None):
        while len(self.report["pages"]) <= page_id:
            self.report["pages"].append({"page_index": len(self.report["pages"]), "size": {"w": 0, "h": 0}, "elements": []})
        
        if extra and extra.get("type") == "text":
            self._register_font(extra.get("font_family"), extra.get("font_size"), extra.get("color"))

        element = {
            "name": name or "Unnamed",
            "coords": {"x": round(x, 2), "y": round(y, 2)},
            "size": {"w": round(w, 2), "h": round(h, 2)},
            "z_index": z,
            "metadata": extra or {}
        }
        self.report["pages"][page_id]["elements"].append(element)

    def process_pdf(self, path):
        print(f"[*] Parsing PDF: {path}")
        doc = fitz.open(path)
        for p_idx, page in enumerate(doc):
            m_box = page.rect
            self.report["pages"].append({"page_index": p_idx, "size": {"w": m_box.width, "h": m_box.height}, "elements": []})
            
            # Текст (глубокий анализ spans)
            for block in page.get_text("dict")["blocks"]:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            self.add_element(p_idx, span["text"][:15], span["bbox"][0], span["bbox"][1],
                                            span["bbox"][2]-span["bbox"][0], span["bbox"][3]-span["bbox"][1], 0,
                                            {"type": "text", "font_family": span["font"], "font_size": span["size"], 
                                             "color": f"#{span['color']:06x}", "raw_content": span["text"]})
            
            # Изображения
            for img in page.get_images(full=True):
                xref = img[0]
                pix = doc.extract_image(xref)
                img_data = pix["image"]
                src = self._get_base64(img_data) if self.embed_assets else f"assets/img_{xref}.{pix['ext']}"
                
                if not self.embed_assets:
                    with open(os.path.join(self.assets_dir, f"img_{xref}.{pix['ext']}"), "wb") as f: f.write(img_data)
                
                # Ищем координаты картинки
                for info in page.get_image_info():
                    if info['xref'] == xref:
                        b = info['bbox']
                        self.add_element(p_idx, f"Image_{xref}", b[0], b[1], b[2]-b[0], b[3]-b[1], 1, {"type": "image", "src": src})

    def process_psd(self, path):
        print(f"[*] Parsing PSD: {path}")
        psd = PSDImage.open(path)
        self.report["pages"].append({"page_index": 0, "size": {"w": psd.width, "h": psd.height}, "elements": []})
        
        for i, layer in enumerate(psd.descendants()):
            if not layer.visible or layer.width == 0: continue
            extra = {"type": "pixel"}
            if layer.kind == 'type':
                extra = {"type": "text", "font_family": "PSD_Font", "font_size": 14, "color": "#000000", "raw_content": layer.text}
            elif layer.kind in ['pixel', 'smartobject']:
                img = layer.topil()
                if img:
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    img_data = buf.getvalue()
                    src = self._get_base64(img_data) if self.embed_assets else f"assets/layer_{i}.png"
                    if not self.embed_assets:
                        img.save(os.path.join(self.assets_dir, f"layer_{i}.png"))
                    extra = {"type": "image", "src": src}
            
            self.add_element(0, layer.name, layer.left, layer.top, layer.width, layer.height, i, extra)

    def save(self):
        # JSON Report
        with open(os.path.join(self.output_dir, "data.json"), "w", encoding="utf-8") as f:
            json.dump({"fonts": self.font_list, "pages": self.report["pages"]}, f, indent=2, ensure_all_ascii=False)
        
        # HTML Viewer
        html = ['<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{background:#2c2c2c;color:white;font-family:sans-serif;display:flex;flex-direction:column;align-items:center}.page{background:white;position:relative;margin:30px;box-shadow:0 0 20px #000}.el{position:absolute;overflow:hidden;outline:1px solid transparent}.el:hover{outline:1px solid #007bff;background:rgba(0,123,255,0.1)}img{width:100%;height:100%;object-fit:contain}</style></head><body>']
        for p in self.report["pages"]:
            html.append(f'<h2>Page {p["page_index"]} ({p["size"]["w"]}x{p["size"]["h"]})</h2>')
            html.append(f'<div class="page" style="width:{p["size"]["w"]}px; height:{p["size"]["h"]}px;">')
            for el in sorted(p["elements"], key=lambda x: x["z_index"]):
                m = el["metadata"]
                st = f"left:{el['coords']['x']}px;top:{el['coords']['y']}px;width:{el['size']['w']}px;height:{el['size']['h']}px;z-index:{el['z_index']};"
                if m.get("type") == "text":
                    st += f"font-size:{m.get('font_size')}px;color:{m.get('color')};"
                    html.append(f'<div class="el" style="{st}">{m.get("raw_content")}</div>')
                elif m.get("type") == "image":
                    html.append(f'<div class="el" style="{st}"><img src="{m.get("src")}"></div>')
            html.append('</div>')
        
        with open(os.path.join(self.output_dir, "index.html"), "w", encoding="utf-8") as f: f.write("\n".join(html + ["</body></html>"]))
        print(f"[+] Success! Check '{self.output_dir}' folder.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Universal Layout Parser")
    parser.add_argument("input", help="Path to PDF or PSD file")
    parser.add_argument("--output", default="dist", help="Output directory")
    parser.add_argument("--embed", action="store_true", help="Embed images as Base64 in JSON/HTML")
    args = parser.parse_args()

    worker = UniversalParser(args.output, args.embed)
    if args.input.lower().endswith(".pdf"): worker.process_pdf(args.input)
    elif args.input.lower().endswith(".psd"): worker.process_psd(args.input)
    worker.save()
