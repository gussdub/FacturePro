"""Tests — Dépenses télécom à usage mixte (feature #14).

Couvre : le snapshot (portion affaires/perso), le helper de %, la réduction P&L, et
surtout l'ÉCRITURE de grand livre à 3 lignes (Dr charge affaires / Dr taxes affaires /
Dr Dû par un actionnaire / Cr Encaisse), qui doit TOUJOURS équilibrer.

Le split GL est testé sur un org JETABLE (chart seedé, supprimé en fin de test) pour ne
toucher aucune donnée réelle.
"""
import os
import sys
import uuid as _uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")

import pytest  # noqa: E402
from backend.server import (  # noqa: E402
    _build_expense_category_snapshot,
    _telecom_business_pct,
    _build_expense_charge_lines,
    _ensure_chart_seeded,
    EXPENSE_ACCOUNT_NUMBERS,
    db,
)


# ─── Snapshot ───
class TestTelecomSnapshot:
    def test_mixed_85pct(self):
        s = _build_expense_category_snapshot({"category_code": "telecom_cell"}, 80.0, telecom_business_pct=85)
        assert s["business_use_pct"] == 85
        assert s["deductible_percentage"] == 85
        assert s["deductible_amount"] == 68.0
        assert s["personal_use_amount_cad"] == 12.0

    def test_off_is_full_business(self):
        s = _build_expense_category_snapshot({"category_code": "telecom_internet"}, 80.0, telecom_business_pct=None)
        assert s["deductible_amount"] == 80.0
        assert s["personal_use_amount_cad"] == 0.0

    def test_zero_pct(self):
        s = _build_expense_category_snapshot({"category_code": "telecom_cell"}, 50.0, telecom_business_pct=0)
        assert s["deductible_amount"] == 0.0
        assert s["personal_use_amount_cad"] == 50.0

    def test_non_telecom_has_no_personal_field(self):
        s = _build_expense_category_snapshot({"category_code": "meals_entertainment"}, 100.0)
        assert "personal_use_amount_cad" not in s
        assert s["deductible_percentage"] == 50  # inchangé pour les repas

    def test_rounding(self):
        s = _build_expense_category_snapshot({"category_code": "telecom_cell"}, 33.33, telecom_business_pct=33)
        # 33.33 * 0.33 = 10.9989 -> 11.00 ; perso = 33.33 - 11.00 = 22.33
        assert s["deductible_amount"] == 11.0
        assert s["personal_use_amount_cad"] == 22.33
        assert round(s["deductible_amount"] + s["personal_use_amount_cad"], 2) == 33.33


class TestTelecomBusinessPct:
    def test_mixed_on(self):
        assert _telecom_business_pct({"telecom_cell_mixed_use": True, "telecom_cell_business_pct": 70}, "telecom_cell") == 70

    def test_mixed_off_returns_none(self):
        assert _telecom_business_pct({"telecom_cell_mixed_use": False}, "telecom_cell") is None

    def test_internet_independent(self):
        s = {"telecom_internet_mixed_use": True, "telecom_internet_business_pct": 40}
        assert _telecom_business_pct(s, "telecom_internet") == 40
        assert _telecom_business_pct(s, "telecom_cell") is None

    def test_non_telecom(self):
        assert _telecom_business_pct({}, "office_expenses") is None


# ─── Écriture de grand livre (split) — org jetable ───
@pytest.fixture()
def temp_org():
    org_id = f"TESTORG-{_uuid.uuid4()}"
    user_id = f"TESTUSER-{_uuid.uuid4()}"
    _ensure_chart_seeded(org_id, user_id)
    yield org_id, user_id
    db.chart_of_accounts.delete_many({"organization_id": org_id})


def _num_by_id(org_id):
    return {a["id"]: a["account_number"]
            for a in db.chart_of_accounts.find({"organization_id": org_id}, {"_id": 0})}


def _sum(lines, side):
    return round(sum(float(l.get(side, 0) or 0) for l in lines), 2)


class TestTelecomLedgerSplit:
    def test_seed_includes_new_accounts(self, temp_org):
        org_id, _ = temp_org
        nums = set(_num_by_id(org_id).values())
        assert "1300" in nums                          # Dû par un actionnaire
        assert EXPENSE_ACCOUNT_NUMBERS["telecom_cell"] in nums  # 5050

    def test_mixed_no_tax_three_line_split(self, temp_org):
        org_id, user_id = temp_org
        exp = {
            "id": "e1", "amount_cad": 80.0, "category_code": "telecom_cell",
            "gst_paid_cad": 0, "qst_paid_cad": 0, "hst_paid_cad": 0,
            "personal_use_amount_cad": 12.0,  # business 85% -> 68 / perso 12
        }
        lines = _build_expense_charge_lines(org_id, user_id, exp)
        by = _num_by_id(org_id)
        debits = {by[l["account_id"]]: l["debit"] for l in lines if l["debit"] > 0}
        credits = {by[l["account_id"]]: l["credit"] for l in lines if l["credit"] > 0}
        assert debits["5050"] == 68.0            # charge affaires
        assert debits["1300"] == 12.0            # portion perso -> actionnaire
        assert credits["1000"] == 80.0           # Encaisse (total)
        assert _sum(lines, "debit") == _sum(lines, "credit") == 80.0

    def test_mixed_with_tax_itc_business_only(self, temp_org):
        org_id, user_id = temp_org
        exp = {
            "id": "e2", "amount_cad": 100.0, "category_code": "telecom_cell",
            "gst_paid_cad": 5.0, "qst_paid_cad": 0, "hst_paid_cad": 0,
            "personal_use_amount_cad": 15.0,  # business 85%
        }
        lines = _build_expense_charge_lines(org_id, user_id, exp)
        by = _num_by_id(org_id)
        debits = {by[l["account_id"]]: l["debit"] for l in lines if l["debit"] > 0}
        assert debits["1200"] == 4.25           # CTI limité à 85% de 5.00
        assert debits["1300"] == 15.0           # portion perso
        assert debits["5050"] == 80.75          # 100 - 15 - 4.25
        assert _sum(lines, "debit") == _sum(lines, "credit") == 100.0

    def test_off_100pct_no_shareholder_line(self, temp_org):
        org_id, user_id = temp_org
        exp = {
            "id": "e3", "amount_cad": 80.0, "category_code": "telecom_cell",
            "gst_paid_cad": 0, "qst_paid_cad": 0, "hst_paid_cad": 0,
            "personal_use_amount_cad": 0.0,  # OFF -> 100% affaires
        }
        lines = _build_expense_charge_lines(org_id, user_id, exp)
        by = _num_by_id(org_id)
        nums = {by[l["account_id"]] for l in lines}
        assert "1300" not in nums                # aucune ligne actionnaire
        debits = {by[l["account_id"]]: l["debit"] for l in lines if l["debit"] > 0}
        assert debits["5050"] == 80.0
        assert _sum(lines, "debit") == _sum(lines, "credit") == 80.0

    def test_balance_holds_on_odd_amounts(self, temp_org):
        org_id, user_id = temp_org
        exp = {
            "id": "e4", "amount_cad": 77.77, "category_code": "telecom_internet",
            "gst_paid_cad": 3.33, "qst_paid_cad": 6.64, "hst_paid_cad": 0,
            "personal_use_amount_cad": 23.33,  # business ~70%
        }
        lines = _build_expense_charge_lines(org_id, user_id, exp)
        assert _sum(lines, "debit") == _sum(lines, "credit") == 77.77  # équilibre exact

    # ── Garde-fous ajoutés suite à la revue adversariale ──
    def test_personal_exceeds_amount_is_clamped(self, temp_org):
        # Donnée aberrante (édition DB) : personal > amount. Doit être plafonné → équilibre tenu.
        org_id, user_id = temp_org
        exp = {"id": "e5", "amount_cad": 80.0, "category_code": "telecom_cell",
               "gst_paid_cad": 0, "qst_paid_cad": 0, "hst_paid_cad": 0,
               "personal_use_amount_cad": 200.0}
        lines = _build_expense_charge_lines(org_id, user_id, exp)
        assert _sum(lines, "debit") == _sum(lines, "credit") == 80.0
        assert all(l["debit"] >= 0 and l["credit"] >= 0 for l in lines)

    def test_taxes_near_full_amount_still_balances(self, temp_org):
        # Taxes ≈ 100 % du montant : charge_b tendrait vers négatif → rognage des taxes, équilibre tenu.
        org_id, user_id = temp_org
        exp = {"id": "e6", "amount_cad": 1.00, "category_code": "telecom_cell",
               "gst_paid_cad": 0.56, "qst_paid_cad": 0.55, "hst_paid_cad": 0,
               "personal_use_amount_cad": 0.09}
        lines = _build_expense_charge_lines(org_id, user_id, exp)
        assert _sum(lines, "debit") == _sum(lines, "credit") == 1.00
        assert all(l["debit"] >= 0 and l["credit"] >= 0 for l in lines)

    def test_offset_pointing_to_expense_account_falls_back_to_1300(self, temp_org):
        # Réglage piégé : offset vers un compte de CHARGE (5050) → la portion perso doit
        # basculer sur 1300 (actif), jamais sur une charge déductible.
        org_id, user_id = temp_org
        db.company_settings.insert_one({
            "organization_id": org_id, "telecom_personal_offset_account": "5050"})
        try:
            exp = {"id": "e7", "amount_cad": 100.0, "category_code": "telecom_internet",
                   "gst_paid_cad": 0, "qst_paid_cad": 0, "hst_paid_cad": 0,
                   "personal_use_amount_cad": 15.0}
            lines = _build_expense_charge_lines(org_id, user_id, exp)
            by = _num_by_id(org_id)
            personal_line = next(l for l in lines if l["debit"] == 15.0)
            assert by[personal_line["account_id"]] == "1300"   # pas 5050
            assert _sum(lines, "debit") == _sum(lines, "credit") == 100.0
        finally:
            db.company_settings.delete_many({"organization_id": org_id})
