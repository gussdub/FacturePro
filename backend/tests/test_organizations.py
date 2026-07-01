import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uuid
import pytest
from datetime import datetime, timezone

from server import (
    PERMISSIONS_EDITABLE,
    PERMISSIONS_OWNER_ONLY,
    DEFAULT_ROLE_PERMISSIONS,
    migrate_organizations_v1,
    _resolve_permissions,
    _synthesize_solo_org_from_user,
    CurrentUser,
    db as server_db,
)


class TestPermissionConstants:
    def test_editable_codes_present(self):
        for code in ["expenses:read", "expenses:write", "invoices:read", "invoices:write",
                     "quotes:read", "quotes:write", "clients:read", "clients:write",
                     "products:read", "products:write", "employees:read", "employees:write",
                     "reports:read", "bank:read", "bank:write", "receipts:scan"]:
            assert code in PERMISSIONS_EDITABLE, f"Missing editable code: {code}"

    def test_owner_only_codes_present(self):
        for code in ["settings:manage", "billing:manage", "team:manage"]:
            assert code in PERMISSIONS_OWNER_ONLY

    def test_no_overlap_editable_owner_only(self):
        assert set(PERMISSIONS_EDITABLE).isdisjoint(set(PERMISSIONS_OWNER_ONLY))

    def test_default_accountant_has_all_editable(self):
        assert set(DEFAULT_ROLE_PERMISSIONS["accountant"]) == set(PERMISSIONS_EDITABLE)

    def test_default_viewer_read_only(self):
        for code in DEFAULT_ROLE_PERMISSIONS["viewer"]:
            assert code.endswith(":read"), f"Viewer should not have write perm: {code}"
        assert "receipts:scan" not in DEFAULT_ROLE_PERMISSIONS["viewer"]


class TestMigrateOrganizationsV1:
    def _make_orphan_user(self):
        uid = f"test-org-mig-{uuid.uuid4().hex[:8]}"
        server_db.users.insert_one({
            "id": uid,
            "email": f"{uid}@test.local",
            "company_name": "Acme Migration Test",
            "is_active": True,
            "subscription_status": "trial",
            "trial_end_date": "2099-12-31T00:00:00+00:00",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        # Insert some business docs with legacy user_id only
        server_db.invoices.insert_one({
            "id": f"inv-{uid}", "user_id": uid, "invoice_number": "TEST-001",
            "total_cad": 100.0,
        })
        server_db.expenses.insert_one({
            "id": f"exp-{uid}", "user_id": uid, "vendor": "Test Vendor",
            "amount_cad": 25.0,
        })
        return uid

    def _cleanup(self, uid):
        server_db.users.delete_one({"id": uid})
        server_db.organizations.delete_many({"owner_id": uid})
        for coll in ["invoices", "expenses", "quotes", "clients", "products",
                     "employees", "company_settings"]:
            server_db[coll].delete_many({"user_id": uid})

    def test_creates_org_for_orphan_user(self):
        uid = self._make_orphan_user()
        try:
            migrate_organizations_v1()
            user = server_db.users.find_one({"id": uid})
            assert user.get("organization_id") is not None
            assert user.get("role") == "owner"
            org = server_db.organizations.find_one({"id": user["organization_id"]})
            assert org is not None
            assert org["owner_id"] == uid
            assert org["name"] == "Acme Migration Test"
            assert org["subscription_status"] == "trial"
            assert org["trial_ends_at"] == "2099-12-31T00:00:00+00:00"
            assert org["role_permissions"] == DEFAULT_ROLE_PERMISSIONS
        finally:
            self._cleanup(uid)

    def test_backfills_business_docs(self):
        uid = self._make_orphan_user()
        try:
            migrate_organizations_v1()
            user = server_db.users.find_one({"id": uid})
            org_id = user["organization_id"]
            inv = server_db.invoices.find_one({"id": f"inv-{uid}"})
            assert inv["organization_id"] == org_id
            assert inv["created_by_user_id"] == uid
            exp = server_db.expenses.find_one({"id": f"exp-{uid}"})
            assert exp["organization_id"] == org_id
            assert exp["created_by_user_id"] == uid
        finally:
            self._cleanup(uid)

    def test_idempotent(self):
        uid = self._make_orphan_user()
        try:
            migrate_organizations_v1()
            user1 = server_db.users.find_one({"id": uid})
            org1 = user1["organization_id"]
            migrate_organizations_v1()  # re-run
            user2 = server_db.users.find_one({"id": uid})
            assert user2["organization_id"] == org1
            # Only 1 org for this owner (idempotence)
            assert server_db.organizations.count_documents({"owner_id": uid}) == 1
        finally:
            self._cleanup(uid)

    def test_fallback_name_from_email(self):
        uid = f"test-noname-{uuid.uuid4().hex[:8]}"
        server_db.users.insert_one({
            "id": uid, "email": f"{uid}@test.local",
            "company_name": None, "is_active": True,
            "subscription_status": "trial",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        try:
            migrate_organizations_v1()
            user = server_db.users.find_one({"id": uid})
            org = server_db.organizations.find_one({"id": user["organization_id"]})
            assert org["name"] == f"{uid}@test.local"
        finally:
            server_db.users.delete_one({"id": uid})
            server_db.organizations.delete_many({"owner_id": uid})


class TestResolvePermissions:
    def test_owner_gets_all(self):
        org = {"role_permissions": {"accountant": ["expenses:read"]}}
        perms = _resolve_permissions(org, "owner")
        for code in PERMISSIONS_EDITABLE:
            assert code in perms
        for code in PERMISSIONS_OWNER_ONLY:
            assert code in perms

    def test_accountant_gets_matrix(self):
        org = {"role_permissions": {"accountant": ["expenses:read", "expenses:write"]}}
        perms = _resolve_permissions(org, "accountant")
        assert perms == ["expenses:read", "expenses:write"]

    def test_viewer_gets_matrix(self):
        org = {"role_permissions": {"viewer": ["expenses:read", "reports:read"]}}
        perms = _resolve_permissions(org, "viewer")
        assert perms == ["expenses:read", "reports:read"]

    def test_owner_only_codes_stripped_from_editable_matrix(self):
        # Even if matrix pollution tries to grant owner-only codes to accountant,
        # they must be filtered out.
        org = {"role_permissions": {"accountant": [
            "expenses:read", "billing:manage", "team:manage"
        ]}}
        perms = _resolve_permissions(org, "accountant")
        assert "expenses:read" in perms
        assert "billing:manage" not in perms
        assert "team:manage" not in perms

    def test_unknown_codes_ignored(self):
        org = {"role_permissions": {"viewer": ["not:a:real:code", "expenses:read"]}}
        perms = _resolve_permissions(org, "viewer")
        assert perms == ["expenses:read"]

    def test_missing_role_permissions_empty(self):
        org = {}
        perms = _resolve_permissions(org, "viewer")
        assert perms == []

    def test_missing_role_in_matrix_empty(self):
        org = {"role_permissions": {"accountant": ["expenses:read"]}}
        perms = _resolve_permissions(org, "viewer")
        assert perms == []


class TestSynthesizeSoloOrg:
    def test_basic(self):
        user = {
            "id": "user-1", "email": "u@x.com", "company_name": "SoloCo",
            "subscription_status": "trial", "trial_end_date": "2099-01-01T00:00:00Z",
            "scan_count_this_month": 5,
        }
        org = _synthesize_solo_org_from_user(user)
        assert org["id"] == "pending-user-1"
        assert org["owner_id"] == "user-1"
        assert org["name"] == "SoloCo"
        assert org["subscription_status"] == "trial"
        assert org["trial_ends_at"] == "2099-01-01T00:00:00Z"
        assert org["scan_count_this_month"] == 5
        assert org["role_permissions"] == DEFAULT_ROLE_PERMISSIONS

    def test_no_company_name_falls_back_to_email(self):
        user = {"id": "u2", "email": "x@y.com"}
        org = _synthesize_solo_org_from_user(user)
        assert org["name"] == "x@y.com"


class TestCurrentUserModel:
    def test_shape(self):
        cu = CurrentUser(
            id="u1", email="a@b.com", organization_id="org1",
            role="accountant", permissions=["expenses:read"], is_exempt=False,
        )
        assert cu.id == "u1"
        assert cu.role == "accountant"
        assert "expenses:read" in cu.permissions
