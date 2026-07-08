"""Tests — dépenses nettes des taxes récupérables (feature #7.7).

Vérifie le helper unifié de fraction récupérable (50% repas, seuils 10/90 télécom),
la charge nette (P&L/5xxx), le rapport TPS/TVQ, l'équilibre partie double, et la
migration idempotente.
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


def _exp(**kw):
    """Fabrique un dict dépense minimal pour les tests unitaires des helpers."""
    base = {"amount_cad": 0.0, "currency": "CAD", "exchange_rate_to_cad": 1.0,
            "gst_paid_cad": 0.0, "qst_paid_cad": 0.0, "hst_paid_cad": 0.0,
            "category_code": "office_supplies"}
    base.update(kw)
    return base


def test_recovery_frac_normal_meals_telecom():
    from backend.server import _expense_recovery_frac
    # normal → 1.0
    assert _expense_recovery_frac(_exp(category_code="office_supplies")) == 1.0
    # repas → 0.5
    assert _expense_recovery_frac(_exp(category_code="meals_entertainment")) == 0.5
    # télécom 60% (perso 40% de 100) → 0.6
    assert abs(_expense_recovery_frac(_exp(category_code="telecom_cell",
               amount_cad=100.0, personal_use_amount_cad=40.0)) - 0.6) < 1e-9
    # télécom 8% affaires (perso 92) → seuil ≤10% → 0.0
    assert _expense_recovery_frac(_exp(category_code="telecom_cell",
               amount_cad=100.0, personal_use_amount_cad=92.0)) == 0.0
    # télécom 95% affaires (perso 5) → seuil ≥90% → 1.0
    assert _expense_recovery_frac(_exp(category_code="telecom_cell",
               amount_cad=100.0, personal_use_amount_cad=5.0)) == 1.0


def test_net_business_and_balance():
    from backend.server import _expense_net_business_cad, _expense_recoverable_tax_cad
    # Office 114.98 TTC (100 + 14.98 taxes QC) → net 100.00
    e = _exp(category_code="office_supplies", amount_cad=114.98, gst_paid_cad=5.0, qst_paid_cad=9.98)
    assert _expense_net_business_cad(e) == 100.00
    # Repas 114.98 → récupérable 50% (7.49) → net 107.49
    m = _exp(category_code="meals_entertainment", amount_cad=114.98, gst_paid_cad=5.0, qst_paid_cad=9.98)
    assert _expense_net_business_cad(m) == 107.49
    # Télécom 60% 114.98 (perso 45.99) → récupérable 0.6×14.98=8.99 → net 60.00
    t = _exp(category_code="telecom_cell", amount_cad=114.98, personal_use_amount_cad=45.99,
             gst_paid_cad=5.0, qst_paid_cad=9.98)
    assert _expense_net_business_cad(t) == 60.00
    # INVARIANT équilibre : net + Σrecoverable + personal == amount_cad (au cent près)
    for exp in (e, m, t):
        gst, qst, hst = _expense_recoverable_tax_cad(exp)
        personal = float(exp.get("personal_use_amount_cad", 0) or 0)
        net = _expense_net_business_cad(exp)
        assert abs(net + gst + qst + hst + personal - exp["amount_cad"]) < 0.011


def test_recoverable_capped_at_business_amount():
    from backend.server import _expense_recoverable_tax_cad
    # Taxes aberrantes > montant : capées à amount - personal (jamais > la portion affaires payée).
    e = _exp(category_code="office_supplies", amount_cad=10.0, gst_paid_cad=8.0, qst_paid_cad=8.0)
    gst, qst, hst = _expense_recoverable_tax_cad(e)
    assert abs((gst + qst + hst) - 10.0) < 0.011
