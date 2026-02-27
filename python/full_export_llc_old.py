import os
import sys
import io
import json
import zipfile
import warnings
from pathlib import Path
from PIL import Image
from tqdm import tqdm

# Настройки для работы с графикой
warnings.simplefilter('ignore', Image.DecompressionBombWarning)
Image.MAX_IMAGE_PIXELS = None 

def generate_css(layers_data, output_dir, file_prefix):
    """Генерация CSS для PSD"""
    css_path = os.path.join(output_dir, f"{file_prefix}_styles.css")
    with open(css_path, 'w', encoding='utf-8') as f:
        f.write(f"/* Styles for {file_prefix} */\n")
        for layer in layers_data:
            name = "".join(e for e in layer['name'].replace(" ", "-").lower() if e.isalnum() or e == "-")
            f.write(f".{name}_{layer['id']} {{\n")
            f.write(f"  position: absolute;\n  width: {layer['width']}px;\n  height: {layer['height']}px;\n")
            f.write(f"  left: {layer['left']}px;\n  top: {layer['top']}px;\n")
            f.write(f"  opacity: {layer['opacity']};\n}}\n\n")
    print(f"🎨 CSS создан: {css_path}")

def process_psd(path, out_dir):
    """PSD -> PNG + CSS"""
    from psd_tools import PSDImage
    psd = PSDImage.open(path)
    file_stem = Path(path).stem
    layers_metadata = []
    
    all_layers = list(psd.descendants())
    for i, layer in enumerate(tqdm(all_layers, desc="PSD to PNG/CSS")):
        if hasattr(layer, 'topil') and layer.size != (0, 0):
            try:
                img = layer.topil()
                if img:
                    fname = f"{file_stem}_layer_{i}.png"
                    img.save(os.path.join(out_dir, fname))
                    layers_metadata.append({
                        "id": i, "name": layer.name or "layer",
                        "width": layer.width, "height": layer.height,
                        "left": layer.left, "top": layer.top,
                        "opacity": round(layer.opacity / 255, 2)
                    })
            except: continue
    generate_css(layers_metadata, out_dir, file_stem)

def process_pdf(path, out_dir):
    """PDF -> PNG + SVG"""
    import fitz  # PyMuPDF
    doc = fitz.open(path)
    file_stem = Path(path).stem
    
    for page_num in tqdm(range(len(doc)), desc="PDF to PNG/SVG"):
        page = doc.load_page(page_num)
        
        # 1. Сохраняем PNG (растр)
        pix = page.get_pixmap(dpi=150)
        pix.save(os.path.join(out_dir, f"{file_stem}_p{page_num+1}.png"))
        
        # 2. Сохраняем SVG (вектор)
        svg_data = page.get_svg_image()
        with open(os.path.join(out_dir, f"{file_stem}_p{page_num+1}.svg"), "w", encoding="utf-8") as f:
            f.write(svg_data)
    doc.close()
    print(f"📄 PDF обработан: PNG и SVG созданы.")

def process_fig(path, out_dir):
    """FIG -> PNG + SVG (Extract blobs)"""
    file_stem = Path(path).stem
    images_extracted = 0
    
    with zipfile.ZipFile(path, 'r') as z:
        # В .fig изображения лежат в папке images/
        items = [f for f in z.namelist() if f.startswith('images/')]
        
        for i, item in enumerate(tqdm(items, desc="FIG to PNG/SVG")):
            with z.open(item) as f:
                data = f.read()
                # Определяем расширение по сигнатуре
                ext = ".png"
                if data.startswith(b'\x89PNG'): ext = ".png"
                elif data.startswith(b'\xff\xd8'): ext = ".jpg"
                elif data.startswith(b'<svg') or b'http://www.w3.org' in data[:500]: ext = ".svg"
                
                out_name = f"{file_stem}_img_{i}{ext}"
                with open(os.path.join(out_dir, out_name), "wb") as out_f:
                    out_f.write(data)
                
                # Если это не SVG, создаем пустую векторную обертку (для структуры)
                if ext != ".svg":
                    svg_wrapper = f'<svg xmlns="http://www.w3.org"><image href="{out_name}" /></svg>'
                    with open(os.path.join(out_dir, f"{file_stem}_img_{i}.svg"), "w") as f_svg:
                        f_svg.write(svg_wrapper)
            images_extracted += 1
    print(f"💎 FIG обработан: извлечено {images_extracted} объектов.")

def main():
    if len(sys.argv) < 2:
        print("Использование: python script.py <файл>")
        return

    path = sys.argv[1]
    ext = Path(path).suffix.lower()
    out = "exports"
    os.makedirs(out, exist_ok=True)

    if ext == '.psd':
        process_psd(path, out)
    elif ext == '.pdf':
        process_pdf(path, out)
    elif ext == '.fig':
        process_fig(path, out)
    else:
        print(f"Формат {ext} не поддерживается.")

if __name__ == "__main__":
    main()