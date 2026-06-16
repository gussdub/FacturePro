"""Tests unitaires pour les catégories de dépenses ARC (feature #3)."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "facturepro_test_unit")
os.environ.setdefault("JWT_SECRET", "test")

from server import EXPENSE_CATEGORIES, EXPENSE_CATEGORY_GROUPS, _find_category


class TestExpenseCategoriesConstant:
    def test_has_18_entries(self):
        # 17 canoniques + "other"
        assert len(EXPENSE_CATEGORIES) == 18

    def test_each_entry_has_required_keys(self):
        required = {"code", "label_fr", "label_en", "arc_line", "deductible_percentage", "group"}
        for cat in EXPENSE_CATEGORIES:
            assert required.issubset(cat.keys()), f"Missing keys in {cat['code']}: {required - cat.keys()}"

    def test_each_code_is_unique(self):
        codes = [c["code"] for c in EXPENSE_CATEGORIES]
        assert len(codes) == len(set(codes)), "Duplicate code(s) detected"

    def test_meals_entertainment_is_50_percent(self):
        cat = _find_category("meals_entertainment")
        assert cat is not None
        assert cat["deductible_percentage"] == 50
        assert cat["arc_line"] == "8523"
        assert cat["group"] == "marketing"

    def test_office_expenses_is_100_percent(self):
        cat = _find_category("office_expenses")
        assert cat is not None
        assert cat["deductible_percentage"] == 100
        assert cat["arc_line"] == "8810"

    def test_other_category_present(self):
        cat = _find_category("other")
        assert cat is not None
        assert cat["arc_line"] == ""
        assert cat["deductible_percentage"] == 100
        assert cat["group"] == "other"

    def test_all_non_meals_are_100_percent(self):
        for cat in EXPENSE_CATEGORIES:
            if cat["code"] != "meals_entertainment":
                assert cat["deductible_percentage"] == 100, f"{cat['code']} should be 100%"

    def test_groups_are_known(self):
        valid_groups = set(EXPENSE_CATEGORY_GROUPS.keys())
        for cat in EXPENSE_CATEGORIES:
            assert cat["group"] in valid_groups, f"{cat['code']} has unknown group {cat['group']}"


class TestExpenseCategoryGroups:
    def test_has_6_groups(self):
        assert set(EXPENSE_CATEGORY_GROUPS.keys()) == {
            "office", "marketing", "premises", "travel", "personnel", "other"
        }

    def test_french_labels(self):
        assert EXPENSE_CATEGORY_GROUPS["marketing"] == "Marketing"
        assert EXPENSE_CATEGORY_GROUPS["other"] == "Autre"


class TestFindCategory:
    def test_returns_dict_for_canonical_code(self):
        cat = _find_category("rent")
        assert cat["label_fr"] == "Loyer"
        assert cat["arc_line"] == "8910"

    def test_returns_none_for_unknown(self):
        assert _find_category("definitely_not_a_real_code") is None

    def test_returns_none_for_empty(self):
        assert _find_category("") is None

    def test_returns_none_for_none(self):
        assert _find_category(None) is None
