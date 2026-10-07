"""Tests — état des résultats tiré du grand livre et bilan incluant le résultat non clôturé."""
import os
import sys
import uuid as _uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")
os.environ.setdefault("DB_NAME", "facturepro")

import pytest  # noqa: E402
from fastapi import Response  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from backend.server import (  # noqa: E402
    db, _build_default_accounts, _income_statement, balance_sheet,
    income_statement, income_statement_pdf, CurrentUser,
)


@pytest.fixture()
def org():
    org_id = f"TESTORG-IS-{_uuid.uuid4()}"
    accts = _build_default_accounts(org_id, "u1")
    db.chart_of_accounts.insert_many([dict(a) for a in accts])
    by_num = {a["account_number"]: a for a in accts}

    def je(date, lines, num=None):
        db.journal_entries.insert_one({
            "id": str(_uuid.uuid4()), "organization_id": org_id,
            "entry_number": num or f"JE-{_uuid.uuid4().hex[:6]}", "entry_date": date,
            "status": "posted", "entry_type": "manual", "description": "t",
            "lines": [{"account_id": by_num[n]["id"], "account_number": n,
                       "debit": d, "credit": c} for (n, d, c) in lines]})

    yield org_id, by_num, je
    db.chart_of_accounts.delete_many({"organization_id": org_id})
    db.journal_entries.delete_many({"organization_id": org_id})
    db.company_settings.delete_many({"organization_id": org_id})


def _user(org_id):
    return CurrentUser(id="u1", email="t@t.ca", organization_id=org_id, role="owner",
                       permissions=["accounting:read"])


def _rev(by_num):
    return next(n for n, a in by_num.items() if a["account_type"] == "revenue")


def _exp(by_num):
    return "5040"


def _bs(org_id, as_of):
    return balance_sheet(response=Response(), as_of=as_of, current_user=_user(org_id))


class TestIncomeStatement:
    def test_includes_manual_entries_and_respects_dates(self, org):
        org_id, by_num, je = org
        rev = _rev(by_num)
        je("2026-02-01", [("1000", 1000, 0), (rev, 0, 1000)])
        je("2026-02-15", [(_exp(by_num), 25, 0), ("1000", 0, 25)])  # frais bancaires manuels
        je("2026-05-01", [("1000", 500, 0), (rev, 0, 500)])          # hors période
        inc = _income_statement(org_id, "2026-01-01", "2026-03-31")
        assert inc["revenues"]["total"] == 1000.0
        assert inc["expenses"]["total"] == 25.0
        assert inc["net_income"] == 975.0
        assert [a["account_number"] for a in inc["expenses"]["accounts"]] == ["5040"]

    def test_closing_entry_is_excluded(self, org):
        org_id, by_num, je = org
        rev = _rev(by_num)
        je("2025-06-01", [("1000", 800, 0), (rev, 0, 800)])
        je("2025-12-31", [(rev, 800, 0), ("3200", 0, 800)])  # clôture vers BNR
        inc = _income_statement(org_id, "2025-01-01", "2025-12-31")
        assert inc["net_income"] == 800.0
        assert inc["closing_entries_excluded"] == 1

    def test_endpoint_default_period_and_pdf(self, org):
        org_id, _, _ = org
        u = _user(org_id)
        r = income_statement(response=Response(), start=None, end="2026-03-31", current_user=u)
        assert r["start"] == "2026-01-01"  # début de l'exercice par défaut
        with pytest.raises(HTTPException) as e:
            income_statement(response=Response(), start="2026-04-01", end="2026-03-01",
                             current_user=u)
        assert e.value.status_code == 400
        pdf = income_statement_pdf(start="2026-01-01", end="2026-03-31", current_user=u)
        assert pdf.body[:4] == b"%PDF"


class TestBalanceSheetUnclosedResults:
    def test_prior_year_not_closed_still_balances(self, org):
        org_id, by_num, je = org
        rev = _rev(by_num)
        je("2025-06-01", [("1000", 1000, 0), (rev, 0, 1000)])
        je("2026-02-01", [("1000", 300, 0), (rev, 0, 300)])
        je("2026-02-10", [(_exp(by_num), 50, 0), ("1000", 0, 50)])
        bs = _bs(org_id, "2026-03-31")
        assert bs["equity"]["unclosed_prior_years_income"] == 1000.0
        assert bs["equity"]["net_income_current_year"] == 250.0
        assert bs["equity"]["revenues_current_year"] == 300.0
        assert bs["equity"]["expenses_current_year"] == 50.0
        assert bs["total_assets"] == 1250.0
        assert bs["balanced"] is True

    def test_after_closing_entry_prior_moves_to_bnr(self, org):
        org_id, by_num, je = org
        rev = _rev(by_num)
        je("2025-06-01", [("1000", 1000, 0), (rev, 0, 1000)])
        # Clôture datée APRÈS la fin d'exercice : ne doit pas toucher le résultat courant.
        je("2026-01-20", [(rev, 1000, 0), ("3200", 0, 1000)])
        je("2026-02-01", [("1000", 300, 0), (rev, 0, 300)])
        bs = _bs(org_id, "2026-03-31")
        assert bs["equity"]["unclosed_prior_years_income"] == 0.0
        assert bs["equity"]["net_income_current_year"] == 300.0
        assert {a["account_number"]: a["balance"] for a in bs["equity"]["accounts"]}["3200"] == 1000.0
        assert bs["balanced"] is True
