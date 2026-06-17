"""Tests unitaires pour le rapport TPS/TVQ (feature #4)."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "facturepro_test_unit")
os.environ.setdefault("JWT_SECRET", "test")

from server import _compute_taxes_paid, _quarter_to_dates, PROVINCES_VALID


class TestComputeTaxesPaid:
    def test_qc_on_114_975(self):
        # 114.975 brut = 100 net + 5 TPS + 9.975 TVQ
        result = _compute_taxes_paid(114.975, "QC")
        assert result["gst"] == 5.00
        # 9.975 rounded to 2 decimals can be 9.97 or 9.98 depending on float repr
        assert result["qst"] in (9.97, 9.98)
        assert result["hst"] == 0

    def test_qc_zero_amount(self):
        result = _compute_taxes_paid(0, "QC")
        assert result == {"gst": 0, "qst": 0, "hst": 0}

    def test_qc_none_amount(self):
        result = _compute_taxes_paid(None, "QC")
        assert result == {"gst": 0, "qst": 0, "hst": 0}

    def test_qc_negative_amount(self):
        result = _compute_taxes_paid(-50, "QC")
        assert result == {"gst": 0, "qst": 0, "hst": 0}

    def test_on_on_113(self):
        # 113 brut = 100 net + 13 TVH
        result = _compute_taxes_paid(113, "ON")
        assert result["gst"] == 0
        assert result["qst"] == 0
        assert result["hst"] == 13.00

    def test_nb_on_115(self):
        # 115 brut = 100 net + 15 TVH (Maritimes)
        result = _compute_taxes_paid(115, "NB")
        assert result["hst"] == 15.00
        assert result["gst"] == 0

    def test_ns_on_115(self):
        assert _compute_taxes_paid(115, "NS")["hst"] == 15.00

    def test_pe_on_115(self):
        assert _compute_taxes_paid(115, "PE")["hst"] == 15.00

    def test_nl_on_115(self):
        assert _compute_taxes_paid(115, "NL")["hst"] == 15.00

    def test_bc_on_105(self):
        # 105 brut = 100 net + 5 TPS (BC : la PST n'est pas tracée comme CTI)
        result = _compute_taxes_paid(105, "BC")
        assert result["gst"] == 5.00
        assert result["qst"] == 0
        assert result["hst"] == 0

    def test_ab_on_105(self):
        assert _compute_taxes_paid(105, "AB")["gst"] == 5.00

    def test_unknown_province_falls_back_to_gst_only(self):
        result = _compute_taxes_paid(105, "ZZ")
        assert result == {"gst": 5.00, "qst": 0, "hst": 0}


class TestQuarterToDates:
    def test_q1(self):
        assert _quarter_to_dates("2026", "Q1") == ("2026-01-01", "2026-03-31")

    def test_q2(self):
        assert _quarter_to_dates("2026", "Q2") == ("2026-04-01", "2026-06-30")

    def test_q3(self):
        assert _quarter_to_dates("2026", "Q3") == ("2026-07-01", "2026-09-30")

    def test_q4(self):
        assert _quarter_to_dates("2026", "Q4") == ("2026-10-01", "2026-12-31")

    def test_year_2025(self):
        assert _quarter_to_dates("2025", "Q1") == ("2025-01-01", "2025-03-31")


class TestProvincesValid:
    def test_contains_qc_on(self):
        assert "QC" in PROVINCES_VALID
        assert "ON" in PROVINCES_VALID

    def test_contains_all_13(self):
        expected = {
            "QC", "ON", "BC", "AB", "SK", "MB",
            "NB", "NS", "PE", "NL", "YT", "NU", "NT",
        }
        assert set(PROVINCES_VALID) == expected
