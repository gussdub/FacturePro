import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uuid
import pytest
from datetime import datetime, timezone

from server import (
    ACCOUNT_TYPES,
    ACCOUNT_NUMBER_RANGES,
    DEFAULT_BASE_ACCOUNTS,
    EXPENSE_ACCOUNT_NUMBERS,
    _normal_balance_for_type,
    _account_type_for_number,
    _build_default_accounts,
    EXPENSE_CATEGORIES,
)


class TestAccountConstants:
    def test_five_account_types(self):
        assert set(ACCOUNT_TYPES) == {"asset", "liability", "equity", "revenue", "expense"}

    def test_ranges_cover_five_types(self):
        assert ACCOUNT_NUMBER_RANGES["asset"] == (1000, 1999)
        assert ACCOUNT_NUMBER_RANGES["liability"] == (2000, 2999)
        assert ACCOUNT_NUMBER_RANGES["equity"] == (3000, 3999)
        assert ACCOUNT_NUMBER_RANGES["revenue"] == (4000, 4999)
        assert ACCOUNT_NUMBER_RANGES["expense"] == (5000, 5999)


class TestNormalBalance:
    def test_asset_and_expense_are_debit(self):
        assert _normal_balance_for_type("asset") == "debit"
        assert _normal_balance_for_type("expense") == "debit"

    def test_liability_equity_revenue_are_credit(self):
        for t in ("liability", "equity", "revenue"):
            assert _normal_balance_for_type(t) == "credit"


class TestAccountTypeForNumber:
    def test_ranges(self):
        assert _account_type_for_number("1000") == "asset"
        assert _account_type_for_number("2100") == "liability"
        assert _account_type_for_number("3200") == "equity"
        assert _account_type_for_number("4000") == "revenue"
        assert _account_type_for_number("5900") == "expense"

    def test_out_of_range_returns_none(self):
        assert _account_type_for_number("6000") is None
        assert _account_type_for_number("999") is None
        assert _account_type_for_number("abcd") is None


class TestBuildDefaultAccounts:
    def test_total_29_accounts(self):
        accounts = _build_default_accounts("org-x", "user-x")
        assert len(accounts) == 29  # 12 base + 17 dépenses

    def test_all_scoped_and_system(self):
        accounts = _build_default_accounts("org-x", "user-x")
        for a in accounts:
            assert a["organization_id"] == "org-x"
            assert a["created_by_user_id"] == "user-x"
            assert a["is_system"] is True
            assert a["is_active"] is True

    def test_numbers_unique(self):
        accounts = _build_default_accounts("org-x", "user-x")
        numbers = [a["account_number"] for a in accounts]
        assert len(numbers) == len(set(numbers))

    def test_normal_balance_matches_type(self):
        accounts = _build_default_accounts("org-x", "user-x")
        for a in accounts:
            assert a["normal_balance"] == _normal_balance_for_type(a["account_type"])
            derived = _account_type_for_number(a["account_number"])
            assert a["account_type"] == derived

    def test_expense_accounts_mapped_to_17_categories(self):
        accounts = _build_default_accounts("org-x", "user-x")
        mapped = {a["expense_category_code"] for a in accounts if a.get("expense_category_code")}
        catalogue = {c["code"] for c in EXPENSE_CATEGORIES if c["code"] != "other"}
        assert mapped == catalogue  # les 17 catégories hors "other"

    def test_base_accounts_include_cash_and_owner_contribution(self):
        accounts = _build_default_accounts("org-x", "user-x")
        by_number = {a["account_number"]: a for a in accounts}
        assert by_number["1000"]["name"] == "Encaisse"
        assert by_number["3100"]["name"] == "Apport du propriétaire"
        assert by_number["4000"]["account_type"] == "revenue"
