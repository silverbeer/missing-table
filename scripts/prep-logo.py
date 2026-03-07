#!/usr/bin/env python3
"""
Prepare club logo images for upload.

Takes a source image (any format/size), removes the background,
centers and pads to a square, and outputs a 512x512 transparent PNG.

Usage:
    # Single file mode (by club name):
    cd backend && uv run python ../scripts/prep-logo.py input.png --club "Bayside FC"
    cd backend && uv run python ../scripts/prep-logo.py input.jpg --club "Inter Miami CF" --size 256
    cd backend && uv run python ../scripts/prep-logo.py input.png --club "CF Montréal" --no-remove-bg

    # Batch mode (process all images in club-logos/raw/):
    cd backend && uv run python ../scripts/prep-logo.py --batch
    cd backend && uv run python ../scripts/prep-logo.py --batch --no-remove-bg

Dependencies (managed via uv in backend/pyproject.toml):
    pillow, rembg

Single-file mode: output to club-logos/ready/{slug}.png (slug from club name).
Batch mode: globs club-logos/raw/*, outputs to club-logos/ready/{stem}.png.
"""

import argparse
import sys
from pathlib import Path

# Add backend to path so we can import models
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from PIL import Image

from models.clubs import club_name_to_slug

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}
PROJECT_ROOT = Path(__file__).parent.parent
RAW_DIR = PROJECT_ROOT / "club-logos" / "raw"
READY_DIR = PROJECT_ROOT / "club-logos" / "ready"


def remove_background(img: Image.Image) -> Image.Image:
    """Remove background using rembg."""
    from rembg import remove

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


def process_single(input_path: Path, output_path: Path, size: int, skip_bg_removal: bool) -> bool:
    """Process a single image file. Returns True on success."""
    print(f"Processing: {input_path}")

    img = Image.open(input_path).convert("RGBA")
    print(f"  Source: {img.size[0]}x{img.size[1]}")

    if not skip_bg_removal:
        print("  Removing background...")
        img = remove_background(img)

    print(f"  Centering and padding to {size}x{size}...")
    img = center_and_pad(img, size)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    print(f"  Saved: {output_path}")
    return True


def run_batch(size: int, skip_bg_removal: bool) -> None:
    """Process all images in club-logos/raw/ and output to club-logos/ready/."""
    if not RAW_DIR.exists():
        print(f"Raw directory not found: {RAW_DIR}")
        print("Create it and place source images there, named as {slug}.ext")
        sys.exit(1)

    READY_DIR.mkdir(parents=True, exist_ok=True)

    raw_files = sorted(RAW_DIR.iterdir())
    if not raw_files:
        print(f"No files found in {RAW_DIR}")
        return

    stats = {"processed": 0, "skipped_fresh": 0, "skipped_unsupported": 0, "errors": 0}

    for raw_path in raw_files:
        if not raw_path.is_file():
            continue

        # Skip unsupported formats
        if raw_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            print(f"Skipping unsupported format: {raw_path.name}")
            stats["skipped_unsupported"] += 1
            continue

        # Output uses the filename stem (without extension) as the slug
        output_path = READY_DIR / f"{raw_path.stem}.png"

        # Skip if output already exists and is newer than input
        if output_path.exists() and output_path.stat().st_mtime > raw_path.stat().st_mtime:
            print(f"Skipping (already up to date): {raw_path.name}")
            stats["skipped_fresh"] += 1
            continue

        try:
            process_single(raw_path, output_path, size, skip_bg_removal)
            stats["processed"] += 1
        except Exception as e:
            print(f"Error processing {raw_path.name}: {e}")
            stats["errors"] += 1

    # Summary
    print(f"\nBatch complete: {stats['processed']} processed", end="")
    if stats["skipped_fresh"]:
        print(f", {stats['skipped_fresh']} up-to-date", end="")
    if stats["skipped_unsupported"]:
        print(f", {stats['skipped_unsupported']} unsupported", end="")
    if stats["errors"]:
        print(f", {stats['errors']} errors", end="")
    print()


def main():
    parser = argparse.ArgumentParser(description="Prepare club logo for upload")
    parser.add_argument("input", type=Path, nargs="?", help="Source image file (single-file mode)")
    parser.add_argument("--club", help="Club name for single-file mode (e.g. 'Inter Miami CF')")
    parser.add_argument("--batch", action="store_true", help="Process all images in club-logos/raw/")
    parser.add_argument("--size", type=int, default=512, help="Output size in pixels (default: 512)")
    parser.add_argument(
        "--no-remove-bg",
        action="store_true",
        help="Skip background removal (use if image already has transparent background)",
    )
    parser.add_argument("--output-dir", type=Path, default=None, help="Output directory (single-file mode)")
    args = parser.parse_args()

    if args.batch:
        # Batch mode: process all files in club-logos/raw/
        run_batch(args.size, args.no_remove_bg)
    elif args.input and args.club:
        # Single-file mode: process one file by club name
        if not args.input.exists():
            print(f"Input file not found: {args.input}")
            sys.exit(1)

        slug = club_name_to_slug(args.club)
        output_dir = args.output_dir or READY_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{slug}.png"

        print(f"Club: {args.club} -> {slug}.png")
        process_single(args.input, output_path, args.size, args.no_remove_bg)
    else:
        parser.error("Either --batch or (input + --club) is required")


if __name__ == "__main__":
    main()
