"""Tests unitaires pour les helpers de numéros de taxes."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub env vars before importing server (which reads them at module load)
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "facturepro_test_unit")
os.environ.setdefault("JWT_SECRET", "test")

import pytest
from pymongo import MongoClient

from server import normalize_tax_number, check_tax_number, TAX_FORMATS


@pytest.fixture
def test_db():
    """Fournit une DB MongoDB de test isolée. Drop à la fin."""
    client = MongoClient("mongodb://localhost:27017")
    db_name = "facturepro_test_migration"
    db = client[db_name]
    yield db
    client.drop_database(db_name)


class TestNormalizeTaxNumber:
    def test_strip_whitespace(self):
        assert normalize_tax_number("  123456789  ") == "123456789"

    def test_remove_internal_spaces(self):
        assert normalize_tax_number("123 456 789") == "123456789"

    def test_remove_dashes(self):
        assert normalize_tax_number("123-456-789-RT-0001") == "123456789RT0001"

    def test_uppercase(self):
        assert normalize_tax_number("123456789rt0001") == "123456789RT0001"

    def test_combined(self):
        assert normalize_tax_number("  123 456 789-rt-0001  ") == "123456789RT0001"

    def test_idempotent(self):
        x = "123456789RT0001"
        assert normalize_tax_number(normalize_tax_number(x)) == x

    def test_none_tolerated(self):
        assert normalize_tax_number(None) == ""

    def test_empty(self):
        assert normalize_tax_number("") == ""


class TestCheckTaxNumber:
    def test_empty_is_valid(self):
        result = check_tax_number("", "bn")
        assert result["valid"] is True
        assert result["expected"] == ""

    def test_bn_valid_9_digits(self):
        result = check_tax_number("123456789", "bn")
        assert result["valid"] is True
        assert result["expected"] == "9 chiffres"

    def test_bn_invalid_too_short(self):
        result = check_tax_number("12345", "bn")
        assert result["valid"] is False
        assert "9 chiffres" in result["expected"]

    def test_gst_valid_with_suffix(self):
        result = check_tax_number("123456789RT0001", "gst")
        assert result["valid"] is True

    def test_gst_invalid_missing_suffix(self):
        result = check_tax_number("123456789", "gst")
        assert result["valid"] is False
        assert "RT0001" in result["expected"]

    def test_qst_valid(self):
        result = check_tax_number("1234567890TQ0001", "qst")
        assert result["valid"] is True

    def test_qst_invalid(self):
        result = check_tax_number("123456789", "qst")
        assert result["valid"] is False

    def test_hst_valid(self):
        result = check_tax_number("123456789RT0001", "hst")
        assert result["valid"] is True

    def test_neq_valid_10_digits(self):
        result = check_tax_number("1234567890", "neq")
        assert result["valid"] is True

    def test_neq_invalid_9_digits(self):
        result = check_tax_number("123456789", "neq")
        assert result["valid"] is False

    def test_unknown_kind_raises(self):
        import pytest
        with pytest.raises(ValueError, match="Unknown tax kind"):
            check_tax_number("123", "unknown")


class TestTaxFormats:
    def test_all_keys_present(self):
        assert set(TAX_FORMATS.keys()) == {"bn", "gst", "qst", "hst", "neq"}

    def test_each_format_is_tuple_of_2(self):
        for kind, (pattern, hint) in TAX_FORMATS.items():
            assert isinstance(pattern, str)
            assert isinstance(hint, str)


class TestMigration:
    def test_migrates_pst_to_qst(self, test_db):
        from server import migrate_pst_to_qst
        test_db.company_settings.insert_one({"user_id": "u1", "pst_number": "test1"})
        migrate_pst_to_qst(test_db)
        doc = test_db.company_settings.find_one({"user_id": "u1"})
        assert doc["qst_number"] == "test1"
        assert "pst_number" not in doc

    def test_idempotent(self, test_db):
        from server import migrate_pst_to_qst
        test_db.company_settings.insert_one({"user_id": "u1", "pst_number": "x"})
        migrate_pst_to_qst(test_db)
        doc_after_first = test_db.company_settings.find_one({"user_id": "u1"})
        migrate_pst_to_qst(test_db)
        doc_after_second = test_db.company_settings.find_one({"user_id": "u1"})
        assert doc_after_first == doc_after_second

    def test_skips_when_qst_already_exists(self, test_db):
        from server import migrate_pst_to_qst
        # Doc with both: should not overwrite qst
        test_db.company_settings.insert_one({"user_id": "u1", "pst_number": "old", "qst_number": "new"})
        migrate_pst_to_qst(test_db)
        doc = test_db.company_settings.find_one({"user_id": "u1"})
        assert doc["qst_number"] == "new"
        # pst_number left untouched in this corner case
        assert doc.get("pst_number") == "old"

    def test_skips_when_no_pst(self, test_db):
        from server import migrate_pst_to_qst
        test_db.company_settings.insert_one({"user_id": "u1", "qst_number": "x"})
        migrate_pst_to_qst(test_db)
        doc = test_db.company_settings.find_one({"user_id": "u1"})
        assert doc["qst_number"] == "x"
