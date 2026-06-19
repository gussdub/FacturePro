import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from server import (
    _sanitize_cell,
    _parse_csv_date,
    _normalize_amount,
    _compute_file_hash,
)


class TestSanitizeCell:
    def test_strip_equals(self):
        assert _sanitize_cell("=cmd|...") == "cmd|..."
    def test_strip_plus(self):
        assert _sanitize_cell("+33-1") == "33-1"
    def test_strip_minus(self):
        assert _sanitize_cell("-1234") == "1234"
    def test_strip_at(self):
        assert _sanitize_cell("@mention") == "mention"
    def test_strip_leading_tab(self):
        assert _sanitize_cell("\tdata") == "data"
    def test_preserves_leading_space_then_strips(self):
        assert _sanitize_cell("  =evil") == "evil"
    def test_normal_value(self):
        assert _sanitize_cell("hello world") == "hello world"
    def test_empty(self):
        assert _sanitize_cell("") == ""
    def test_none_safe(self):
        assert _sanitize_cell(None) == ""


class TestParseCsvDate:
    def test_iso(self):
        assert _parse_csv_date("2026-03-14", "YYYY-MM-DD") == "2026-03-14"
    def test_dmy(self):
        assert _parse_csv_date("14/03/2026", "DD/MM/YYYY") == "2026-03-14"
    def test_mdy(self):
        assert _parse_csv_date("03/14/2026", "MM/DD/YYYY") == "2026-03-14"
    def test_invalid(self):
        assert _parse_csv_date("not a date", "YYYY-MM-DD") is None
    def test_empty(self):
        assert _parse_csv_date("", "YYYY-MM-DD") is None
    def test_wrong_format(self):
        # 14/03/2026 parsed as MM/DD/YYYY → invalid (month 14)
        assert _parse_csv_date("14/03/2026", "MM/DD/YYYY") is None


class TestNormalizeAmount:
    def test_us(self):
        assert _normalize_amount("1,234.56") == 1234.56
    def test_eu(self):
        assert _normalize_amount("1 234,56") == 1234.56
    def test_nbsp(self):
        # non-breaking space U+00A0
        assert _normalize_amount("1 234,56") == 1234.56
    def test_negative(self):
        assert _normalize_amount("-99.50") == -99.50
    def test_plain_int(self):
        assert _normalize_amount("100") == 100.0
    def test_empty(self):
        assert _normalize_amount("") is None
    def test_invalid(self):
        assert _normalize_amount("abc") is None
    def test_only_dot(self):
        assert _normalize_amount("100.") == 100.0
    def test_only_comma_decimal(self):
        assert _normalize_amount("0,50") == 0.50


class TestComputeFileHash:
    def test_deterministic(self):
        a = _compute_file_hash(b"hello,world\n1,2\n")
        b = _compute_file_hash(b"hello,world\n1,2\n")
        assert a == b
        assert len(a) == 64  # sha256 hex
    def test_crlf_lf_same(self):
        a = _compute_file_hash(b"hello,world\r\n1,2\r\n")
        b = _compute_file_hash(b"hello,world\n1,2\n")
        assert a == b
    def test_different_content_different_hash(self):
        a = _compute_file_hash(b"x")
        b = _compute_file_hash(b"y")
        assert a != b


from server import _parse_csv_rows


class TestParseCsvRows:
    def _mapping(self, **overrides):
        m = {
            "delimiter": ",", "has_header": True,
            "date_column": 0, "date_format": "YYYY-MM-DD",
            "description_column": 1,
            "amount_mode": "single", "amount_column": 2,
            "debit_column": None, "credit_column": None,
            "sign_convention": "positive_is_credit",
        }
        m.update(overrides)
        return m

    def test_simple_csv(self):
        csv_text = "date,desc,amount\n2026-03-14,Costco,-127.84\n2026-03-15,Client X,250.00\n"
        rows = _parse_csv_rows(csv_text.encode(), self._mapping())
        assert len(rows) == 2
        assert rows[0]["date"] == "2026-03-14"
        assert rows[0]["description"] == "Costco"
        assert rows[0]["amount_cad"] == -127.84
        assert rows[0]["parse_error"] is False
        assert rows[1]["amount_cad"] == 250.00

    def test_no_header(self):
        csv_text = "2026-03-14,Costco,-100\n"
        rows = _parse_csv_rows(csv_text.encode(), self._mapping(has_header=False))
        assert len(rows) == 1
        assert rows[0]["description"] == "Costco"

    def test_semicolon_delimiter(self):
        csv_text = "date;desc;amount\n2026-03-14;Costco;-127.84\n"
        rows = _parse_csv_rows(csv_text.encode(), self._mapping(delimiter=";"))
        assert len(rows) == 1
        assert rows[0]["amount_cad"] == -127.84

    def test_eu_amount(self):
        csv_text = "date;desc;amount\n14/03/2026;Costco;-1 234,56\n"
        rows = _parse_csv_rows(csv_text.encode(),
                                self._mapping(delimiter=";",
                                              date_format="DD/MM/YYYY"))
        assert rows[0]["amount_cad"] == -1234.56

    def test_debit_credit_mode_credit(self):
        m = self._mapping(amount_mode="debit_credit", amount_column=None,
                          debit_column=2, credit_column=3)
        csv_text = "date,desc,debit,credit\n2026-03-14,Salary,,1500.00\n"
        rows = _parse_csv_rows(csv_text.encode(), m)
        assert rows[0]["amount_cad"] == 1500.00

    def test_debit_credit_mode_debit(self):
        m = self._mapping(amount_mode="debit_credit", amount_column=None,
                          debit_column=2, credit_column=3)
        csv_text = "date,desc,debit,credit\n2026-03-14,Fee,3.95,\n"
        rows = _parse_csv_rows(csv_text.encode(), m)
        assert rows[0]["amount_cad"] == -3.95

    def test_debit_credit_both_filled(self):
        m = self._mapping(amount_mode="debit_credit", amount_column=None,
                          debit_column=2, credit_column=3)
        csv_text = "date,desc,debit,credit\n2026-03-14,X,100,5\n"
        rows = _parse_csv_rows(csv_text.encode(), m)
        # credit - debit = 5 - 100 = -95
        assert rows[0]["amount_cad"] == -95.0

    def test_sign_convention_positive_is_debit(self):
        m = self._mapping(sign_convention="positive_is_debit")
        csv_text = "date,desc,amount\n2026-03-14,Costco,100\n"
        rows = _parse_csv_rows(csv_text.encode(), m)
        # positive in CSV → debit → amount_cad negative
        assert rows[0]["amount_cad"] == -100.0

    def test_skip_empty_rows(self):
        csv_text = "date,desc,amount\n2026-03-14,A,1\n\n2026-03-15,B,2\n"
        rows = _parse_csv_rows(csv_text.encode(), self._mapping())
        assert len(rows) == 2  # ligne vide ignorée
        assert rows[0]["description"] == "A"
        assert rows[1]["description"] == "B"

    def test_parse_error_invalid_date(self):
        csv_text = "date,desc,amount\nnot-a-date,X,100\n"
        rows = _parse_csv_rows(csv_text.encode(), self._mapping())
        assert rows[0]["parse_error"] is True
        assert rows[0]["date"] is None

    def test_parse_error_invalid_amount(self):
        csv_text = "date,desc,amount\n2026-03-14,X,foo\n"
        rows = _parse_csv_rows(csv_text.encode(), self._mapping())
        assert rows[0]["parse_error"] is True
        assert rows[0]["amount_cad"] is None

    def test_row_limit_5001(self):
        # 5001 data rows (+ header) doit lever ValueError
        lines = ["date,desc,amount"] + [f"2026-03-14,X,{i}" for i in range(5001)]
        csv_text = "\n".join(lines) + "\n"
        with pytest.raises(ValueError, match="row limit"):
            _parse_csv_rows(csv_text.encode(), self._mapping())

    def test_sanitization_applied(self):
        csv_text = "date,desc,amount\n2026-03-14,=cmd|attack,100\n"
        rows = _parse_csv_rows(csv_text.encode(), self._mapping())
        assert rows[0]["description"] == "cmd|attack"

    def test_raw_line_only_when_parse_error(self):
        csv_text = "date,desc,amount\n2026-03-14,Costco,100\nbad,X,nope\n"
        rows = _parse_csv_rows(csv_text.encode(), self._mapping())
        assert rows[0].get("raw_line") is None
        assert rows[1]["raw_line"] is not None
        assert "bad" in rows[1]["raw_line"]
