#!/usr/bin/env python3
"""
Prepare club logo images for upload.

Takes a source image (any format/size), removes the background,
centers and pads to a square, and outputs a 512x512 transparent PNG.

Usage:
    python scripts/prep-logo.py input.png --club "Bayside FC"
    python scripts/prep-logo.py input.jpg --club "Inter Miami CF" --size 256
    python scripts/prep-logo.py input.png --club "CF Montréal" --no-remove-bg

Dependencies:
    pip install Pillow rembg

The output is saved to club-logos/{slug}.png where slug is derived
from the club name (lowercase, hyphens, accents stripped).
"""

import argparse
import re
import sys
import unicodedata
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Missing dependency: pip install Pillow")
    sys.exit(1)


def club_name_to_slug(name: str) -> str:
    """Convert club name to filename slug: 'Inter Miami CF' -> 'inter-miami-cf'"""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return name


def remove_background(img: Image.Image) -> Image.Image:
    """Remove background using rembg."""
    try:
        from rembg import remove
    except ImportError:
        print("Missing dependency: pip install rembg")
        print("Or use --no-remove-bg to skip background removal.")
        sys.exit(1)

    return remove(img)


def center_and_pad(img: Image.Image, target_size: int) -> Image.Image:
    """Center the image content in a square canvas with transparent padding."""
    # Crop to content bounding box (non-transparent pixels)
    if img.mode == "RGBA":
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)

    # Scale to fit within target_size with some padding (90% of canvas)
    usable = int(target_size * 0.90)
    w, h = img.size
    scale = min(usable / w, usable / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    # Center on transparent canvas
    canvas = Image.new("RGBA", (target_size, target_size), (0, 0, 0, 0))
    x = (target_size - new_w) // 2
    y = (target_size - new_h) // 2
    canvas.paste(img, (x, y), img if img.mode == "RGBA" else None)

    return canvas


def main():
    parser = argparse.ArgumentParser(description="Prepare club logo for upload")
    parser.add_argument("input", type=Path, help="Source image file")
    parser.add_argument("--club", required=True, help="Club name (e.g. 'Inter Miami CF')")
    parser.add_argument("--size", type=int, default=512, help="Output size in pixels (default: 512)")
    parser.add_argument(
        "--no-remove-bg",
        action="store_true",
        help="Skip background removal (use if image already has transparent background)",
    )
    parser.add_argument("--output-dir", type=Path, default=None, help="Output directory (default: club-logos/)")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Input file not found: {args.input}")
        sys.exit(1)

    # Determine output path
    slug = club_name_to_slug(args.club)
    output_dir = args.output_dir or Path(__file__).parent.parent / "club-logos"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"{slug}.png"

    print(f"Processing: {args.input}")
    print(f"Club: {args.club} -> {slug}.png")

    img = Image.open(args.input).convert("RGBA")
    print(f"Source: {img.size[0]}x{img.size[1]}")

    if not args.no_remove_bg:
        print("Removing background...")
        img = remove_background(img)

    print(f"Centering and padding to {args.size}x{args.size}...")
    img = center_and_pad(img, args.size)

    img.save(output_path, "PNG")
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
