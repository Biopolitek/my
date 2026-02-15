#!/usr/bin/env python3
"""
Figma to PNG Grid Export Script
Exports Figma frames to PNG grid with optimal sizing
No external dependencies except Pillow
"""

import os
import sys
import json
import zipfile
import argparse
from pathlib import Path
from PIL import Image, ImageDraw

def check_figma_file(figma_file):
    """Check if .fig file is valid and extract info"""
    try:
        with zipfile.ZipFile(figma_file, 'r') as zip_file:
            if 'canvas.json' not in zip_file.namelist():
                print("✗ Invalid .fig file structure")
                return False
            
            # Read canvas info
            with zip_file.open('canvas.json') as f:
                canvas_data = json.load(f)
                print(f"✓ Figma file loaded: {len(canvas_data.get('children', []))} frames found")
                return True
    except Exception as e:
        print(f"✗ Error reading .fig file: {e}")
        return False

def extract_frames_from_figma(figma_file, output_dir="exports", max_width=1920, max_height=1080):
    """
    Extract frames from .fig file and create PNG grid
    
    Args:
        figma_file: Path to .fig file
        output_dir: Output directory for PNG files
        max_width: Maximum width per PNG file
        max_height: Maximum height per PNG file
    """
    
    if not os.path.exists(figma_file):
        print(f"✗ Figma file not found: {figma_file}")
        return False
    
    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    
    try:
        with zipfile.ZipFile(figma_file, 'r') as zip_file:
            # Extract all images
            image_files = [f for f in zip_file.namelist() if f.startswith('images/')]
            
            if not image_files:
                print("✗ No images found in .fig file")
                return False
            
            print(f"📤 Found {len(image_files)} images, extracting...")
            
            # Create grid layout
            grid_images = []
            current_row = []
            current_width = 0
            current_height = 0
            
            for img_file in image_files:
                try:
                    with zip_file.open(img_file) as img_data:
                        img = Image.open(img_data)
                        
                        # Check if we need new row
                        if current_width + img.width > max_width:
                            if current_row:
                                grid_images.append(current_row)
                                current_row = []
                                current_width = 0
                        
                        current_row.append(img)
                        current_width += img.width
                        current_height = max(current_height, img.height)
                        
                except Exception as e:
                    print(f"⚠️  Skipping {img_file}: {e}")
            
            # Add last row
            if current_row:
                grid_images.append(current_row)
            
            # Create PNG files from grid
            for i, row in enumerate(grid_images):
                if not row:
                    continue
                
                # Calculate grid dimensions
                row_width = sum(img.width for img in row)
                row_height = max(img.height for img in row)
                
                # Create grid image
                grid_img = Image.new('RGBA', (row_width, row_height), (255, 255, 255, 0))
                
                # Paste images
                x_offset = 0
                for img in row:
                    grid_img.paste(img, (x_offset, 0), img if img.mode == 'RGBA' else None)
                    x_offset += img.width
                
                # Save grid
                output_file = os.path.join(output_dir, f'figma_grid_{i+1:03d}.png')
                grid_img.save(output_file, 'PNG')
                print(f"✓ Saved: {output_file} ({row_width}x{row_height})")
            
            print(f"\n🎉 Export completed! {len(grid_images)} PNG files created")
            return True
            
    except Exception as e:
        print(f"✗ Error extracting frames: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Export Figma .fig file to PNG grid')
    parser.add_argument('figma_file', help='Path to .fig file')
    parser.add_argument('output_dir', nargs='?', default='exports', help='Output directory (default: exports)')
    parser.add_argument('--max-width', type=int, default=1920, help='Maximum width per PNG (default: 1920)')
    parser.add_argument('--max-height', type=int, default=1080, help='Maximum height per PNG (default: 1080)')
    
    args = parser.parse_args()
    
    print("=== Figma to PNG Grid Export ===")
    print(f"📁 Input: {args.figma_file}")
    print(f"📂 Output: {args.output_dir}")
    print(f"📏 Max size: {args.max_width}x{args.max_height}")
    
    # Check dependencies
    try:
        from PIL import Image
        print("✓ PIL/Pillow available")
    except ImportError:
        print("✗ PIL/Pillow not found. Install with:")
        print("pip install Pillow")
        sys.exit(1)
    
    # Check Figma file
    if not check_figma_file(args.figma_file):
        sys.exit(1)
    
    # Export
    success = extract_frames_from_figma(
        args.figma_file, 
        args.output_dir,
        args.max_width,
        args.max_height
    )
    
    if success:
        print(f"\n🎉 Ready to upload PNG files to chat!")
        print(f"📁 Check the {args.output_dir} directory")
        print(f"📊 Files created: {len([f for f in os.listdir(args.output_dir) if f.endswith('.png')])}")
    else:
        print("\n❌ Export failed. Check the error messages above.")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
