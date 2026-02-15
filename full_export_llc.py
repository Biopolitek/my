import os
import sys
import zipfile
import warnings
import io
import multiprocessing
from pathlib import Path
from PIL import Image
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed

# Настройки графики
warnings.simplefilter('ignore', Image.DecompressionBombWarning)
Image.MAX_IMAGE_PIXELS = None 

def generate_css(layers_data, output_dir, file_prefix):
    css_path = os.path.join(output_dir, f"{file_prefix}_styles.css")
    with open(css_path, 'w', encoding='utf-8') as f:
        f.write(f"/* Styles for {file_prefix} */\n")
        for layer in layers_data:
            name = "".join(e for e in layer['name'].replace(" ", "-").lower() if e.isalnum() or e == "-")
            f.write(f".{name}_{layer['id']} {{\n")
            f.write(f"  position: absolute;\n  width: {layer['width']}px; height: {layer['height']}px;\n")
            f.write(f"  left: {layer['left']}px; top: {layer['top']}px;\n")
            f.write(f"  opacity: {layer['opacity']}; z-index: {layer['id']};\n}}\n\n")
    print(f"🎨 CSS создан: {css_path}")

def process_pdf_worker(args):
    path, page_num, out_dir, file_stem = args
    import fitz
    try:
        doc = fitz.open(path)
        page = doc.load_page(page_num)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) # High Quality
        pix.save(os.path.join(out_dir, f"{file_stem}_p{page_num+1}.png"))
        svg_data = page.get_svg_image()
        with open(os.path.join(out_dir, f"{file_stem}_p{page_num+1}.svg"), "w", encoding="utf-8") as f:
            f.write(svg_data)
        doc.close()
        return True
    except KeyboardInterrupt: return False
    except: return False

def process_pdf(path, out_dir):
    import fitz
    file_stem = Path(path).stem
    with fitz.open(path) as doc: num_pages = len(doc)
    tasks = [(path, i, out_dir, file_stem) for i in range(num_pages)]
    
    # ProcessPoolExecutor для максимальной скорости PDF (обход GIL)
    with ProcessPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
        futures = [executor.submit(process_pdf_worker, t) for t in tasks]
        try:
            with tqdm(total=num_pages, desc="PDF High-Res Export") as pbar:
                for future in as_completed(futures):
                    future.result()
                    pbar.update(1)
        except KeyboardInterrupt:
            executor.shutdown(wait=False, cancel_futures=True)
            raise

def process_psd(path, out_dir):
    from psd_tools import PSDImage
    psd = PSDImage.open(path)
    file_stem = Path(path).stem
    layers_metadata = []
    layers = [l for l in psd.descendants() if hasattr(l, 'topil') and l.size != (0, 0) and l.visible]
    
    with ThreadPoolExecutor() as executor:
        futures = {}
        for i, layer in enumerate(layers):
            try:
                img = layer.topil()
                if img:
                    fname = f"{file_stem}_layer_{i}.png"
                    fut = executor.submit(img.save, os.path.join(out_dir, fname), "PNG")
                    futures[fut] = i
                    layers_metadata.append({
                        "id": i, "name": layer.name or "layer",
                        "width": layer.width, "height": layer.height,
                        "left": layer.left, "top": layer.top,
                        "opacity": round(layer.opacity / 255, 2)
                    })
            except: continue
        
        try:
            for _ in tqdm(as_completed(futures), total=len(futures), desc="PSD Export"): pass
        except KeyboardInterrupt:
            executor.shutdown(wait=False, cancel_futures=True)
            raise
    generate_css(layers_metadata, out_dir, file_stem)

def process_fig_worker(args):
    zip_path, item, out_dir, file_stem = args
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            data = z.read(item)
            safe_name = item.split('/')[-1]
            base_out = os.path.join(out_dir, f"{file_stem}_{safe_name}")
            if data.startswith(b'<svg') or b'http://www.w3.org' in data[:500]:
                with open(base_out + ".svg", "wb") as f: f.write(data)
            else:
                img = Image.open(io.BytesIO(data))
                img.save(os.path.splitext(base_out)[0] + ".png", "PNG")
            return True
    except: return False

def process_fig(path, out_dir):
    file_stem = Path(path).stem
    with zipfile.ZipFile(path, 'r') as z:
        items = [f for f in z.namelist() if f.startswith('images/') and len(f) > 7]
    tasks = [(path, item, out_dir, file_stem) for item in items]
    
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(process_fig_worker, t) for t in tasks]
        try:
            for _ in tqdm(as_completed(futures), total=len(tasks), desc="FIG Export"): pass
        except KeyboardInterrupt:
            executor.shutdown(wait=False, cancel_futures=True)
            raise

def main():
    if len(sys.argv) < 2: return
    p = sys.argv[1]
    ext = Path(p).suffix.lower()
    out = "exports"
    os.makedirs(out, exist_ok=True)

    try:
        if ext == '.psd': process_psd(p, out)
        elif ext == '.pdf': process_pdf(p, out)
        elif ext == '.fig': process_fig(p, out)
        print(f"\n✅ Завершено успешно.")
    except KeyboardInterrupt:
        print(f"\n\n⚠️ Процесс прерван пользователем. Остановка...")
        sys.exit(1)

if __name__ == "__main__":
    multiprocessing.freeze_support() # Критично для EXE в 2026 году
    main()