"""Tests — codes fiscaux adaptés au type d'entité (feature #7.6).

Vérifie que :
- EXPENSE_CATEGORIES porte les 4 nouveaux champs (t2125_line, gifi_code, etc.).
- Le snapshot de dépense fige les deux codes + garde category_arc_line legacy.
- La migration migrate_expense_tax_codes_v1 corrige les codes ARC erronés + ajoute
  les nouveaux champs sur les dépenses historiques.
- Le rapport GIFI agrège par category_gifi_code.
- Le rapport T2125 continue de fonctionner (rétrocompat via category_arc_line).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")
os.environ.setdefault("DB_NAME", "facturepro")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from backend.server import app, db  # noqa: E402

client = TestClient(app)


@pytest.fixture
def auth_headers():
    r = client.post("/api/auth/login", json={"email": "gussdub@gmail.com", "password": "testpass123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
