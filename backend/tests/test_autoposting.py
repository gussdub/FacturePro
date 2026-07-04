"""Tests unitaires — Grand livre Phase 2 : auto-posting (feature #12).

TDD. Chaque test crée ses données dans une org JETABLE (jamais le seed org
gussdub) et se nettoie en finally, pour ne pas salir la copie-prod locale
(pattern _setup_org/_cleanup de TestLedgerCrossOrgIsolation).

Backend requis : MongoDB local (MONGO_URL/.env). Le plan comptable est seedé
via _ensure_chart_seeded pour que _snapshot_lines résolve les account_id.
"""
import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))

import uuid
import pytest

import server as server_module


def _make_org():
    """Crée une org jetable + seed du plan comptable. Renvoie (org_id, user_id)."""
    org_id = str(uuid.uuid4())
    user_id = f"ap-{uuid.uuid4().hex[:8]}"
    server_module._ensure_chart_seeded(org_id, user_id)
    return org_id, user_id


def _cleanup_org(org_id):
    server_module.db.chart_of_accounts.delete_many({"organization_id": org_id})
    server_module.db.journal_entries.delete_many({"organization_id": org_id})
    server_module.db.ledger_counters.delete_many({"organization_id": org_id})


def _account_id(org_id, account_number):
    acc = server_module.db.chart_of_accounts.find_one(
        {"organization_id": org_id, "account_number": account_number}, {"id": 1})
    assert acc, f"compte {account_number} non seedé pour {org_id}"
    return acc["id"]


class TestCreateJournalEntryThreadsSource:
    """Tâche 1 — _create_journal_entry doit threader source_type/source_id."""

    def test_create_journal_entry_threads_source(self):
        org_id, user_id = _make_org()
        try:
            lines = [
                {"account_id": _account_id(org_id, "1000"), "debit": 100, "credit": 0},
                {"account_id": _account_id(org_id, "4000"), "debit": 0, "credit": 100},
            ]
            entry = server_module._create_journal_entry(
                org_id, user_id, entry_date="2026-07-01", description="x",
                lines=lines, status="posted", entry_type="auto",
                source_type="invoice", source_id="inv-1",
            )
            # Retour de la factory
            assert entry["source_type"] == "invoice"
            assert entry["source_id"] == "inv-1"
            # Document réellement inséré dans journal_entries
            doc = server_module.db.journal_entries.find_one(
                {"id": entry["id"], "organization_id": org_id}, {"_id": 0})
            assert doc is not None
            assert doc["source_type"] == "invoice"
            assert doc["source_id"] == "inv-1"
            assert doc["entry_type"] == "auto"
        finally:
            _cleanup_org(org_id)

    def test_create_journal_entry_source_defaults_none(self):
        # Non-régression Phase 1 : sans passer les params, source_type/id = None.
        org_id, user_id = _make_org()
        try:
            lines = [
                {"account_id": _account_id(org_id, "1000"), "debit": 50, "credit": 0},
                {"account_id": _account_id(org_id, "4000"), "debit": 0, "credit": 50},
            ]
            entry = server_module._create_journal_entry(
                org_id, user_id, entry_date="2026-07-01", description="manuelle",
                lines=lines, status="posted",
            )
            assert entry["source_type"] is None
            assert entry["source_id"] is None
            doc = server_module.db.journal_entries.find_one(
                {"id": entry["id"], "organization_id": org_id}, {"_id": 0})
            assert doc["source_type"] is None
            assert doc["source_id"] is None
        finally:
            _cleanup_org(org_id)
