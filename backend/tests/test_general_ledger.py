import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uuid
import pytest
from datetime import datetime, timezone

from server import (
    ACCOUNT_TYPES,
    ACCOUNT_NUMBER_RANGES,
    DEFAULT_BASE_ACCOUNTS,
    EXPENSE_ACCOUNT_NUMBERS,
    _normal_balance_for_type,
    _account_type_for_number,
    _build_default_accounts,
    EXPENSE_CATEGORIES,
)


class TestAccountConstants:
    def test_five_account_types(self):
        assert set(ACCOUNT_TYPES) == {"asset", "liability", "equity", "revenue", "expense"}

    def test_ranges_cover_five_types(self):
        assert ACCOUNT_NUMBER_RANGES["asset"] == (1000, 1999)
        assert ACCOUNT_NUMBER_RANGES["liability"] == (2000, 2999)
        assert ACCOUNT_NUMBER_RANGES["equity"] == (3000, 3999)
        assert ACCOUNT_NUMBER_RANGES["revenue"] == (4000, 4999)
        assert ACCOUNT_NUMBER_RANGES["expense"] == (5000, 5999)


class TestNormalBalance:
    def test_asset_and_expense_are_debit(self):
        assert _normal_balance_for_type("asset") == "debit"
        assert _normal_balance_for_type("expense") == "debit"

    def test_liability_equity_revenue_are_credit(self):
        for t in ("liability", "equity", "revenue"):
            assert _normal_balance_for_type(t) == "credit"


class TestAccountTypeForNumber:
    def test_ranges(self):
        assert _account_type_for_number("1000") == "asset"
        assert _account_type_for_number("2100") == "liability"
        assert _account_type_for_number("3200") == "equity"
        assert _account_type_for_number("4000") == "revenue"
        assert _account_type_for_number("5900") == "expense"

    def test_out_of_range_returns_none(self):
        assert _account_type_for_number("6000") is None
        assert _account_type_for_number("999") is None
        assert _account_type_for_number("abcd") is None


class TestBuildDefaultAccounts:
    def test_total_29_accounts(self):
        accounts = _build_default_accounts("org-x", "user-x")
        assert len(accounts) == 29  # 12 base + 17 dépenses

    def test_all_scoped_and_system(self):
        accounts = _build_default_accounts("org-x", "user-x")
        for a in accounts:
            assert a["organization_id"] == "org-x"
            assert a["created_by_user_id"] == "user-x"
            assert a["is_system"] is True
            assert a["is_active"] is True

    def test_numbers_unique(self):
        accounts = _build_default_accounts("org-x", "user-x")
        numbers = [a["account_number"] for a in accounts]
        assert len(numbers) == len(set(numbers))

    def test_normal_balance_matches_type(self):
        accounts = _build_default_accounts("org-x", "user-x")
        for a in accounts:
            assert a["normal_balance"] == _normal_balance_for_type(a["account_type"])
            derived = _account_type_for_number(a["account_number"])
            assert a["account_type"] == derived

    def test_expense_accounts_mapped_to_17_categories(self):
        accounts = _build_default_accounts("org-x", "user-x")
        mapped = {a["expense_category_code"] for a in accounts if a.get("expense_category_code")}
        catalogue = {c["code"] for c in EXPENSE_CATEGORIES if c["code"] != "other"}
        assert mapped == catalogue  # les 17 catégories hors "other"

    def test_base_accounts_include_cash_and_owner_contribution(self):
        accounts = _build_default_accounts("org-x", "user-x")
        by_number = {a["account_number"]: a for a in accounts}
        assert by_number["1000"]["name"] == "Encaisse"
        assert by_number["3100"]["name"] == "Apport du propriétaire"
        assert by_number["4000"]["account_type"] == "revenue"


from server import (
    PERMISSIONS_EDITABLE,
    PERMISSIONS_OWNER_ONLY,
    DEFAULT_ROLE_PERMISSIONS,
    _resolve_permissions,
)


class TestAccountingPermissions:
    def test_accounting_codes_editable(self):
        assert "accounting:read" in PERMISSIONS_EDITABLE
        assert "accounting:write" in PERMISSIONS_EDITABLE

    def test_accounting_not_owner_only(self):
        assert "accounting:read" not in PERMISSIONS_OWNER_ONLY
        assert "accounting:write" not in PERMISSIONS_OWNER_ONLY

    def test_accountant_default_has_both(self):
        assert "accounting:read" in DEFAULT_ROLE_PERMISSIONS["accountant"]
        assert "accounting:write" in DEFAULT_ROLE_PERMISSIONS["accountant"]

    def test_viewer_default_read_only(self):
        assert "accounting:read" in DEFAULT_ROLE_PERMISSIONS["viewer"]
        assert "accounting:write" not in DEFAULT_ROLE_PERMISSIONS["viewer"]

    def test_owner_resolves_both(self):
        perms = _resolve_permissions({}, "owner")
        assert "accounting:read" in perms
        assert "accounting:write" in perms

    def test_viewer_can_be_granted_write_by_owner(self):
        # accounting:write est un code EDITABLE (pas owner-only) : l'owner peut
        # l'accorder volontairement à un rôle via la matrice role_permissions.
        # Ici l'owner a coché accounting:write pour le viewer → le résolveur
        # doit le laisser passer (il franchit le filtre PERMISSIONS_EDITABLE).
        org = {"role_permissions": {"viewer": ["accounting:read", "accounting:write"]}}
        perms = _resolve_permissions(org, "viewer")
        assert "accounting:write" in perms


from server import migrate_general_ledger_v1, db as server_db


class TestMigrateGeneralLedgerV1:
    def _make_org_and_settings(self):
        org_id = f"gl-mig-{uuid.uuid4().hex[:8]}"
        server_db.organizations.insert_one({
            "id": org_id, "name": "GL Mig Test", "owner_id": "u-" + org_id,
            "role_permissions": {"accountant": [], "viewer": []},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        server_db.company_settings.insert_one({
            "id": f"cs-{org_id}", "user_id": "u-" + org_id,
            "organization_id": org_id, "company_name": "GL Mig Test",
        })
        return org_id

    def _cleanup(self, org_id):
        server_db.organizations.delete_one({"id": org_id})
        server_db.company_settings.delete_many({"organization_id": org_id})

    def test_backfills_fiscal_fields_default_dec_31(self):
        org_id = self._make_org_and_settings()
        try:
            migrate_general_ledger_v1()
            cs = server_db.company_settings.find_one({"organization_id": org_id})
            assert cs["fiscal_year_end_month"] == 12
            assert cs["fiscal_year_end_day"] == 31
        finally:
            self._cleanup(org_id)

    def test_backfills_accounting_perms(self):
        org_id = self._make_org_and_settings()
        try:
            migrate_general_ledger_v1()
            org = server_db.organizations.find_one({"id": org_id})
            rp = org["role_permissions"]
            assert "accounting:read" in rp["accountant"]
            assert "accounting:write" in rp["accountant"]
            assert "accounting:read" in rp["viewer"]
            assert "accounting:write" not in rp["viewer"]
        finally:
            self._cleanup(org_id)

    def test_idempotent(self):
        org_id = self._make_org_and_settings()
        try:
            migrate_general_ledger_v1()
            migrate_general_ledger_v1()  # re-run — no crash, no dup
            cs = server_db.company_settings.find_one({"organization_id": org_id})
            assert cs["fiscal_year_end_month"] == 12
        finally:
            self._cleanup(org_id)

    def test_does_not_overwrite_custom_fiscal(self):
        org_id = self._make_org_and_settings()
        server_db.company_settings.update_one(
            {"organization_id": org_id},
            {"$set": {"fiscal_year_end_month": 3, "fiscal_year_end_day": 31}}
        )
        try:
            migrate_general_ledger_v1()
            cs = server_db.company_settings.find_one({"organization_id": org_id})
            assert cs["fiscal_year_end_month"] == 3  # respecté
        finally:
            self._cleanup(org_id)

    def test_sets_one_shot_flag(self):
        # Le 1er passage pose le flag persisté `ledger_perms_backfilled` (spec §8.2).
        org_id = self._make_org_and_settings()
        try:
            migrate_general_ledger_v1()
            org = server_db.organizations.find_one({"id": org_id})
            assert org.get("ledger_perms_backfilled") is True
        finally:
            self._cleanup(org_id)

    def test_owner_removal_not_reimposed_on_reboot(self):
        # Régression : après le 1er backfill, un owner retire volontairement
        # accounting:* d'un rôle. Un boot suivant (re-run de la migration) NE
        # doit PAS le ré-accorder, car le flag one-shot est déjà posé (spec §8.2).
        org_id = self._make_org_and_settings()
        try:
            migrate_general_ledger_v1()  # 1er passage : perms ajoutées + flag posé
            # L'owner retire volontairement accounting:* du comptable et du lecteur.
            server_db.organizations.update_one(
                {"id": org_id},
                {"$set": {"role_permissions": {"accountant": [], "viewer": []}}},
            )
            migrate_general_ledger_v1()  # reboot : ne doit rien ré-imposer
            org = server_db.organizations.find_one({"id": org_id})
            rp = org["role_permissions"]
            assert "accounting:read" not in rp["accountant"]
            assert "accounting:write" not in rp["accountant"]
            assert "accounting:read" not in rp["viewer"]
        finally:
            self._cleanup(org_id)

    def test_flag_skips_already_backfilled_org(self):
        # Une org qui a déjà le flag (jamais touchée par le backfill) garde ses
        # perms telles quelles même vides — le backfill la saute entièrement.
        org_id = self._make_org_and_settings()
        server_db.organizations.update_one(
            {"id": org_id}, {"$set": {"ledger_perms_backfilled": True}}
        )
        try:
            migrate_general_ledger_v1()
            org = server_db.organizations.find_one({"id": org_id})
            rp = org["role_permissions"]
            assert rp["accountant"] == []
            assert rp["viewer"] == []
        finally:
            self._cleanup(org_id)
