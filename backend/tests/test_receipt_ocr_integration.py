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


class TestGetReceipt:
    _cleanup_files = set()

    def test_get_existing_receipt(self, client, auth_headers, mock_extraction):
        mock_extraction({"vendor": "Test", "category_code": "other"})
        jpeg = _make_minimal_jpeg()
        scan = client.post("/api/expenses/scan-receipt",
                           files={"file": ("a.jpg", jpeg, "image/jpeg")},
                           headers=auth_headers).json()
        fid = scan["file_id"]
        TestGetReceipt._cleanup_files.add(fid)

        r = client.get(f"/api/receipts/{fid}", headers=auth_headers)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/")
        assert len(r.content) > 0

    def test_get_unknown_returns_404(self, client, auth_headers):
        r = client.get("/api/receipts/non-existent-id-12345", headers=auth_headers)
        assert r.status_code == 404

    def test_get_without_auth_returns_401_or_403(self, client):
        r = client.get("/api/receipts/anything")
        assert r.status_code in (401, 403)

    @classmethod
    def teardown_class(cls):
        if not cls._cleanup_files:
            return
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


class TestDeleteFile:
    def test_delete_existing_soft_deletes(self, client, auth_headers, mock_extraction):
        mock_extraction({"vendor": "X", "category_code": "other"})
        jpeg = _make_minimal_jpeg()
        scan = client.post("/api/expenses/scan-receipt",
                           files={"file": ("a.jpg", jpeg, "image/jpeg")},
                           headers=auth_headers).json()
        fid = scan["file_id"]

        r = client.delete(f"/api/files/{fid}", headers=auth_headers)
        assert r.status_code == 204

        # GET maintenant 404 (soft-deleted)
        r2 = client.get(f"/api/receipts/{fid}", headers=auth_headers)
        assert r2.status_code == 404

    def test_delete_unknown_returns_404(self, client, auth_headers):
        r = client.delete("/api/files/non-existent-id-xyz", headers=auth_headers)
        assert r.status_code == 404


class TestExpenseReceiptIntegration:
    _cleanup_expenses = set()
    _cleanup_files = set()

    def _create_scan(self, client, auth_headers, mock_extraction):
        mock_extraction({"vendor": "X", "category_code": "other"})
        jpeg = _make_minimal_jpeg()
        return client.post("/api/expenses/scan-receipt",
                            files={"file": ("a.jpg", jpeg, "image/jpeg")},
                            headers=auth_headers).json()

    def test_post_expense_with_receipt_persists_link(self, client, auth_headers, mock_extraction):
        scan = self._create_scan(client, auth_headers, mock_extraction)
        fid = scan["file_id"]
        TestExpenseReceiptIntegration._cleanup_files.add(fid)

        r = client.post("/api/expenses", headers=auth_headers, json={
            "vendor": "X", "expense_date": "2099-06-15",
            "amount": 100.00, "currency": "CAD",
            "category_code": "other",
            "receipt_file_id": fid,
        })
        assert r.status_code in (200, 201), r.text
        exp = r.json()
        assert exp.get("receipt_file_id") == fid
        TestExpenseReceiptIntegration._cleanup_expenses.add(exp["id"])

    def test_put_expense_swap_receipt_soft_deletes_old(self, client, auth_headers, mock_extraction):
        s1 = self._create_scan(client, auth_headers, mock_extraction)
        s2 = self._create_scan(client, auth_headers, mock_extraction)
        TestExpenseReceiptIntegration._cleanup_files.update([s1["file_id"], s2["file_id"]])

        exp = client.post("/api/expenses", headers=auth_headers, json={
            "vendor": "Y", "expense_date": "2099-06-16",
            "amount": 50.00, "currency": "CAD",
            "category_code": "other",
            "receipt_file_id": s1["file_id"],
        }).json()
        TestExpenseReceiptIntegration._cleanup_expenses.add(exp["id"])

        r = client.put(f"/api/expenses/{exp['id']}", headers=auth_headers, json={
            "receipt_file_id": s2["file_id"],
        })
        assert r.status_code == 200

        # s1 soft-deleted
        g = client.get(f"/api/receipts/{s1['file_id']}", headers=auth_headers)
        assert g.status_code == 404

    def test_delete_expense_with_receipt_soft_deletes_file(self, client, auth_headers, mock_extraction):
        scan = self._create_scan(client, auth_headers, mock_extraction)
        fid = scan["file_id"]
        TestExpenseReceiptIntegration._cleanup_files.add(fid)

        exp = client.post("/api/expenses", headers=auth_headers, json={
            "vendor": "Z", "expense_date": "2099-06-17",
            "amount": 25.00, "currency": "CAD",
            "category_code": "other",
            "receipt_file_id": fid,
        }).json()
        TestExpenseReceiptIntegration._cleanup_expenses.add(exp["id"])

        r = client.delete(f"/api/expenses/{exp['id']}", headers=auth_headers)
        assert r.status_code in (200, 204)

        g = client.get(f"/api/receipts/{fid}", headers=auth_headers)
        assert g.status_code == 404


class TestAuthMeQuota:
    def test_auth_me_includes_scan_quota(self, client, auth_headers):
        r = client.get("/api/auth/me", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert "scan_count_this_month" in body
        assert "scan_quota_limit" in body
        assert body["scan_quota_limit"] == 400
        assert "receipt_ocr_consent_at" in body

    def test_grant_consent_endpoint(self, client, auth_headers):
        r = client.post("/api/auth/me/receipt-ocr-consent", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body.get("receipt_ocr_consent_at")
        # Verify it's now in auth/me
        r2 = client.get("/api/auth/me", headers=auth_headers)
        assert r2.json().get("receipt_ocr_consent_at")
