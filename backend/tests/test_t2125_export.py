import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from server import T2125_LINE_LABELS, EXPENSE_CATEGORIES, T2125_LABEL_TABLE_TAX_YEAR


class TestT2125LineLabels:
    def test_label_table_year_constant_present(self):
        assert T2125_LABEL_TABLE_TAX_YEAR == 2024

    def test_known_line(self):
        assert T2125_LINE_LABELS["8520"] == "Publicité et promotion"
        assert T2125_LINE_LABELS["8523"] == "Repas et représentation"
        assert T2125_LINE_LABELS["9945"] == "Frais d'utilisation de la résidence aux fins de l'entreprise"

    def test_all_expense_categories_arc_lines_covered(self):
        """Toute arc_line non-vide dans EXPENSE_CATEGORIES doit avoir un libellé.
        Test de régression : ajouter une catégorie sans libellé doit faire échouer."""
        missing = []
        for cat in EXPENSE_CATEGORIES:
            arc_line = cat.get("arc_line") or ""
            if arc_line and arc_line not in T2125_LINE_LABELS:
                missing.append((cat["code"], arc_line))
        assert not missing, f"Catégories avec arc_line non couverte : {missing}"

    def test_9270_other_fallback_present(self):
        # Catégorie 'other' (arc_line="") tombe sur 9270 via _t2125_flatten_pnl_expenses
        assert "9270" in T2125_LINE_LABELS
        assert T2125_LINE_LABELS["9270"] == "Autres dépenses"


from server import _t2125_flatten_pnl_expenses


class TestFlattenPnlExpenses:
    def test_empty_groups(self):
        assert _t2125_flatten_pnl_expenses([]) == {}

    def test_none_groups(self):
        assert _t2125_flatten_pnl_expenses(None) == {}

    def test_basic_flatten(self):
        groups = [
            {"group": "office", "categories": [
                {"code": "office_expenses", "arc_line": "8810",
                 "gross": 1200.0, "deductible": 1200.0},
                {"code": "office_supplies", "arc_line": "8811",
                 "gross": 600.0, "deductible": 600.0},
            ]},
            {"group": "marketing", "categories": [
                {"code": "advertising", "arc_line": "8520",
                 "gross": 1500.0, "deductible": 1500.0},
            ]},
        ]
        flat = _t2125_flatten_pnl_expenses(groups)
        assert set(flat.keys()) == {"office_expenses", "office_supplies", "advertising"}
        assert flat["office_expenses"]["gross"] == 1200.0
        assert flat["office_expenses"]["arc_line"] == "8810"
        assert flat["advertising"]["deductible"] == 1500.0

    def test_other_category_empty_arc_line_falls_back_to_9270(self):
        groups = [{"group": "other", "categories": [
            {"code": "other", "arc_line": "", "gross": 50.0, "deductible": 50.0},
        ]}]
        flat = _t2125_flatten_pnl_expenses(groups)
        assert flat["other"]["arc_line"] == "9270"

    def test_missing_arc_line_falls_back_to_9270(self):
        groups = [{"group": "x", "categories": [
            {"code": "weird", "gross": 10.0, "deductible": 10.0},
        ]}]
        flat = _t2125_flatten_pnl_expenses(groups)
        assert flat["weird"]["arc_line"] == "9270"

    def test_gross_none_becomes_zero(self):
        groups = [{"group": "x", "categories": [
            {"code": "x", "arc_line": "8810", "gross": None, "deductible": None},
        ]}]
        flat = _t2125_flatten_pnl_expenses(groups)
        assert flat["x"]["gross"] == 0.0
        assert flat["x"]["deductible"] == 0.0


from server import _t2125_group_by_arc_line


class TestGroupByArcLine:
    def test_empty_flat(self):
        assert _t2125_group_by_arc_line({}) == []

    def test_basic_grouping(self):
        flat = {
            "advertising": {"gross": 1500.0, "deductible": 1500.0, "arc_line": "8520"},
            "meals_entertainment": {"gross": 2400.0, "deductible": 1200.0, "arc_line": "8523"},
            "office_expenses": {"gross": 1200.0, "deductible": 1200.0, "arc_line": "8810"},
        }
        out = _t2125_group_by_arc_line(flat)
        assert len(out) == 3
        # Trié par arc_line croissant
        assert [line["arc_line"] for line in out] == ["8520", "8523", "8810"]
        line_8523 = next(l for l in out if l["arc_line"] == "8523")
        assert line_8523["gross"] == 2400.0
        assert line_8523["deductible"] == 1200.0
        assert line_8523["note"] == "50 % déductible"

    def test_label_from_table(self):
        flat = {"advertising": {"gross": 100.0, "deductible": 100.0, "arc_line": "8520"}}
        out = _t2125_group_by_arc_line(flat)
        assert out[0]["label"] == "Publicité et promotion"

    def test_unknown_arc_line_label_fallback(self):
        flat = {"x": {"gross": 10.0, "deductible": 10.0, "arc_line": "9999"}}
        out = _t2125_group_by_arc_line(flat)
        assert out[0]["label"] == "Autres dépenses"

    def test_exclude_codes(self):
        flat = {
            "rent": {"gross": 12000.0, "deductible": 12000.0, "arc_line": "8910"},
            "advertising": {"gross": 500.0, "deductible": 500.0, "arc_line": "8520"},
        }
        out = _t2125_group_by_arc_line(flat, exclude_codes={"rent"})
        assert len(out) == 1
        assert out[0]["arc_line"] == "8520"

    def test_multiple_categories_same_arc_line_summed(self):
        # Fixture custom (n'existe pas dans EXPENSE_CATEGORIES actuel mais teste la logique)
        flat = {
            "cat_a": {"gross": 100.0, "deductible": 100.0, "arc_line": "9999"},
            "cat_b": {"gross": 50.0, "deductible": 50.0, "arc_line": "9999"},
        }
        out = _t2125_group_by_arc_line(flat)
        assert len(out) == 1
        assert out[0]["gross"] == 150.0
        assert set(out[0]["categories"]) == {"cat_a", "cat_b"}

    def test_exclude_codes_none(self):
        flat = {"advertising": {"gross": 500.0, "deductible": 500.0, "arc_line": "8520"}}
        # exclude_codes None ne doit pas crasher
        out = _t2125_group_by_arc_line(flat, exclude_codes=None)
        assert len(out) == 1


from server import (
    _t2125_compute_home_office_adjustment,
    _t2125_compute_vehicle_adjustment,
)


class TestHomeOfficeAdjustment:
    def _flat(self):
        return {
            "rent": {"gross": 12000.0, "deductible": 12000.0, "arc_line": "8910"},
            "utilities": {"gross": 2000.0, "deductible": 2000.0, "arc_line": "9220"},
            "insurance": {"gross": 1000.0, "deductible": 1000.0, "arc_line": "8690"},
            "advertising": {"gross": 500.0, "deductible": 500.0, "arc_line": "8520"},  # exclu
        }

    def test_zero_returns_none(self):
        assert _t2125_compute_home_office_adjustment(self._flat(), 0) is None
        assert _t2125_compute_home_office_adjustment(self._flat(), 0.0) is None

    def test_negative_returns_none(self):
        assert _t2125_compute_home_office_adjustment(self._flat(), -5) is None

    def test_15_percent(self):
        adj = _t2125_compute_home_office_adjustment(self._flat(), 15)
        assert adj["percentage"] == 15
        assert adj["original_total"] == 15000.0  # 12000 + 2000 + 1000
        assert adj["deductible_amount"] == 2250.0  # 15000 × 15%
        assert adj["saved_to_arc_line"] == "9945"
        assert set(adj["applies_to"]) == {"rent", "utilities", "insurance"}

    def test_100_percent(self):
        adj = _t2125_compute_home_office_adjustment(self._flat(), 100)
        assert adj["deductible_amount"] == 15000.0

    def test_no_relevant_expenses(self):
        flat = {"advertising": {"gross": 500.0, "deductible": 500.0, "arc_line": "8520"}}
        adj = _t2125_compute_home_office_adjustment(flat, 15)
        assert adj["original_total"] == 0
        assert adj["deductible_amount"] == 0

    def test_applies_to_sorted(self):
        adj = _t2125_compute_home_office_adjustment(self._flat(), 15)
        assert adj["applies_to"] == sorted(adj["applies_to"])


class TestVehicleAdjustment:
    def _flat(self):
        return {
            "vehicle_expenses": {"gross": 5000.0, "deductible": 5000.0, "arc_line": "9281"},
            "advertising": {"gross": 500.0, "deductible": 500.0, "arc_line": "8520"},
        }

    def test_zero_returns_none(self):
        assert _t2125_compute_vehicle_adjustment(self._flat(), 0) is None

    def test_40_percent(self):
        adj = _t2125_compute_vehicle_adjustment(self._flat(), 40)
        assert adj["percentage"] == 40
        assert adj["original_total"] == 5000.0
        assert adj["deductible_amount"] == 2000.0
        assert adj["saved_to_arc_line"] == "9281"
        assert adj["applies_to"] == ["vehicle_expenses"]

    def test_no_vehicle_expenses(self):
        flat = {"advertising": {"gross": 500.0, "deductible": 500.0, "arc_line": "8520"}}
        adj = _t2125_compute_vehicle_adjustment(flat, 40)
        assert adj["original_total"] == 0
        assert adj["deductible_amount"] == 0


import uuid
from server import _build_t2125_report, db as server_db
from fastapi import HTTPException
from datetime import datetime, timezone


class TestBuildT2125Report:
    def _setup_settings(self, user_id, entity_type="sole_proprietor",
                       home_pct=0, vehicle_pct=0):
        server_db.company_settings.update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id, "entity_type": entity_type,
                "company_name": "Test Co",
                "bn_number": "123456789",
                "province": "QC",
                "home_office_percentage": home_pct,
                "vehicle_business_percentage": vehicle_pct,
            }},
            upsert=True,
        )

    def _cleanup_settings(self, user_id):
        server_db.company_settings.delete_one({"user_id": user_id})

    def test_year_too_low_raises_422(self):
        uid = f"test-t2125-{uuid.uuid4().hex[:8]}"
        self._setup_settings(uid)
        try:
            with pytest.raises(HTTPException) as exc:
                _build_t2125_report(uid, 1999, "accrual")
            assert exc.value.status_code == 422
        finally:
            self._cleanup_settings(uid)

    def test_year_too_high_raises_422(self):
        uid = f"test-t2125-{uuid.uuid4().hex[:8]}"
        self._setup_settings(uid)
        try:
            future = datetime.now(timezone.utc).year + 5
            with pytest.raises(HTTPException) as exc:
                _build_t2125_report(uid, future, "accrual")
            assert exc.value.status_code == 422
        finally:
            self._cleanup_settings(uid)

    def test_current_year_plus_one_allowed_for_timezone_buffer(self):
        uid = f"test-t2125-{uuid.uuid4().hex[:8]}"
        self._setup_settings(uid)
        try:
            yr = datetime.now(timezone.utc).year + 1
            report = _build_t2125_report(uid, yr, "accrual")
            assert report["year"] == yr
            assert report["is_partial_year"] is True
        finally:
            self._cleanup_settings(uid)

    def test_invalid_basis(self):
        uid = f"test-t2125-{uuid.uuid4().hex[:8]}"
        self._setup_settings(uid)
        try:
            with pytest.raises(HTTPException) as exc:
                _build_t2125_report(uid, 2099, "xxx")
            assert exc.value.status_code == 422
        finally:
            self._cleanup_settings(uid)

    def test_corporation_raises_422(self):
        uid = f"test-t2125-{uuid.uuid4().hex[:8]}"
        self._setup_settings(uid, entity_type="corporation")
        try:
            with pytest.raises(HTTPException) as exc:
                _build_t2125_report(uid, 2099, "accrual")
            assert exc.value.status_code == 422
        finally:
            self._cleanup_settings(uid)

    def test_no_settings_raises_422(self):
        uid = f"test-t2125-noset-{uuid.uuid4().hex[:8]}"
        valid_year = datetime.now(timezone.utc).year + 1
        # Pas de _setup_settings → settings absent
        with pytest.raises(HTTPException) as exc:
            _build_t2125_report(uid, valid_year, "accrual")
        assert exc.value.status_code == 422
        assert "Réglages" in exc.value.detail

    def test_empty_year_no_data(self):
        uid = f"test-t2125-{uuid.uuid4().hex[:8]}"
        valid_year = datetime.now(timezone.utc).year + 1
        self._setup_settings(uid)
        try:
            report = _build_t2125_report(uid, valid_year, "accrual")
            assert report["gross_income"] == 0
            assert report["expenses_by_arc_line"] == []
            assert report["total_expenses_deductible"] == 0
            assert report["net_income"] == 0
            assert report["business_use_adjustments"] == {}
        finally:
            self._cleanup_settings(uid)

    def test_report_structure(self):
        uid = f"test-t2125-{uuid.uuid4().hex[:8]}"
        valid_year = datetime.now(timezone.utc).year + 1
        self._setup_settings(uid)
        try:
            report = _build_t2125_report(uid, valid_year, "accrual")
            for key in ["year", "basis", "period", "entity_type", "province",
                        "company_name", "bn_number", "gross_income", "income_line",
                        "expenses_by_arc_line", "total_expenses_deductible",
                        "business_use_adjustments", "net_income", "net_income_line",
                        "is_partial_year"]:
                assert key in report, f"Missing key: {key}"
            assert report["income_line"] == "8000"
            assert report["net_income_line"] == "9369"
            assert report["period"] == {"start": f"{valid_year}-01-01", "end": f"{valid_year}-12-31"}
        finally:
            self._cleanup_settings(uid)


from server import _t2125_format_money


class TestT2125FormatMoney:
    def test_thousands_separator(self):
        # FR-CA: espace milliers, virgule décimale, $ après
        result = _t2125_format_money(85000.00)
        assert "$" in result
        assert "85" in result and "000" in result
        assert "," in result

    def test_zero(self):
        assert _t2125_format_money(0) == "0,00 $"

    def test_negative(self):
        result = _t2125_format_money(-1500.50)
        assert "1" in result and "500" in result and "50" in result
        assert result.startswith("-")

    def test_decimal_rounding(self):
        assert "12,35" in _t2125_format_money(12.347)
