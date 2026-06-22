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
