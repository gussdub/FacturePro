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


def test_expense_categories_have_dual_codes():
    """Chaque catégorie porte les 4 nouveaux champs (t2125_line + t2125_label_fr +
    gifi_code + gifi_label_en) et n'a PLUS de arc_line."""
    from backend.server import EXPENSE_CATEGORIES
    required = {"code", "label_fr", "label_en", "t2125_line", "t2125_label_fr",
                "gifi_code", "gifi_label_en", "deductible_percentage", "group"}
    for cat in EXPENSE_CATEGORIES:
        missing = required - set(cat.keys())
        assert not missing, f"{cat['code']} manque {missing}"
        assert "arc_line" not in cat, f"{cat['code']} porte encore l'ancien arc_line"


def test_expense_categories_correct_codes():
    """Codes fiscaux corrigés par la revue adversariale multi-sources CRA."""
    from backend.server import EXPENSE_CATEGORIES
    by = {c["code"]: c for c in EXPENSE_CATEGORIES}
    # Corrections dues aux erreurs historiques
    assert by["bank_charges"]["t2125_line"] == "8710"
    assert by["bank_charges"]["gifi_code"] == "8715"
    assert by["subscriptions"]["t2125_line"] == "8760"
    assert by["subscriptions"]["gifi_code"] == "8810"
    assert by["subcontracts"]["t2125_line"] == "9060"  # pas de ligne T2125 dédiée
    assert by["subcontracts"]["gifi_code"] == "9110"
    # T2125 8521 ≠ GIFI 8520 pour la pub (à 1 chiffre d'écart)
    assert by["advertising"]["t2125_line"] == "8521"
    assert by["advertising"]["gifi_code"] == "8520"
    # Télécom : T2125 pas de ligne dédiée (convention 9220), GIFI granulaire
    assert by["telecom_cell"]["gifi_code"] == "9225"
    assert by["telecom_internet"]["gifi_code"] == "9152"
