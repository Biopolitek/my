#!/usr/bin/env python3
"""
Grid-Safe Design to PNG Export Script
Saves multiple pages per PNG until size limit
Uses filename as prefix
"""

import os
import sys
import json
import zipfile
import argparse
import io
import gc
import warnings
from pathlib import Path
from PIL import Image, ImageDraw

# Disable PIL decompression bomb warnings
warnings.simplefilter('ignore', Image.DecompressionBombWarning)

# Set PIL limits to very high values
Image.MAX_IMAGE_PIXELS = None  # Disable limit
Image.MAX_IMAGE_BLOCKS = 1000000

def check_file_exists(file_path):
    """Check if file exists and get info"""
    if not os.path.exists(file_path):
        print(f"✗ File not found: {file_path}")
        return False
    
    file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
    print(f"✓ File found: {file_path} ({file_size:.1f}MB)")
    
    if file_size > 100:
        print("⚠️  Large file detected - using grid-safe mode")
    
    return True

def export_figma_to_png(figma_file, output_dir="exports", max_width=1920, max_height=1080):
    """Export Figma .fig file to PNG grid"""
    try:
        with zipfile.ZipFile(figma_file, 'r') as zip_file:
            # Extract all images
            image_files = [f for f in zip_file.namelist() if f.startswith('images/')]
            
            if not image_files:
                print("✗ No images found in .fig file")
                return False
            
            print(f"📤 Found {len(image_files)} images in Figma file")
            return create_png_grid_from_images(zip_file, image_files, output_dir, max_width, max_height, Path(figma_file).stem)
            
    except Exception as e:
        print(f"✗ Error processing Figma file: {e}")
        return False

def export_psd_to_png(psd_file, output_dir="exports", max_width=1920, max_height=1080):
    """Export PSD file to PNG grid"""
    try:
        from psd_tools import PSDImage
        psd = PSDImage.open(psd_file)
        
        # Extract all layers as images
        layer_images = []
        
        # Try to get composite image first
        try:
            composite_img = psd.topil()
            if composite_img:
                layer_images.append(composite_img)
                print(f"📤 Using composite image from PSD")
        except:
            pass
        
        # If no composite, try layers
        if not layer_images:
            for layer in psd:
                try:
                    if hasattr(layer, 'is_visible') and layer.is_visible():
                        layer_img = layer.topil()
                        if layer_img:
                            layer_images.append(layer_img)
                except:
                    continue
        
        if not layer_images:
            print("✗ No extractable images found in PSD file")
            print("💡 Try saving PSD as composite image in Photoshop first")
            return False
        
        print(f"📤 Found {len(layer_images)} extractable images in PSD file")
        return create_png_grid_from_pil_images(layer_images, output_dir, max_width, max_height, Path(psd_file).stem)
        
    except ImportError:
        print("✗ psd-tools not installed. Install with:")
        print("pip install psd-tools")
        return False
    except Exception as e:
        print(f"✗ Error processing PSD file: {e}")
        return False

def export_pdf_to_png(pdf_file, output_dir="exports", max_width=1920, max_height=1080):
    """Export PDF file to PNG grid - grid-safe mode"""
    try:
        import fitz  # PyMuPDF
        pdf_document = fitz.open(pdf_file)
        
        total_pages = len(pdf_document)
        print(f"📤 Found {total_pages} pages in PDF file")
        
        # Process one page at a time for maximum safety
        all_images = []
        
        for page_num in range(min(total_pages, 50)):  # Limit to 50 pages
            try:
                print(f"📄 Processing page {page_num + 1}...")
                
                page = pdf_document.load_page(page_num)
                
                # Use very low resolution for memory safety
                scale = 1.0  # Reduced to 1.0 for safety
                
                try:
                    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
                    
                    # Check if pixmap is too large
                    if pix.size > 50 * 1024 * 1024:  # 50MB limit per page
                        print(f"⚠️  Page {page_num + 1} too large, skipping")
                        continue
                    
                    img_data = pix.tobytes("png")
                    
                    # Quick size check before opening
                    if len(img_data) > 20 * 1024 * 1024:  # 20MB limit
                        print(f"⚠️  Page {page_num + 1} image too large, skipping")
                        continue
                    
                    img = Image.open(io.BytesIO(img_data))
                    
                    # Aggressive resizing
                    max_dimension = 1500  # Reduced from 2000
                    if img.width > max_dimension or img.height > max_dimension:
                        img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                        print(f"🔧 Resized page {page_num + 1} to {img.width}x{img.height}")
                    
                    all_images.append(img)
                    
                    # Clear memory immediately
                    del pix, img_data
                    gc.collect()
                    
                except Exception as e:
                    if "malloc" in str(e) or "memory" in str(e).lower():
                        print(f"⚠️  Memory error on page {page_num + 1}, skipping")
                    else:
                        print(f"⚠️  Error on page {page_num + 1}: {e}")
                    continue
                
            except Exception as e:
                print(f"⚠️  Skipping page {page_num + 1}: {e}")
                continue
        
        if not all_images:
            print("✗ No pages could be processed from PDF file")
            return False
        
        print(f"📤 Processed {len(all_images)} pages successfully")
        return create_png_grid_from_pil_images(all_images, output_dir, max_width, max_height, Path(pdf_file).stem)
        
    except ImportError:
        print("✗ PyMuPDF not installed. Install with:")
        print("pip install PyMuPDF")
        return False
    except Exception as e:
        print(f"✗ Error processing PDF file: {e}")
        return False
    finally:
        # Ensure PDF document is closed
        try:
            if 'pdf_document' in locals():
                pdf_document.close()
        except:
            pass

def create_png_grid_from_images(zip_file, image_files, output_dir, max_width, max_height, file_prefix):
    """Create PNG grid from images in zip file - grid-safe mode"""
    # Create grid layout with size checking
    grid_images = []
    current_row = []
    current_width = 0
    current_height = 0
    
    for img_file in image_files:
        try:
            with zip_file.open(img_file) as img_data:
                img_bytes = img_data.read()
                if len(img_bytes) > 0 and len(img_bytes) < 10 * 1024 * 1024:  # 10MB limit per image
                    img = Image.open(io.BytesIO(img_bytes))
                    
                    # Check if adding this image would exceed limits
                    new_width = current_width + img.width
                    new_height = max(current_height, img.height)
                    estimated_size = new_width * new_height * 4  # 4 bytes per pixel for RGBA
                    
                    # If adding would exceed limit, save current grid and start new
                    if estimated_size > 50 * 1024 * 1024:  # 50MB limit per grid
                        if current_row:
                            grid_images.append(current_row)
                            current_row = [img]
                            current_width = img.width
                            current_height = img.height
                        continue
                    
                    # Check if we need new row
                    if current_width + img.width > max_width:
                        if current_row:
                            grid_images.append(current_row)
                            current_row = []
                            current_width = 0
                            current_height = 0
                    
                    current_row.append(img)
                    current_width += img.width
                    current_height = max(current_height, img.height)
                
        except Exception as e:
            print(f"⚠️  Skipping {img_file}: {e}")
    
    # Add last row
    if current_row:
        grid_images.append(current_row)
    
    return save_grid_images(grid_images, output_dir, file_prefix)

def create_png_grid_from_pil_images(pil_images, output_dir, max_width, max_height, file_prefix):
    """Create PNG grid from PIL images - grid-safe mode"""
    # Create grid layout with size checking
    grid_images = []
    current_row = []
    current_width = 0
    current_height = 0
    
    for img in pil_images:
        # Check if adding this image would exceed limits
        new_width = current_width + img.width
        new_height = max(current_height, img.height)
        estimated_size = new_width * new_height * 4  # 4 bytes per pixel for RGBA
        
        # If adding would exceed limit, save current grid and start new
        if estimated_size > 50 * 1024 * 1024:  # 50MB limit per grid
            if current_row:
                grid_images.append(current_row)
                current_row = [img]
                current_width = img.width
                current_height = img.height
            continue
        
        # Check if we need new row
        if current_width + img.width > max_width:
            if current_row:
                grid_images.append(current_row)
                current_row = []
                current_width = 0
                current_height = 0
        
        current_row.append(img)
        current_width += img.width
        current_height = max(current_height, img.height)
    
    # Add last row
    if current_row:
        grid_images.append(current_row)
    
    return save_grid_images(grid_images, output_dir, file_prefix)

def save_grid_images(grid_images, output_dir, file_prefix):
    """Save grid images to PNG files - grid-safe mode"""
    try:
        # Get existing files to avoid conflicts
        existing_files = {}
        if os.path.exists(output_dir):
            for f in os.listdir(output_dir):
                if f.endswith('.png'):
                    parts = f.replace('.png', '').split('_')
                    if len(parts) >= 2:
                        prefix = '_'.join(parts[:-1])
                        try:
                            num = int(parts[-1])
                            if prefix not in existing_files or num > existing_files[prefix]:
                                existing_files[prefix] = num
                        except:
                            continue
        
        # Starting number for this prefix
        start_num = existing_files.get(file_prefix, 0) + 1
        
        saved_count = 0
        for i, row in enumerate(grid_images):
            if not row:
                continue
            
            try:
                # Calculate grid dimensions
                row_width = sum(img.width for img in row)
                row_height = max(img.height for img in row)
                
                # Final size check
                estimated_size = row_width * row_height * 4
                if estimated_size > 50 * 1024 * 1024:  # 50MB limit
                    print(f"⚠️  Grid {i+1} too large ({estimated_size//1024//1024}MB), splitting...")
                    # Split into smaller grids
                    saved_count += save_split_grid(row, output_dir, file_prefix, start_num + saved_count)
                    continue
                
                # Create grid image
                grid_img = Image.new('RGBA', (row_width, row_height), (255, 255, 255, 0))
                
                # Paste images
                x_offset = 0
                for img in row:
                    try:
                        grid_img.paste(img, (x_offset, 0), img if img.mode == 'RGBA' else None)
                        x_offset += img.width
                    except Exception as e:
                        print(f"⚠️  Error pasting image in grid {i+1}: {e}")
                        continue
                
                # Save with maximum compression
                output_file = os.path.join(output_dir, f'{file_prefix}_{start_num + saved_count:03d}.png')
                grid_img.save(output_file, 'PNG', optimize=True, compress_level=9)
                print(f"✓ Saved: {output_file} ({row_width}x{row_height})")
                saved_count += 1
                
                # Clear memory immediately
                del grid_img
                gc.collect()
                
            except Exception as e:
                print(f"⚠️  Error saving grid {i+1}: {e}")
                continue
        
        print(f"\n🎉 Export completed! {saved_count} PNG files created")
        return True
        
    except Exception as e:
        print(f"✗ Error saving grid images: {e}")
        return False

def save_split_grid(row, output_dir, file_prefix, start_num):
    """Split a large grid into smaller ones"""
    saved_count = 0
    max_images_per_grid = 5  # Limit images per grid when splitting
    
    for i in range(0, len(row), max_images_per_grid):
        sub_row = row[i:i + max_images_per_grid]
        
        try:
            # Calculate sub-grid dimensions
            row_width = sum(img.width for img in sub_row)
            row_height = max(img.height for img in sub_row)
            
            # Create sub-grid image
            grid_img = Image.new('RGBA', (row_width, row_height), (255, 255, 255, 0))
            
            # Paste images
            x_offset = 0
            for img in sub_row:
                try:
                    grid_img.paste(img, (x_offset, 0), img if img.mode == 'RGBA' else None)
                    x_offset += img.width
                except:
                    continue
            
            # Save sub-grid
            output_file = os.path.join(output_dir, f'{file_prefix}_{start_num + saved_count:03d}.png')
            grid_img.save(output_file, 'PNG', optimize=True, compress_level=9)
            print(f"✓ Saved split: {output_file} ({row_width}x{row_height})")
            saved_count += 1
            
            # Clear memory
            del grid_img
            gc.collect()
            
        except Exception as e:
            print(f"⚠️  Error saving split grid: {e}")
            continue
    
    return saved_count

def export_design_to_png(file_path, output_dir="exports", max_width=1920, max_height=1080):
    """
    Universal export function - detects format by extension
    """
    file_ext = Path(file_path).suffix.lower()
    file_name = Path(file_path).stem
    
    print(f"=== Design to PNG Grid Export (Grid-Safe) ===")
    print(f"📁 Input: {file_path}")
    print(f"📂 Output: {output_dir}")
    print(f"📏 Max size: {max_width}x{max_height}")
    print(f"🔍 Format detected: {file_ext}")
    print(f"📝 File prefix: {file_name}")
    
    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    
    # Route to appropriate exporter with file prefix
    if file_ext == '.fig':
        return export_figma_to_png(file_path, output_dir, max_width, max_height)
    elif file_ext == '.psd':
        return export_psd_to_png(file_path, output_dir, max_width, max_height)
    elif file_ext == '.pdf':
        return export_pdf_to_png(file_path, output_dir, max_width, max_height)
    else:
        print(f"✗ Unsupported format: {file_ext}")
        print("Supported formats: .fig, .psd, .pdf")
        return False

def main():
    parser = argparse.ArgumentParser(description='Grid-Safe Design to PNG Export')
    parser.add_argument('file_path', help='Path to design file (.fig, .psd, .pdf)')
    parser.add_argument('output_dir', nargs='?', default='exports', help='Output directory (default: exports)')
    parser.add_argument('--max-width', type=int, default=1920, help='Maximum width per PNG (default: 1920)')
    parser.add_argument('--max-height', type=int, default=1080, help='Maximum height per PNG (default: 1080)')
    
    args = parser.parse_args()
    
    # Check file exists
    if not check_file_exists(args.file_path):
        sys.exit(1)
    
    # Check dependencies
    try:
        from PIL import Image
        print("✓ PIL/Pillow available")
    except ImportError:
        print("✗ PIL/Pillow not found. Install with:")
        print("pip install Pillow")
        sys.exit(1)
    
    # Export
    success = export_design_to_png(
        args.file_path, 
        args.output_dir,
        args.max_width,
        args.max_height
    )
    
    if success:
        print(f"\n🎉 Ready to upload PNG files to chat!")
        print(f"📁 Check the {args.output_dir} directory")
        png_files = [f for f in os.listdir(args.output_dir) if f.endswith('.png')]
        print(f"📊 Total files in directory: {len(png_files)}")
    else:
        print("\n❌ Export failed. Check the error messages above.")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
