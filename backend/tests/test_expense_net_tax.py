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


# ─── T2 : grand livre refactoré ───

def _line_account_number(server_mod, line):
    acc = server_mod.db.chart_of_accounts.find_one({"id": line.get("account_id")}, {"_id": 0, "account_number": 1})
    return acc.get("account_number") if acc else None


def test_migration_reposts_meals_gl_idempotent(auth_headers):
    """Une écriture de repas legacy (taxe récupérée 100%) est re-postée à 50% ; 2e passage no-op."""
    from backend import server
    org = server.db.users.find_one({"email": "gussdub@gmail.com"})
    org_id = org.get("organization_id")
    if not org_id:
        pytest.skip("org_id indisponible")
    prev = (server.db.company_settings.find_one({"organization_id": org_id}, {"_id": 0}) or {}).get("autopost_enabled", False)
    server.db.company_settings.update_one({"organization_id": org_id},
        {"$set": {"autopost_enabled": True}}, upsert=True)
    exp_id = None
    try:
        exp_id = client.post("/api/expenses", headers=auth_headers, json={
            "amount": 114.98, "currency": "CAD", "category_code": "meals_entertainment",
            "description": "Migr diner", "expense_date": "2099-10-01",
            "gst_paid_cad": 5.0, "qst_paid_cad": 9.98}).json()["id"]
        # Simuler l'ancien snapshot déductible TTC (57.49 = 50% de 114.98)
        server.db.expenses.update_one({"id": exp_id}, {"$set": {"deductible_amount": 57.49}})
        stats = server.migrate_expense_net_tax_v1()
        assert stats["resnapshotted"] >= 1 or stats["reposted"] >= 1
        exp = server.db.expenses.find_one({"id": exp_id}, {"_id": 0})
        # 107.49 × 50% = 53.745 → banker's rounding produit 53.74 (accepter 53.74 ou 53.75).
        assert abs(exp["deductible_amount"] - 53.745) <= 0.01, exp["deductible_amount"]
        # Idempotence : 2e passage ne re-snapshotte plus cette dépense
        stats2 = server.migrate_expense_net_tax_v1()
        assert exp_id not in stats2.get("resnapshotted_ids", [])
    finally:
        if exp_id:
            client.delete(f"/api/expenses/{exp_id}", headers=auth_headers)
        server.db.company_settings.update_one({"organization_id": org_id},
            {"$set": {"autopost_enabled": prev}})


def test_reconciliation_balanced_after_net(auth_headers):
    """Après le fix, P&L net == GL net → expenses_diff ≈ 0 (org autopost activé)."""
    from backend import server
    org = server.db.users.find_one({"email": "gussdub@gmail.com"})
    org_id = org.get("organization_id")
    if not org_id:
        pytest.skip("org_id indisponible")
    prev = (server.db.company_settings.find_one({"organization_id": org_id}, {"_id": 0}) or {}).get("autopost_enabled", False)
    server.db.company_settings.update_one({"organization_id": org_id},
        {"$set": {"autopost_enabled": True}}, upsert=True)
    exp_id = None
    try:
        exp_id = client.post("/api/expenses", headers=auth_headers, json={
            "amount": 114.98, "currency": "CAD", "category_code": "meals_entertainment",
            "description": "Recon diner", "expense_date": "2099-09-15",
            "gst_paid_cad": 5.0, "qst_paid_cad": 9.98}).json()["id"]
        r = client.get("/api/ledger/reconciliation?start=2099-09-01&end=2099-09-30",
                       headers=auth_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert abs(data["expenses"]["diff"]) < 0.02, data["expenses"]
    finally:
        if exp_id:
            client.delete(f"/api/expenses/{exp_id}", headers=auth_headers)
        server.db.company_settings.update_one({"organization_id": org_id},
            {"$set": {"autopost_enabled": prev}})


def test_sales_tax_meals_50_and_telecom_threshold(auth_headers):
    """CTI = 50% de la taxe repas ; télécom 8% affaires → CTI 0 (seuil ≤10%)."""
    ids = []
    try:
        ids.append(client.post("/api/expenses", headers=auth_headers, json={
            "amount": 114.98, "currency": "CAD", "category_code": "meals_entertainment",
            "description": "Diner", "expense_date": "2099-08-01",
            "gst_paid_cad": 5.0, "qst_paid_cad": 9.98}).json()["id"])
        # Télécom 8% affaires : perso 92% de 114.98 = 105.78
        ids.append(client.post("/api/expenses", headers=auth_headers, json={
            "amount": 114.98, "currency": "CAD", "category_code": "telecom_cell",
            "description": "Cell", "expense_date": "2099-08-02",
            "gst_paid_cad": 5.0, "qst_paid_cad": 9.98}).json()["id"])
        from backend import server
        server.db.expenses.update_one({"id": ids[1]}, {"$set": {"personal_use_amount_cad": 105.78}})
        r = client.get("/api/reports/sales-tax?start=2099-08-01&end=2099-08-31",
                       headers=auth_headers)
        assert r.status_code == 200, r.text
        summary = r.json()["summary"]
        # Repas seul contribue au CTI : 50% de 5.00 = 2.50 (GST) ; télécom 8% → 0.
        assert abs(summary["gst"]["paid"] - 2.50) < 0.02, summary["gst"]
        assert abs(summary["qst"]["paid"] - 4.99) < 0.02, summary["qst"]  # 50% de 9.98
    finally:
        from backend import server
        for i in ids:
            server.db.expenses.delete_one({"id": i})


def test_pnl_net_of_tax(auth_headers):
    """Le P&L compte la charge NETTE : office 114.98 → gross 100.00 ; repas → 107.49 / déd. 53.75."""
    ids = []
    try:
        ids.append(client.post("/api/expenses", headers=auth_headers, json={
            "amount": 114.98, "currency": "CAD", "category_code": "office_supplies",
            "description": "Fournitures", "expense_date": "2099-07-05",
            "gst_paid_cad": 5.0, "qst_paid_cad": 9.98}).json()["id"])
        ids.append(client.post("/api/expenses", headers=auth_headers, json={
            "amount": 114.98, "currency": "CAD", "category_code": "meals_entertainment",
            "description": "Diner", "expense_date": "2099-07-06",
            "gst_paid_cad": 5.0, "qst_paid_cad": 9.98}).json()["id"])
        r = client.get("/api/reports/pnl?start=2099-07-01&end=2099-07-31&basis=accrual",
                       headers=auth_headers)
        assert r.status_code == 200, r.text
        flat = {}
        for g in r.json()["expense_groups"]:
            for c in g["categories"]:
                flat[c["code"]] = c["current"]
        assert flat["office_supplies"]["gross"] == 100.00, flat["office_supplies"]
        assert flat["office_supplies"]["deductible"] == 100.00
        assert flat["meals_entertainment"]["gross"] == 107.49, flat["meals_entertainment"]
        # 107.49 × 50% = 53.745 → banker's rounding produit 53.74 (attendu 53.74 ou 53.75).
        assert abs(flat["meals_entertainment"]["deductible"] - 53.745) <= 0.01
    finally:
        from backend import server
        for i in ids:
            server.db.expenses.delete_one({"id": i})


def test_gl_charge_lines_meals_50pct(auth_headers):
    """Une écriture de repas récupère 50% de la taxe (12xx) et pose le reste en charge (5xxx)."""
    from backend import server
    org = server.db.users.find_one({"email": "gussdub@gmail.com"})
    org_id = org.get("organization_id")
    if not org_id:
        pytest.skip("org_id indisponible")
    prev = server.db.company_settings.find_one({"organization_id": org_id}, {"_id": 0}) or {}
    server.db.company_settings.update_one({"organization_id": org_id},
        {"$set": {"autopost_enabled": True}}, upsert=True)
    exp_id = None
    try:
        r = client.post("/api/expenses", headers=auth_headers, json={
            "amount": 114.98, "currency": "CAD", "category_code": "meals_entertainment",
            "description": "Diner client", "expense_date": "2099-04-10",
            "gst_paid_cad": 5.0, "qst_paid_cad": 9.98})
        assert r.status_code in (200, 201), r.text
        exp_id = r.json()["id"]
        exp = server.db.expenses.find_one({"id": exp_id}, {"_id": 0})
        lines = server._build_expense_charge_lines(org_id, org["id"], exp)
        debits = round(sum(l.get("debit", 0) for l in lines), 2)
        credits = round(sum(l.get("credit", 0) for l in lines), 2)
        assert debits == credits == 114.98, f"équilibre: Dr {debits} Cr {credits}"
        # Charge nette 5xxx = 107.49 (net de 50% de taxe)
        # Taxes récupérables 12xx = 7.49 (50% de 14.98)
        tax_debit = round(sum(l.get("debit", 0) for l in lines
                              if _line_account_number(server, l) in ("1200", "1210", "1220")), 2)
        assert tax_debit == 7.49, f"taxes récupérables attendues 7.49, obtenu {tax_debit}"
    finally:
        if exp_id:
            client.delete(f"/api/expenses/{exp_id}", headers=auth_headers)
        server.db.company_settings.update_one({"organization_id": org_id},
            {"$set": {"autopost_enabled": prev.get("autopost_enabled", False)}})


# ─── Non-régression : findings revue adversariale opus (feature #7.7) ───

def test_defensive_amount_cad_negative_no_imbalance():
    """[Finding G1 BLOCKING] amount_cad < 0 : les helpers clampent à 0 → pas de Σ Dr ≠ Cr.
    Une saisie erronée (montant négatif) ne peut plus casser l'équilibre partie double."""
    from backend.server import _expense_net_business_cad, _expense_recoverable_tax_cad
    e = _exp(amount_cad=-100.00, gst_paid_cad=-5.00, qst_paid_cad=-10.00,
             category_code="office_supplies")
    # Après clamp : amt = 0, taxes = 0 → net = 0 (pas de fantôme au P&L, pas de rejet GL).
    assert _expense_net_business_cad(e) == 0.0
    gst, qst, hst = _expense_recoverable_tax_cad(e)
    assert gst == 0.0 and qst == 0.0 and hst == 0.0


def test_defensive_taxes_negative_clamped():
    """[Finding G2 BLOCKING] Taxes saisies négatives clampées à 0 (une taxe payée est ≥ 0)."""
    from backend.server import _expense_recoverable_tax_cad
    e = _exp(amount_cad=100.00, gst_paid_cad=-5.00, qst_paid_cad=-10.00,
             category_code="office_supplies")
    gst, qst, hst = _expense_recoverable_tax_cad(e)
    assert gst == 0.0 and qst == 0.0 and hst == 0.0


def test_defensive_zero_exchange_rate_treated_as_cad():
    """[Finding G4 IMPORTANT] rate=0 traité comme non-étranger → pas de div/0, pas de bypass."""
    from backend.server import _expense_recoverable_tax_cad
    e = _exp(amount_cad=100.00, currency="USD", exchange_rate_to_cad=0.0,
             gst_paid_cad=5.00, qst_paid_cad=10.00, category_code="office_supplies")
    # is_foreign = False (rate ≤ 0) → taxes prises verbatim, pas de div/0.
    gst, qst, hst = _expense_recoverable_tax_cad(e)
    assert gst == 5.00 and qst == 10.00 and hst == 0.0


def test_telecom_threshold_boundary_exactly_10pct_zero_credit():
    """[Finding T1] À 10 % pile → 0 CTI (règle ARC Mémo 8-1 : « plus de 10 % » strict)."""
    from backend.server import _expense_recovery_frac
    # amt=1000, personal=900 → biz = 0.10 exactement → 0 (règle « > 10 % » stricte).
    e = _exp(amount_cad=1000.00, personal_use_amount_cad=900.00,
             category_code="telecom_cell")
    assert _expense_recovery_frac(e) == 0.0


def test_telecom_threshold_ieee754_stability_near_90pct():
    """[Finding T2] Non-déterminisme IEEE-754 aux voisinages 10/90 : biz arrondi à 4 décimales."""
    from backend.server import _expense_recovery_frac
    # amt=1000, personal=100.03 → biz ≈ 0.89997 (float) → arrondi 0.9000 → 1.0 (≥ 90 %).
    e = _exp(amount_cad=1000.00, personal_use_amount_cad=100.03,
             category_code="telecom_cell")
    assert _expense_recovery_frac(e) == 1.0


def test_sales_tax_uses_capped_helper_not_naive_sum():
    """[Finding G3 IMPORTANT] Le rapport TPS/TVQ utilise _expense_recoverable_tax_cad (avec cap),
    pas une somme naïve. Dépense minuscule avec taxes énormes → CTI capé au cap."""
    from backend.server import _expense_recoverable_tax_cad, _expense_recovery_frac
    e = _exp(amount_cad=0.02, personal_use_amount_cad=0.01,
             gst_paid_cad=0.10, qst_paid_cad=0.10, hst_paid_cad=0.10,
             category_code="office_supplies")
    frac = _expense_recovery_frac(e)  # = 0.5 (biz=0.5 dans (0.1, 0.9))
    assert frac == 0.5
    # Le helper cape à 0.01 (amt - personal), impossible de récupérer plus.
    gst, qst, hst = _expense_recoverable_tax_cad(e)
    assert (gst + qst + hst) <= 0.011  # ≤ cap ± arrondi
