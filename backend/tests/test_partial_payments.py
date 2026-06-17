"""Tests unitaires pour les paiements partiels (feature #6)."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "facturepro_test_unit")
os.environ.setdefault("JWT_SECRET", "test")

from server import _recompute_invoice_status, _enrich_invoice


class TestRecomputeInvoiceStatus:
    def test_no_payments_keeps_sent(self):
        inv = {"total": 100, "payments": [], "status": "sent"}
        assert _recompute_invoice_status(inv) == "sent"

    def test_no_payments_keeps_overdue(self):
        inv = {"total": 100, "payments": [], "status": "overdue"}
        assert _recompute_invoice_status(inv) == "overdue"

    def test_full_payment_returns_paid(self):
        inv = {"total": 100, "payments": [{"amount_cad": 100}], "status": "sent"}
        assert _recompute_invoice_status(inv) == "paid"

    def test_partial_payment_returns_partial(self):
        inv = {"total": 100, "payments": [{"amount_cad": 50}], "status": "sent"}
        assert _recompute_invoice_status(inv) == "partial"

    def test_multiple_payments_summing_to_total(self):
        inv = {"total": 100, "payments": [{"amount_cad": 60}, {"amount_cad": 40}], "status": "partial"}
        assert _recompute_invoice_status(inv) == "paid"

    def test_over_payment_returns_paid(self):
        inv = {"total": 100, "payments": [{"amount_cad": 150}], "status": "sent"}
        assert _recompute_invoice_status(inv) == "paid"

    def test_zero_total_keeps_status(self):
        inv = {"total": 0, "payments": [], "status": "sent"}
        assert _recompute_invoice_status(inv) == "sent"

    def test_missing_payments_field_treated_as_empty(self):
        inv = {"total": 100, "status": "sent"}
        assert _recompute_invoice_status(inv) == "sent"


class TestEnrichInvoice:
    def test_no_payments_outstanding_equals_total(self):
        inv = {"total": 100, "payments": []}
        result = _enrich_invoice(inv)
        assert result["total_paid_cad"] == 0
        assert result["outstanding_cad"] == 100

    def test_with_payments(self):
        inv = {"total": 100, "payments": [{"amount_cad": 30}, {"amount_cad": 20}]}
        result = _enrich_invoice(inv)
        assert result["total_paid_cad"] == 50
        assert result["outstanding_cad"] == 50

    def test_over_payment_clamps_outstanding_to_zero(self):
        inv = {"total": 100, "payments": [{"amount_cad": 150}]}
        result = _enrich_invoice(inv)
        assert result["outstanding_cad"] == 0

    def test_missing_payments_field(self):
        inv = {"total": 100}
        result = _enrich_invoice(inv)
        assert result["total_paid_cad"] == 0
        assert result["outstanding_cad"] == 100

    def test_returns_same_dict(self):
        inv = {"total": 100, "payments": []}
        result = _enrich_invoice(inv)
        # Mutation in-place : le doc original est aussi mis à jour
        assert result is inv
        assert inv["total_paid_cad"] == 0
