"""Unit tests for the shared logo size-variant helper (SB-114).

The previous variant code resized non-square logos straight to (px, px),
squashing them. The helper must fit the source inside a transparent square
canvas instead — the NAC tournament logo (347x431) was the motivating case.
"""

from __future__ import annotations

from io import BytesIO

from PIL import Image as PILImage

from app import _upload_logo_png_variants


class FakeBucket:
    def __init__(self, store):
        self._store = store

    def upload(self, path, content, file_options=None):
        self._store[path] = {"content": content, "file_options": file_options}


class FakeStorage:
    def __init__(self):
        self.uploads = {}

    def from_(self, bucket):
        return FakeBucket(self.uploads)


def _make_png_bytes(width: int, height: int, mode: str = "RGBA") -> bytes:
    img = PILImage.new(mode, (width, height), color=(10, 20, 30, 255))
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _open(data: bytes) -> PILImage.Image:
    return PILImage.open(BytesIO(data))


class TestUploadLogoPngVariants:
    def test_uploads_sm_and_md_variants(self):
        storage = FakeStorage()
        _upload_logo_png_variants(storage, "tournament-logos", "6", _make_png_bytes(347, 431))

        assert set(storage.uploads) == {"6_sm.png", "6_md.png"}
        assert _open(storage.uploads["6_sm.png"]["content"]).size == (64, 64)
        assert _open(storage.uploads["6_md.png"]["content"]).size == (128, 128)

    def test_non_square_source_is_not_distorted(self):
        # A tall source must keep its aspect ratio: the visible (opaque)
        # region of the square canvas should be narrower than it is tall.
        storage = FakeStorage()
        _upload_logo_png_variants(storage, "tournament-logos", "6", _make_png_bytes(347, 431))

        variant = _open(storage.uploads["6_md.png"]["content"])
        left, upper, right, lower = variant.getchannel("A").getbbox()
        visible_w, visible_h = right - left, lower - upper
        assert visible_h == 128  # tall axis fills the canvas
        assert visible_w < 128  # short axis is letterboxed, not stretched
        # Centered horizontally (allow 1px rounding)
        assert abs(left - (128 - right)) <= 1

    def test_square_source_fills_canvas(self):
        storage = FakeStorage()
        _upload_logo_png_variants(storage, "club-logos", "12", _make_png_bytes(500, 500))

        variant = _open(storage.uploads["12_md.png"]["content"])
        assert variant.getchannel("A").getbbox() == (0, 0, 128, 128)

    def test_rgb_source_is_converted(self):
        # JPG-ish RGB content saved as PNG must not crash the RGBA paste.
        storage = FakeStorage()
        _upload_logo_png_variants(storage, "club-logos", "3", _make_png_bytes(300, 200, mode="RGB"))

        variant = _open(storage.uploads["3_sm.png"]["content"])
        assert variant.size == (64, 64)
        assert variant.mode == "RGBA"

    def test_upserts_with_png_content_type(self):
        storage = FakeStorage()
        _upload_logo_png_variants(storage, "tournament-logos", "6", _make_png_bytes(100, 100))

        opts = storage.uploads["6_sm.png"]["file_options"]
        assert opts == {"content-type": "image/png", "upsert": "true"}
