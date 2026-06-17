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
