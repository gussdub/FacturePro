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
