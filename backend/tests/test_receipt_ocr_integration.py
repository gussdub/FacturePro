import io
import os
import uuid
import json
import requests
import pytest

BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="module")
def auth():
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "gussdub@gmail.com", "password": "testpass123"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
from PIL import Image as _PILImage
import server as server_module
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    return TestClient(server_module.app)


@pytest.fixture(scope="module")
def auth_headers(client):
    resp = client.post("/api/auth/login",
                       json={"email": "gussdub@gmail.com", "password": "testpass123"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _make_minimal_jpeg():
    """Mini JPEG valide via PIL."""
    buf = io.BytesIO()
    _PILImage.new("RGB", (10, 10), (255, 255, 255)).save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture
def mock_extraction():
    """Fixture qui force la réponse d'Anthropic via un attribut module-level
    (bypass total de l'appel SDK). Reset après le test."""
    def _set(extraction_dict):
        server_module._TEST_MOCK_EXTRACTION = extraction_dict
    yield _set
    if hasattr(server_module, "_TEST_MOCK_EXTRACTION"):
        delattr(server_module, "_TEST_MOCK_EXTRACTION")


class TestScanReceiptEndpoint:
    _cleanup_files = set()

    def test_missing_file_returns_422(self, client, auth_headers):
        r = client.post("/api/expenses/scan-receipt", headers=auth_headers)
        assert r.status_code == 422

    def test_oversize_returns_413(self, client, auth_headers):
        big = b"\xff\xd8\xff\xe0" + b"X" * (6 * 1024 * 1024)
        files = {"file": ("big.jpg", big, "image/jpeg")}
        r = client.post("/api/expenses/scan-receipt", files=files, headers=auth_headers)
        assert r.status_code == 413

    def test_invalid_mime_returns_422(self, client, auth_headers):
        files = {"file": ("evil.jpg", b"<svg>foo</svg>", "image/jpeg")}
        r = client.post("/api/expenses/scan-receipt", files=files, headers=auth_headers)
        assert r.status_code == 422

    def test_happy_path(self, client, auth_headers, mock_extraction):
        mock_extraction({
            "vendor": "Costco",
            "expense_date": "2099-06-15",
            "total_cad": 127.05,
            "gst_paid_cad": 5.53,
            "qst_paid_cad": 11.02,
            "category_code": "office_supplies",
            "currency_detected": "CAD",
        })
        jpeg = _make_minimal_jpeg()
        files = {"file": ("test.jpg", jpeg, "image/jpeg")}
        r = client.post("/api/expenses/scan-receipt", files=files, headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "file_id" in body
        assert body["extraction"]["vendor"] == "Costco"
        assert body["extraction"]["category_code"] == "office_supplies"
        TestScanReceiptEndpoint._cleanup_files.add(body["file_id"])

    @classmethod
    def teardown_class(cls):
        if not cls._cleanup_files:
            return
        # Use requests against the live server for cleanup
        try:
            resp = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": "gussdub@gmail.com", "password": "testpass123"},
            )
            if resp.status_code != 200:
                return
            auth = {"Authorization": f"Bearer {resp.json()['access_token']}"}
            for fid in cls._cleanup_files:
                try:
                    requests.delete(f"{BASE_URL}/api/files/{fid}", headers=auth)
                except Exception:
                    pass
        except Exception:
            pass
