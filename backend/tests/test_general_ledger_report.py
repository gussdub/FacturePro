"""Tests — rapport de grand livre (par compte + général) et exports PDF/CSV (feature #7.11)."""
import os
import sys
import uuid as _uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")
os.environ.setdefault("DB_NAME", "facturepro")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from backend.server import (  # noqa: E402
    app, db, _build_default_accounts,
    _general_ledger_report, _render_general_ledger_csv, _render_general_ledger_pdf,
)

client = TestClient(app)


@pytest.fixture()
def org():
    org_id = f"TESTORG-GLR-{_uuid.uuid4()}"
    accts = _build_default_accounts(org_id, "u1")
    db.chart_of_accounts.insert_many([dict(a) for a in accts])
    by_num = {a["account_number"]: a for a in accts}

    def je(num, date, dr, cr, amt):
        return {"id": str(_uuid.uuid4()), "organization_id": org_id, "entry_number": num,
                "entry_date": date, "status": "posted", "entry_type": "manual",
                "description": f"Test {num}", "reverses_entry_id": None,
                "reversed_by_entry_id": None,
                "lines": [
                    {"account_id": dr["id"], "account_number": dr["account_number"],
                     "debit": amt, "credit": 0.0},
                    {"account_id": cr["id"], "account_number": cr["account_number"],
                     "debit": 0.0, "credit": amt},
                ]}
    db.journal_entries.insert_many([
        je("JE-1", "2026-01-15", by_num["5040"], by_num["1000"], 100.0),
        je("JE-2", "2026-03-15", by_num["5040"], by_num["1000"], 50.0),
    ])
    yield org_id, by_num
    db.chart_of_accounts.delete_many({"organization_id": org_id})
    db.journal_entries.delete_many({"organization_id": org_id})


class TestReport:
    def test_single_account_no_dates(self, org):
        org_id, by_num = org
        rep = _general_ledger_report(org_id, "u1", by_num["5040"]["id"])
        assert rep["scope"] == "single"
        d = rep["accounts"][0]
        assert d["opening_balance"] == 0.0
        assert len(d["lines"]) == 2
        assert d["closing_balance"] == 150.0  # charge (normal débit) : 100 + 50

    def test_single_account_opening_is_cumulative_before_start(self, org):
        org_id, by_num = org
        # Fenêtre à partir du 2026-02-01 : JE-1 (janvier) tombe dans le solde d'ouverture.
        rep = _general_ledger_report(org_id, "u1", by_num["5040"]["id"], start="2026-02-01")
        d = rep["accounts"][0]
        assert d["opening_balance"] == 100.0  # report de JE-1
        assert len(d["lines"]) == 1           # seul JE-2 est dans la fenêtre
        assert d["lines"][0]["entry_number"] == "JE-2"
        assert d["closing_balance"] == 150.0

    def test_general_excludes_zero_activity_by_default(self, org):
        org_id, _ = org
        rep = _general_ledger_report(org_id, "u1", None)
        assert rep["scope"] == "general"
        nums = {d["account"]["account_number"] for d in rep["accounts"]}
        assert nums == {"1000", "5040"}  # seuls les comptes avec mouvement

    def test_general_include_empty_shows_all(self, org):
        org_id, _ = org
        rep = _general_ledger_report(org_id, "u1", None, include_empty=True)
        total_accounts = db.chart_of_accounts.count_documents({"organization_id": org_id})
        assert len(rep["accounts"]) == total_accounts

    def test_encaisse_running_balance_negative(self, org):
        org_id, by_num = org
        rep = _general_ledger_report(org_id, "u1", by_num["1000"]["id"])
        d = rep["accounts"][0]
        assert d["closing_balance"] == -150.0  # actif crédité 2x

    def test_unknown_account_404(self, org):
        org_id, _ = org
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            _general_ledger_report(org_id, "u1", "does-not-exist")
        assert exc.value.status_code == 404


class TestExports:
    def test_csv_has_opening_and_closing_rows(self, org):
        org_id, by_num = org
        rep = _general_ledger_report(org_id, "u1", by_num["5040"]["id"])
        csv_bytes = _render_general_ledger_csv(rep)
        text = csv_bytes.decode("utf-8-sig")
        assert text.startswith("Compte n°,Compte,Date,N°,Description,Débit,Crédit,Solde")
        assert "Solde d'ouverture" in text
        assert "Solde de clôture" in text
        assert "150.00" in text  # solde de clôture du 5040

    def test_pdf_renders_bytes(self, org):
        org_id, _ = org
        rep = _general_ledger_report(org_id, "u1", None)
        pdf = _render_general_ledger_pdf(rep, org_id, None, None)
        assert pdf[:4] == b"%PDF" and len(pdf) > 800

    def test_csv_neutralizes_formula_injection(self):
        """Revue adverse : nom de compte / description commençant par =,+,-,@ ne doivent pas
        rester en tête de cellule (injection de formule Excel)."""
        report = {"scope": "single", "start": None, "end": None, "accounts": [{
            "account": {"id": "x", "account_number": "5040", "name": "=SUM(A1)",
                        "account_type": "expense", "normal_balance": "debit"},
            "opening_balance": 0.0,
            "lines": [{"entry_id": "e", "entry_number": "JE-1", "entry_date": "2026-01-01",
                       "description": "=cmd|'/c calc'!A0", "reference": None,
                       "debit": 10.0, "credit": 0.0, "running_balance": 10.0}],
            "closing_balance": 10.0}]}
        text = _render_general_ledger_csv(report).decode("utf-8-sig")
        import csv as _csv
        import io as _io
        rows = list(_csv.reader(_io.StringIO(text)))
        dangerous = ("=", "+", "-", "@")
        for r in rows[1:]:  # saute l'entête
            assert not r[1].startswith(dangerous), f"nom dangereux: {r[1]!r}"
            assert not r[4].startswith(dangerous), f"description dangereuse: {r[4]!r}"

    def test_general_includes_unmapped_orphan(self, org):
        """Une ligne postée référant un account_id hors plan est surfacée « Compte non mappé »
        (réconciliation avec la balance de vérification)."""
        org_id, by_num = org
        db.journal_entries.insert_one({
            "id": str(_uuid.uuid4()), "organization_id": org_id, "entry_number": "JE-ORPH",
            "entry_date": "2026-02-01", "status": "posted", "entry_type": "manual",
            "description": "Orphelin", "reverses_entry_id": None, "reversed_by_entry_id": None,
            "lines": [
                {"account_id": "ORPHAN-XYZ", "account_number": "9999", "debit": 25.0, "credit": 0.0},
                {"account_id": by_num["1000"]["id"], "account_number": "1000",
                 "debit": 0.0, "credit": 25.0}],
        })
        rep = _general_ledger_report(org_id, "u1", None)
        assert any("non mappé" in d["account"]["name"] for d in rep["accounts"])


@pytest.fixture
def auth_headers():
    r = client.post("/api/auth/login",
                    json={"email": "gussdub@gmail.com", "password": "testpass123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class TestEndpoints:
    def test_pdf_endpoint_general(self, auth_headers):
        r = client.get("/api/ledger/general-ledger/pdf", headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf"
        assert "grand-livre-general" in r.headers.get("content-disposition", "")
        assert r.content[:4] == b"%PDF"

    def test_csv_endpoint_general(self, auth_headers):
        r = client.get("/api/ledger/general-ledger/csv", headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("text/csv")
        assert r.content[:3] == b"\xef\xbb\xbf"  # BOM utf-8 (Excel FR)

    def test_pdf_endpoint_unknown_account_404(self, auth_headers):
        r = client.get("/api/ledger/general-ledger/pdf?account_id=nope-123", headers=auth_headers)
        assert r.status_code == 404

    def test_endpoint_invalid_date_400(self, auth_headers):
        for url in ("/api/ledger/general-ledger/pdf?start=notadate",
                    "/api/ledger/general-ledger/csv?end=2026-13-99"):
            r = client.get(url, headers=auth_headers)
            assert r.status_code == 400, f"{url} -> {r.status_code}"
