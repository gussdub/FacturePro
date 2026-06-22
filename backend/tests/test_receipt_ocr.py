import io
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from server import _detect_image_mime, _check_image_decompression


class TestDetectImageMime:
    def test_jpeg(self):
        assert _detect_image_mime(b"\xff\xd8\xff\xe0" + b"X" * 10) == "image/jpeg"
    def test_png(self):
        assert _detect_image_mime(b"\x89PNG\r\n\x1a\n" + b"X" * 10) == "image/png"
    def test_gif(self):
        assert _detect_image_mime(b"GIF89a" + b"X" * 10) == "image/gif"
    def test_webp(self):
        assert _detect_image_mime(b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"X" * 10) == "image/webp"
    def test_riff_but_not_webp(self):
        assert _detect_image_mime(b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"X" * 10) is None
    def test_svg_rejected(self):
        assert _detect_image_mime(b"<svg xmlns='...'><script>alert(1)</script></svg>") is None
    def test_empty(self):
        assert _detect_image_mime(b"") is None
    def test_too_short(self):
        assert _detect_image_mime(b"\xff") is None


class TestCheckImageDecompression:
    def test_normal_jpeg_passes(self):
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (100, 100), (200, 200, 200)).save(buf, "JPEG")
        _check_image_decompression(buf.getvalue())  # ne devrait pas raise

    def test_decompression_bomb_rejected(self):
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (10000, 10000), (200, 200, 200)).save(buf, "JPEG")
        with pytest.raises(ValueError, match="too large"):
            _check_image_decompression(buf.getvalue())

    def test_corrupted_data_raises(self):
        with pytest.raises(ValueError):
            _check_image_decompression(b"not an image")
