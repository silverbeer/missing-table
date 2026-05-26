#!/usr/bin/env python3
"""
Generate PWA icon set from a single square source PNG.

Outputs all sizes the manifest + iOS need into frontend/public/pwa/:
  - icon-192.png, icon-256.png, icon-384.png, icon-512.png  (Android / manifest)
  - apple-touch-icon-180.png                                  (iOS home screen)
  - pwa-icon-master.png (copied from source, kept as the canonical 1024px reference)

Usage:
    cd backend && uv run python ../scripts/generate-pwa-icons.py <source.png>

    # Example (placeholder generation from existing wordmark):
    cd backend && uv run python ../scripts/generate-pwa-icons.py \
        ../frontend/src/assets/logo-full.png --pad-with brand-blue

When the real square master asset lands (see Linear SB-45), drop it in as
the source and re-run — outputs swap in place, no other code change needed.

Dependencies (already in backend/pyproject.toml via pillow):
    pillow

Why this script: PWAs need several icon sizes for different OS contexts.
Generating by hand is tedious and error-prone — one source, one command,
deterministic output.
"""

import argparse
import shutil
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "frontend" / "public" / "pwa"
MASTER_SIZE = 1024
SIZES = [192, 256, 384, 512]
APPLE_TOUCH_SIZE = 180
BRAND_BLUE = (2, 87, 254, 255)  # #0257fe — matches Tailwind brand-500


def pad_to_square(img: Image.Image, target: int, bg: tuple[int, int, int, int]) -> Image.Image:
    """Center img on a square canvas of size `target` with bg color.

    Scales img to fit ~88% of the canvas so it has visual breathing room
    against the background (per iOS icon-design guidance).
    """
    img = img.convert("RGBA")
    usable = int(target * 0.88)
    w, h = img.size
    scale = min(usable / w, usable / h)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    img = img.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (target, target), bg)
    x = (target - new_w) // 2
    y = (target - new_h) // 2
    canvas.paste(img, (x, y), img)
    return canvas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, help="Source image (square preferred; non-square gets padded)")
    parser.add_argument(
        "--pad-with",
        choices=["brand-blue", "transparent"],
        default="brand-blue",
        help="Background to pad non-square sources with (default: brand-blue)",
    )
    args = parser.parse_args()

    if not args.source.exists():
        raise SystemExit(f"Source not found: {args.source}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    bg = BRAND_BLUE if args.pad_with == "brand-blue" else (0, 0, 0, 0)

    src = Image.open(args.source).convert("RGBA")
    print(f"Source: {args.source.name} ({src.size[0]}x{src.size[1]})")

    # Master: 1024x1024, padded if source isn't square
    master = pad_to_square(src, MASTER_SIZE, bg)
    master_path = OUTPUT_DIR / "pwa-icon-master.png"
    master.save(master_path, "PNG")
    print(f"  Master: {master_path.relative_to(REPO_ROOT)} ({MASTER_SIZE}x{MASTER_SIZE})")

    # Derived sizes — downscale from master so they all look consistent
    for size in SIZES:
        out = master.resize((size, size), Image.LANCZOS)
        out_path = OUTPUT_DIR / f"icon-{size}.png"
        out.save(out_path, "PNG")
        print(f"  {out_path.name} ({size}x{size})")

    apple = master.resize((APPLE_TOUCH_SIZE, APPLE_TOUCH_SIZE), Image.LANCZOS)
    apple_path = OUTPUT_DIR / f"apple-touch-icon-{APPLE_TOUCH_SIZE}.png"
    apple.save(apple_path, "PNG")
    print(f"  {apple_path.name} ({APPLE_TOUCH_SIZE}x{APPLE_TOUCH_SIZE})")


if __name__ == "__main__":
    main()
