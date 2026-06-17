"""Tests unitaires pour le rapport P&L (feature #5)."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "facturepro_test_unit")
os.environ.setdefault("JWT_SECRET", "test")

from server import _compute_compare_period, _pct_delta


class TestComputeComparePeriod:
    def test_none_returns_none(self):
        assert _compute_compare_period("2026-04-01", "2026-06-30", "none") is None

    def test_invalid_mode_returns_none(self):
        assert _compute_compare_period("2026-04-01", "2026-06-30", "garbage") is None

    def test_previous_q2_to_q1(self):
        result = _compute_compare_period("2026-04-01", "2026-06-30", "previous")
        assert result == ("2026-01-01", "2026-03-31")

    def test_previous_single_day(self):
        result = _compute_compare_period("2026-06-15", "2026-06-15", "previous")
        assert result == ("2026-06-14", "2026-06-14")

    def test_prior_year(self):
        assert _compute_compare_period("2026-04-01", "2026-06-30", "prior_year") == \
            ("2025-04-01", "2025-06-30")

    def test_prior_year_leap_day(self):
        result = _compute_compare_period("2024-02-29", "2024-02-29", "prior_year")
        assert result == ("2023-02-28", "2023-02-28")

    def test_invalid_date_returns_none(self):
        assert _compute_compare_period("not-a-date", "2026-06-30", "previous") is None
        assert _compute_compare_period("2026-06-30", "also-bad", "prior_year") is None


class TestPctDelta:
    def test_positive_growth(self):
        assert _pct_delta(100, 120) == 20.0

    def test_negative_growth(self):
        assert _pct_delta(100, 80) == -20.0

    def test_no_change(self):
        assert _pct_delta(100, 100) == 0.0

    def test_zero_previous_nonzero_current(self):
        assert _pct_delta(0, 50) == 100.0

    def test_zero_previous_zero_current(self):
        assert _pct_delta(0, 0) == 0.0

    def test_negative_previous(self):
        # Convention : la formule (current - previous) / previous * 100
        # avec previous négatif inverse le signe du résultat.
        # (100 - (-50)) / -50 * 100 = -300.0
        assert _pct_delta(-50, 100) == -300.0


import pytest
from pymongo import MongoClient
import uuid


@pytest.fixture
def isolated_db():
    """DB isolée pour tester _aggregate_pnl avec données contrôlées."""
    client = MongoClient("mongodb://localhost:27017")
    db_name = f"facturepro_test_pnl_{uuid.uuid4().hex[:8]}"
    yield client[db_name]
    client.drop_database(db_name)


def _seed_for_aggregate(test_db, user_id):
    """Seed : 2 invoices paid, 1 invoice sent, 1 invoice draft + 3 expenses dans 3 catégories."""
    test_db.invoices.insert_many([
        {"id": "i1", "user_id": user_id, "subtotal": 1000, "currency": "CAD",
         "exchange_rate_to_cad": 1.0, "status": "paid", "issue_date": "2099-04-15"},
        {"id": "i2", "user_id": user_id, "subtotal": 2000, "currency": "CAD",
         "exchange_rate_to_cad": 1.0, "status": "paid", "issue_date": "2099-05-10"},
        {"id": "i3", "user_id": user_id, "subtotal": 500, "currency": "CAD",
         "exchange_rate_to_cad": 1.0, "status": "sent", "issue_date": "2099-06-01"},
        {"id": "i4", "user_id": user_id, "subtotal": 5000, "currency": "CAD",
         "exchange_rate_to_cad": 1.0, "status": "draft", "issue_date": "2099-04-20"},
    ])
    test_db.expenses.insert_many([
        {"id": "e1", "user_id": user_id, "amount_cad": 200,
         "category_code": "office_expenses", "deductible_amount": 200,
         "expense_date": "2099-04-10"},
        {"id": "e2", "user_id": user_id, "amount_cad": 300,
         "category_code": "meals_entertainment", "deductible_amount": 150,
         "expense_date": "2099-05-15"},
        {"id": "e3", "user_id": user_id, "amount_cad": 150,
         "category_code": "rent", "deductible_amount": 150,
         "expense_date": "2099-06-20"},
    ])


class TestAggregatePnl:
    """Tests qui hit la DB locale (via monkey-patch de la global `db`)."""

    def test_accrual_includes_sent_paid_overdue(self, isolated_db, monkeypatch):
        import server
        monkeypatch.setattr(server, "db", isolated_db)
        _seed_for_aggregate(isolated_db, "u1")
        result = server._aggregate_pnl("u1", "2099-04-01", "2099-06-30", "accrual")
        # 2 paid + 1 sent = 3500 (draft exclu)
        assert result["revenue"] == 3500.00
        assert result["invoice_count"] == 3
        assert result["expense_count"] == 3

    def test_cash_only_paid(self, isolated_db, monkeypatch):
        import server
        monkeypatch.setattr(server, "db", isolated_db)
        _seed_for_aggregate(isolated_db, "u1")
        result = server._aggregate_pnl("u1", "2099-04-01", "2099-06-30", "cash")
        # 2 paid uniquement
        assert result["revenue"] == 3000.00
        assert result["invoice_count"] == 2

    def test_expense_groups_structure(self, isolated_db, monkeypatch):
        import server
        monkeypatch.setattr(server, "db", isolated_db)
        _seed_for_aggregate(isolated_db, "u1")
        result = server._aggregate_pnl("u1", "2099-04-01", "2099-06-30", "accrual")
        groups = {g["group"]: g for g in result["expense_groups"]}
        assert "office" in groups
        office_cats = [c["code"] for c in groups["office"]["categories"]]
        assert "office_expenses" in office_cats
        assert "marketing" in groups
        meals = next(c for c in groups["marketing"]["categories"] if c["code"] == "meals_entertainment")
        assert meals["gross"] == 300.00
        assert meals["deductible"] == 150.00
        assert "premises" in groups

    def test_totals(self, isolated_db, monkeypatch):
        import server
        monkeypatch.setattr(server, "db", isolated_db)
        _seed_for_aggregate(isolated_db, "u1")
        result = server._aggregate_pnl("u1", "2099-04-01", "2099-06-30", "accrual")
        assert result["total_expenses"]["gross"] == 650.00
        assert result["total_expenses"]["deductible"] == 500.00
        assert result["net_income"]["management"] == 2850.00
        assert result["net_income"]["taxable"] == 3000.00

    def test_empty_period(self, isolated_db, monkeypatch):
        import server
        monkeypatch.setattr(server, "db", isolated_db)
        result = server._aggregate_pnl("u1", "2020-01-01", "2020-01-31", "accrual")
        assert result["revenue"] == 0
        assert result["total_expenses"] == {"gross": 0, "deductible": 0}
        assert result["net_income"] == {"management": 0, "taxable": 0}
        assert result["expense_groups"] == []
        assert result["invoice_count"] == 0
        assert result["expense_count"] == 0
