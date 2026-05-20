"""Unit tests for the match-photo resize helper (SB-31).

The resize step bounds R2 storage cost. We're on Supabase free tier and want
photos to land at ~300KB regardless of input — uncapped 5MB uploads would
chew through R2 free-tier headroom over a season.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image as PILImage
from PIL import UnidentifiedImageError

from app import (
    _MATCH_PHOTO_JPEG_QUALITY,
    _MATCH_PHOTO_RESIZE_MAX,
    _resize_photo_to_jpeg,
)


def _make_png_bytes(width: int, height: int, mode: str = "RGB") -> bytes:
    img = PILImage.new(mode, (width, height), color=(255, 100, 50))
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _read_dims(data: bytes) -> tuple[int, int]:
    return PILImage.open(BytesIO(data)).size


def _read_format(data: bytes) -> str:
    return PILImage.open(BytesIO(data)).format


class TestResizePhotoToJpeg:
    def test_oversized_image_is_resized_within_bounds(self):
        big = _make_png_bytes(4000, 3000)
        out = _resize_photo_to_jpeg(big)
        w, h = _read_dims(out)
        max_w, max_h = _MATCH_PHOTO_RESIZE_MAX
        assert w <= max_w
        assert h <= max_h
        # aspect ratio preserved
        assert abs((w / h) - (4000 / 3000)) < 0.01

    def test_already_small_image_kept_at_native_size(self):
        small = _make_png_bytes(800, 600)
        out = _resize_photo_to_jpeg(small)
        # Pillow's thumbnail() never upscales, so this stays at 800x600.
        assert _read_dims(out) == (800, 600)

    def test_output_is_jpeg_regardless_of_input_format(self):
        png = _make_png_bytes(500, 500)
        out = _resize_photo_to_jpeg(png)
        assert _read_format(out) == "JPEG"

    def test_rgba_input_is_flattened_to_rgb(self):
        rgba = _make_png_bytes(500, 500, mode="RGBA")
        out = _resize_photo_to_jpeg(rgba)
        # If alpha wasn't flattened, save-as-JPEG would have raised.
        assert _read_format(out) == "JPEG"

    def test_resize_substantially_reduces_byte_size_for_large_input(self):
        # Pseudo-photographic input compresses well at q85.
        big = _make_png_bytes(3000, 2000)
        out = _resize_photo_to_jpeg(big)
        # The 6MP solid-color PNG is ~30KB; a 1080-ish-wide q85 JPEG of the
        # same content should be smaller. The real win shows up with photo
        # input, but we at least verify we didn't accidentally inflate.
        assert len(out) <= len(big)

    def test_invalid_image_bytes_raises(self):
        with pytest.raises(UnidentifiedImageError):
            _resize_photo_to_jpeg(b"not an image at all")

    def test_quality_constant_is_sane(self):
        # Document the expectation so future tweaks are intentional.
        assert 70 <= _MATCH_PHOTO_JPEG_QUALITY <= 95
