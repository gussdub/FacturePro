"""Tests — en-têtes de sécurité HTTP (audit Loi 25).

Backend : le middleware pose les en-têtes durcis sur TOUTES les réponses.
Frontend : vercel.json applique les mêmes en-têtes + une CSP (enforcée) au document servi."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")
os.environ.setdefault("DB_NAME", "facturepro")

from fastapi.testclient import TestClient  # noqa: E402
from backend.server import app  # noqa: E402

client = TestClient(app)

_EXPECTED = {
    "strict-transport-security": "max-age=31536000; includeSubDomains",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
}


class TestBackendHeaders:
    def test_headers_present_on_public_endpoint(self):
        r = client.get("/api/health")
        for k, v in _EXPECTED.items():
            assert r.headers.get(k) == v, f"{k} manquant/incorrect"

    def test_headers_present_on_404(self):
        # Le middleware s'applique à toutes les réponses, y compris les erreurs.
        r = client.get("/api/does-not-exist-xyz")
        assert r.headers.get("x-frame-options") == "DENY"
        assert r.headers.get("x-content-type-options") == "nosniff"

    def test_no_backend_csp(self):
        # Pas de CSP côté API (elle vit sur le frontend) → ne casse pas les endpoints fichiers/PDF.
        r = client.get("/api/health")
        assert "content-security-policy" not in {k.lower() for k in r.headers.keys()}


class TestVercelHeaders:
    def _load(self):
        path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "vercel.json")
        with open(path, encoding="utf-8") as f:
            return json.load(f)   # lève si JSON invalide

    def _csp(self):
        cfg = self._load()
        hdrs = {h["key"]: h["value"] for h in cfg["headers"][0]["headers"]}
        return hdrs

    def test_vercel_json_valid_and_hardening_headers(self):
        h = self._csp()
        assert h["Strict-Transport-Security"].startswith("max-age=")
        assert h["X-Content-Type-Options"] == "nosniff"
        assert h["X-Frame-Options"] == "DENY"
        assert h["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "camera=()" in h["Permissions-Policy"]

    def test_csp_directives(self):
        # CSP désormais ENFORCÉE (plus en Report-Only) après vérification prod (0 violation).
        csp = self._csp()["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "'unsafe-inline'" in csp and "https://fonts.googleapis.com" in csp   # styles inline + fonts
        assert "https://fonts.gstatic.com" in csp                                    # fichiers de police
        assert "frame-ancestors 'none'" in csp                                       # anti-clickjacking
        assert "object-src 'none'" in csp and "base-uri 'self'" in csp
        # le backend doit être autorisé pour connect (fetch/axios) ET img (logos cross-origin)
        assert csp.count("https://facturepro-backend-dkvn.onrender.com") >= 2
        assert "blob:" in csp and "data:" in csp                                     # reçus + QR/vignettes
