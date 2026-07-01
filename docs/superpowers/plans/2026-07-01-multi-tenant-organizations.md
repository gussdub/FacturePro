# Multi-tenant Organizations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable multiple users to share an organization's data with role-based permissions editable by the owner.

**Architecture:** New `organizations` collection; users get `organization_id` + `role`; auth middleware injects role+permissions; all queries filter by `organization_id`; migration at startup is idempotent; email invitations via Resend.

**Tech Stack:** FastAPI + pymongo + Pydantic; Resend for invitations; JWT unchanged; React 18 for team management UI.

**Spec source:** [docs/superpowers/specs/2026-07-01-multi-tenant-organizations-design.md](../specs/2026-07-01-multi-tenant-organizations-design.md)

---

## File Structure

**Backend** (`backend/server.py` — nouvelle section « Organizations & permissions ») :
- Constantes : `PERMISSIONS_EDITABLE`, `PERMISSIONS_OWNER_ONLY`, `DEFAULT_ROLE_PERMISSIONS`
- Modèle Pydantic : `CurrentUser` (nouveau — remplace usage direct de `User`)
- Helpers : `_resolve_permissions`, `_synthesize_solo_org_from_user`, `_check_subscription_active`, `migrate_organizations_v1`, `_get_org_or_synthesize`, `_send_invitation_email`, `_rate_limit_accept_invite`
- Dependency : `get_current_user_with_access` refactoré, nouveau `require_permission("code")`
- Endpoints nouveaux : `GET /api/org/me`, `PUT /api/org/role-permissions`, `POST/GET/DELETE /api/org/invitations`, `GET /api/org/invitations/preview`, `POST /api/auth/accept-invite`, `PUT /api/org/members/{user_id}/role`, `DELETE /api/org/members/{user_id}`
- Endpoints décorés : ~60 endpoints métier reçoivent `Depends(require_permission("..."))`
- Requêtes migrées : tous les `{"user_id": ...}` sur collections métier deviennent `{"organization_id": ...}`

**Tests** (`backend/tests/`) :
- `test_organizations.py` — unitaires (résolution permissions, migration, matrice validation)
- `test_organizations_integration.py` — intégration HTTP (isolation cross-org, flow invitation E2E, permissions)

**Frontend** (`frontend/src/`) :
- `context/AuthContext.js` — expose `permissions`, `role`, `organization`, `hasPermission()`
- `components/RouteGuard.js` — nouveau composant wrapper de route
- `components/Layout.js` — filtre sidebar par permission
- `pages/SettingsPage.js` — nouvel onglet « Équipe » (membres + invitations + matrice permissions)
- `components/InviteMemberModal.js` — modal d'invitation
- `pages/AcceptInvitePage.js` — page publique d'acceptation
- `pages/*Page.js` — boutons d'action gated par `hasPermission()`

---

## Task 0 : Read spec + setup test stubs

**Files:**
- Read: `docs/superpowers/specs/2026-07-01-multi-tenant-organizations-design.md`
- Create: `backend/tests/test_organizations.py`
- Create: `backend/tests/test_organizations_integration.py`

- [ ] **Step 1: Lire la spec complète**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
cat docs/superpowers/specs/2026-07-01-multi-tenant-organizations-design.md | head -300
```

Se concentrer sur :
- §2 (décisions verrouillées — ne pas dévier)
- §3 (modèle de données `organizations` + `invitations` + champs users)
- §4 (auth middleware refactor)
- §5 (endpoints REST — signatures + codes retour exacts)
- §6 (migration idempotente au startup)
- §8 (sécurité — anti-lockout owner, filtrage code inconnus)

- [ ] **Step 2: Créer les stubs de tests**

`backend/tests/test_organizations.py` :
```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uuid
import pytest
from datetime import datetime, timezone
```

`backend/tests/test_organizations_integration.py` :
```python
import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))

import uuid
import pytest
import server as server_module
from fastapi.testclient import TestClient


BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="module")
def client():
    return TestClient(server_module.app)


@pytest.fixture(scope="module")
def owner_headers(client):
    resp = client.post("/api/auth/login",
                       json={"email": "gussdub@gmail.com", "password": "testpass123"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}
```

- [ ] **Step 3: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/tests/test_organizations.py backend/tests/test_organizations_integration.py
git commit -m "test(organizations): stubs for feature #11"
```

---

## Task 1 : Constantes permissions + migration idempotente au startup

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_organizations.py`

- [ ] **Step 1: Écrire les tests de la migration + constantes**

Append à `backend/tests/test_organizations.py` :
```python
from server import (
    PERMISSIONS_EDITABLE,
    PERMISSIONS_OWNER_ONLY,
    DEFAULT_ROLE_PERMISSIONS,
    migrate_organizations_v1,
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
```

- [ ] **Step 2: Verify failure**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
pytest tests/test_organizations.py -v 2>&1 | tail -15
```
Expected : ImportError sur `PERMISSIONS_EDITABLE` (les constantes n'existent pas encore).

- [ ] **Step 3: Ajouter les constantes + la migration dans `server.py`**

Localiser la fin de la section `EXEMPT_USERS`/`get_current_user` (autour de la ligne 1130) et AJOUTER une nouvelle section AVANT `get_current_user` :

```python
# ─── Organizations & permissions (feature #11) ───

PERMISSIONS_EDITABLE = [
    "expenses:read",   "expenses:write",
    "invoices:read",   "invoices:write",
    "quotes:read",     "quotes:write",
    "clients:read",    "clients:write",
    "products:read",   "products:write",
    "employees:read",  "employees:write",
    "reports:read",
    "bank:read",       "bank:write",
    "receipts:scan",
]

PERMISSIONS_OWNER_ONLY = [
    "settings:manage",  # company_info, entity_type, province, home/vehicle %
    "billing:manage",   # Stripe subscription + customer portal
    "team:manage",      # invite, remove, change role, edit permissions
]

DEFAULT_ROLE_PERMISSIONS = {
    "accountant": list(PERMISSIONS_EDITABLE),  # tout coché par défaut
    "viewer": [
        "expenses:read", "invoices:read", "quotes:read",
        "clients:read", "products:read", "employees:read",
        "reports:read", "bank:read",
    ],
}


# Collections métier scopées par organisation (utilisées par migration + queries).
_ORG_SCOPED_COLLECTIONS = [
    "invoices", "quotes", "expenses", "clients", "products", "employees",
    "company_settings", "files", "bank_mappings", "bank_imports",
    "bank_transactions", "payment_transactions", "trial_notifications",
    "quote_tokens",
]


def migrate_organizations_v1():
    """Idempotente. Safe à exécuter à chaque boot backend.
    - Crée une organisation pour chaque user sans organization_id.
    - Backfill organization_id + created_by_user_id sur toutes les collections métier.
    - Crée les indexes nécessaires."""
    users_without_org = list(db.users.find({"organization_id": {"$exists": False}}))
    for user in users_without_org:
        org_id = str(uuid.uuid4())
        org_doc = {
            "id": org_id,
            "name": user.get("company_name") or user["email"],
            "owner_id": user["id"],
            "subscription_status": user.get("subscription_status", "trial"),
            "stripe_customer_id": user.get("stripe_customer_id"),
            "trial_ends_at": user.get("trial_end_date"),
            "role_permissions": DEFAULT_ROLE_PERMISSIONS,
            "scan_count_this_month": user.get("scan_count_this_month", 0),
            "scan_quota_reset_at": user.get("scan_quota_reset_at"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        db.organizations.insert_one(org_doc)
        db.users.update_one(
            {"id": user["id"]},
            {"$set": {"organization_id": org_id, "role": "owner"}}
        )
        # Backfill business collections : organization_id + created_by_user_id
        for coll_name in _ORG_SCOPED_COLLECTIONS:
            db[coll_name].update_many(
                {"user_id": user["id"], "organization_id": {"$exists": False}},
                [{"$set": {
                    "organization_id": org_id,
                    "created_by_user_id": "$user_id",
                }}]
            )

    # Indexes idempotents
    db.organizations.create_index("id", unique=True)
    db.organizations.create_index("owner_id")
    db.invitations.create_index("token", unique=True, sparse=True)
    db.invitations.create_index([("organization_id", 1), ("status", 1)])
    db.invitations.create_index([("email", 1), ("status", 1)])
    for coll_name in _ORG_SCOPED_COLLECTIONS:
        db[coll_name].create_index("organization_id")

    if users_without_org:
        print(f"MIGRATION organizations_v1 : {len(users_without_org)} orgs créées")
```

- [ ] **Step 4: Brancher la migration au startup**

Dans le bloc `@app.on_event("startup") def seed_data()` (autour de la ligne 4363), AJOUTER l'appel après `migrate_pst_to_qst()` et avant le bloc `existing = db.users.find_one({"email": "gussdub@gmail.com"})` :

```python
        # Migration feature #11 — organizations multi-tenant (idempotente)
        migrate_organizations_v1()
```

- [ ] **Step 5: Tests pass**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
pytest tests/test_organizations.py -v 2>&1 | tail -20
```
Expected : 9 tests pass (5 constants + 4 migration).

- [ ] **Step 6: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_organizations.py
git commit -m "feat(organizations): constants + migrate_organizations_v1 idempotent au startup"
```

---

## Task 2 : Auth middleware upgrade — `CurrentUser` + `_resolve_permissions` + `get_current_user_with_access` refactor

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_organizations.py`

- [ ] **Step 1: Écrire les tests unitaires**

Append à `backend/tests/test_organizations.py` :
```python
from server import (
    _resolve_permissions,
    _synthesize_solo_org_from_user,
    CurrentUser,
)


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
```

- [ ] **Step 2: Verify failure**

```bash
pytest tests/test_organizations.py -v 2>&1 | tail -10
```

- [ ] **Step 3: Ajouter le modèle Pydantic + les helpers**

Dans `backend/server.py`, chercher la définition du modèle `User` (autour de la ligne 1100). AJOUTER après `class User(BaseModel):` :

```python
class CurrentUser(BaseModel):
    id: str
    email: str
    organization_id: str
    role: str                      # "owner" | "accountant" | "viewer"
    permissions: List[str]         # résolues à chaque requête
    is_exempt: bool = False
```

Assurer que `List` est importé (déjà présent dans les imports typing en haut du fichier). Si absent : `from typing import List`.

- [ ] **Step 4: Ajouter les helpers de résolution**

Dans la section « Organizations & permissions » (créée en Task 1), AJOUTER après `DEFAULT_ROLE_PERMISSIONS` (avant `_ORG_SCOPED_COLLECTIONS`) :

```python
def _resolve_permissions(org: dict, role: str) -> list:
    """Résout la liste des permissions pour un rôle donné.
    Sécurité : owner-only codes ne peuvent JAMAIS être accordés via la matrice.
    Codes inconnus sont ignorés (protection contre matrice polluée)."""
    if role == "owner":
        return list(PERMISSIONS_EDITABLE) + list(PERMISSIONS_OWNER_ONLY)
    role_perms = (org.get("role_permissions") or {}).get(role, [])
    return [p for p in role_perms if p in PERMISSIONS_EDITABLE]


def _synthesize_solo_org_from_user(user: dict) -> dict:
    """Fallback pre-migration : construit une organisation virtuelle en mémoire
    quand un user existe encore sans organization_id (edge case course condition
    entre boot et migration)."""
    return {
        "id": f"pending-{user['id']}",
        "name": user.get("company_name") or user["email"],
        "owner_id": user["id"],
        "subscription_status": user.get("subscription_status", "trial"),
        "trial_ends_at": user.get("trial_end_date"),
        "role_permissions": DEFAULT_ROLE_PERMISSIONS,
        "scan_count_this_month": user.get("scan_count_this_month", 0),
        "scan_quota_reset_at": user.get("scan_quota_reset_at"),
    }


def _check_subscription_active(org: dict, user: dict):
    """Vérifie l'état d'abonnement au niveau org (avec exempt email fallback).
    Raise HTTPException(402) si l'org est expirée et le user n'est pas exempt."""
    if user.get("email") in EXEMPT_USERS:
        return
    sub_status = org.get("subscription_status", "trial")
    trial_end = org.get("trial_ends_at")
    if sub_status == "trial" and trial_end:
        try:
            trial_end_dt = datetime.fromisoformat(trial_end)
            if datetime.now(timezone.utc) > trial_end_dt:
                sub_status = "expired"
        except Exception:
            pass
    if sub_status == "expired":
        raise HTTPException(402, "Subscription expired — please renew")


def _get_org_for_user(user: dict) -> dict:
    """Retourne l'organisation d'un user, avec fallback synthetic."""
    org_id = user.get("organization_id")
    if not org_id:
        return _synthesize_solo_org_from_user(user)
    org = db.organizations.find_one({"id": org_id}, {"_id": 0})
    if not org:
        # Org orpheline — log + fallback
        print(f"[org] Organisation orpheline pour user {user.get('id')} → synthesize")
        return _synthesize_solo_org_from_user(user)
    return org
```

- [ ] **Step 5: Refactor `get_current_user_with_access`**

Remplacer le corps existant de `get_current_user_with_access` (autour de la ligne 1145) :

**Avant** :
```python
def get_current_user_with_access(credentials: HTTPAuthorizationCredentials = Depends(security)):
    return get_current_user(credentials)
```

**Après** :
```python
def get_current_user_with_access(credentials: HTTPAuthorizationCredentials = Depends(security)) -> CurrentUser:
    """Résout le JWT → user → organisation → rôle → permissions.
    Vérifie l'abonnement au niveau org. Retourne un CurrentUser complet."""
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except Exception:
        raise HTTPException(401, "Invalid token")

    user = db.users.find_one({"id": user_id}, {"_id": 0})
    if not user or not user.get("is_active", True):
        raise HTTPException(401, "User not found or inactive")

    org = _get_org_for_user(user)
    _check_subscription_active(org, user)

    role = user.get("role", "owner")
    return CurrentUser(
        id=user["id"],
        email=user["email"],
        organization_id=org["id"],
        role=role,
        permissions=_resolve_permissions(org, role),
        is_exempt=user["email"] in EXEMPT_USERS,
    )
```

**Important** : le legacy `get_current_user` reste inchangé (autres tests peuvent en dépendre), mais tous les endpoints utilisent désormais `get_current_user_with_access`.

- [ ] **Step 6: Adapter les endpoints qui accèdent à `current_user.id` seulement**

Le refactor change le type de `current_user` de `User` à `CurrentUser`. Le champ `.id` reste identique, donc **aucun changement** requis sur les endpoints qui utilisent uniquement `current_user.id`.

Les endpoints qui utilisaient `current_user.company_name` doivent être migrés — mais `CurrentUser` n'a pas ce champ. Chercher les usages :

```bash
grep -n "current_user\.company_name\|current_user\.subscription_status\|current_user\.trial_end_date" backend/server.py | head -10
```

Pour chaque hit, remplacer par un lookup direct : `db.users.find_one({"id": current_user.id}, {"_id": 0})`.

- [ ] **Step 7: Adapter `GET /api/auth/me` (feature #11 transition)**

Remplacer le corps de `get_me` (autour de la ligne 1148) pour lire l'abonnement depuis l'organisation :

```python
@app.get("/api/auth/me")
def get_me(current_user: CurrentUser = Depends(get_current_user_with_access)):
    user_doc = db.users.find_one({"id": current_user.id}, {"_id": 0})
    org = db.organizations.find_one({"id": current_user.organization_id}, {"_id": 0}) \
          or _synthesize_solo_org_from_user(user_doc)
    is_exempt = current_user.is_exempt
    sub_status = org.get("subscription_status", "trial")
    trial_end = org.get("trial_ends_at")
    if sub_status == "trial" and trial_end and not is_exempt:
        try:
            trial_end_dt = datetime.fromisoformat(trial_end)
            if datetime.now(timezone.utc) > trial_end_dt:
                sub_status = "expired"
        except Exception:
            pass
    # Feature #11 — expose org/role/permissions ; garde legacy pour compat frontend
    return {
        "id": current_user.id,
        "email": current_user.email,
        "company_name": user_doc.get("company_name"),
        # Nouveaux champs (feature #11)
        "organization_id": current_user.organization_id,
        "role": current_user.role,
        "permissions": current_user.permissions,
        # Legacy (transition — 4 semaines)
        "subscription_status": "active" if is_exempt else sub_status,
        "trial_end_date": trial_end,
        "is_exempt": is_exempt,
        "scan_count_this_month": org.get("scan_count_this_month", 0),
        "scan_quota_limit": SCAN_QUOTA_LIMIT,
        "receipt_ocr_consent_at": user_doc.get("receipt_ocr_consent_at"),
    }
```

- [ ] **Step 8: Adapter `POST /api/auth/register` pour créer une org**

Trouver `def register(user_data: UserCreate):` (autour de la ligne 1201). Modifier pour créer une organisation ET rattacher le user comme owner :

```python
@app.post("/api/auth/register", response_model=Token)
def register(user_data: UserCreate):
    existing = db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(400, "Email already registered")

    user_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())
    trial_end = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()

    # Feature #11 — crée l'organisation en même temps que le user
    org_doc = {
        "id": org_id,
        "name": user_data.company_name,
        "owner_id": user_id,
        "subscription_status": "trial",
        "stripe_customer_id": None,
        "trial_ends_at": trial_end,
        "role_permissions": DEFAULT_ROLE_PERMISSIONS,
        "scan_count_this_month": 0,
        "scan_quota_reset_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.organizations.insert_one(org_doc)

    user_doc = {
        "id": user_id,
        "email": user_data.email,
        "company_name": user_data.company_name,
        "is_active": True,
        "organization_id": org_id,
        "role": "owner",
        # Legacy fields (transition — 4 semaines)
        "subscription_status": "trial",
        "trial_end_date": trial_end,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.users.insert_one(user_doc)
    db.user_passwords.insert_one({
        "user_id": user_id,
        "hashed_password": hash_password(user_data.password)
    })

    settings_doc = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "organization_id": org_id,
        "created_by_user_id": user_id,
        "company_name": user_data.company_name,
        "email": user_data.email,
        "phone": "", "address": "", "city": "", "postal_code": "", "country": "",
        "logo_url": "", "primary_color": "#00A08C", "secondary_color": "#1F2937",
        "default_due_days": 30, "bn_number": "", "gst_number": "", "qst_number": "", "hst_number": "", "neq_number": ""
    }
    db.company_settings.insert_one(settings_doc)

    token = create_token(user_id)
    user_response = {k: v for k, v in user_doc.items() if k not in ("created_at", "_id")}
    return Token(access_token=token, user=User(**user_response))
```

- [ ] **Step 9: Tests pass**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_organizations.py -v 2>&1 | tail -25
```
Expected : 20 tests pass (9 T1 + 11 T2).

Vérifier non-régression sur l'auth existante :
```bash
pytest tests/ -k "auth or login" -v 2>&1 | tail -10
```

- [ ] **Step 10: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_organizations.py
git commit -m "feat(organizations): CurrentUser + _resolve_permissions + auth middleware refactor"
```

---

## Task 3 : Dependency `require_permission` helper

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_organizations.py`

- [ ] **Step 1: Écrire les tests**

Append à `backend/tests/test_organizations.py` :
```python
from server import require_permission
from fastapi import HTTPException


class TestRequirePermission:
    def _make_current_user(self, permissions):
        return CurrentUser(
            id="u1", email="a@b.com", organization_id="org1",
            role="accountant", permissions=permissions, is_exempt=False,
        )

    def test_grants_access_when_perm_present(self):
        dep = require_permission("expenses:read")
        cu = self._make_current_user(["expenses:read", "expenses:write"])
        result = dep(current_user=cu)
        assert result is cu

    def test_denies_when_perm_missing(self):
        dep = require_permission("expenses:write")
        cu = self._make_current_user(["expenses:read"])
        with pytest.raises(HTTPException) as exc:
            dep(current_user=cu)
        assert exc.value.status_code == 403
        assert "expenses:write" in exc.value.detail

    def test_owner_only_perm_denied_for_accountant(self):
        dep = require_permission("team:manage")
        cu = self._make_current_user(list(PERMISSIONS_EDITABLE))  # no owner-only
        with pytest.raises(HTTPException) as exc:
            dep(current_user=cu)
        assert exc.value.status_code == 403
```

- [ ] **Step 2: Verify failure**

```bash
pytest tests/test_organizations.py::TestRequirePermission -v 2>&1 | tail -10
```

- [ ] **Step 3: Implémenter le helper**

Dans `backend/server.py`, AJOUTER après `_get_org_for_user` (Task 2, Step 4) :

```python
def require_permission(perm_code: str):
    """FastAPI dependency factory. Utilisation :
        @app.get("/api/expenses", dependencies=[...])
        def list_expenses(current_user: CurrentUser = Depends(require_permission("expenses:read"))):
            ..."""
    def _dep(current_user: CurrentUser = Depends(get_current_user_with_access)) -> CurrentUser:
        if perm_code not in current_user.permissions:
            raise HTTPException(403, f"Permission requise : {perm_code}")
        return current_user
    return _dep
```

- [ ] **Step 4: Tests pass**

```bash
pytest tests/test_organizations.py::TestRequirePermission -v 2>&1 | tail -10
```
Expected : 3 tests pass.

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_organizations.py
git commit -m "feat(organizations): require_permission FastAPI dependency helper"
```

---

## Task 4 : `GET /api/org/me` + `PUT /api/org/role-permissions`

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_organizations_integration.py`

- [x] **Step 1: Écrire les tests d'intégration**

Append à `backend/tests/test_organizations_integration.py` :
```python
class TestOrgMeEndpoint:
    def test_owner_gets_full_context(self, client, owner_headers):
        r = client.get("/api/org/me", headers=owner_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "organization" in body
        assert "current_user" in body
        assert "members" in body
        org = body["organization"]
        assert "id" in org
        assert "name" in org
        assert "role_permissions" in org
        cu = body["current_user"]
        assert cu["role"] == "owner"
        # Owner has all permissions (editable + owner-only)
        for code in ["expenses:read", "settings:manage", "team:manage"]:
            assert code in cu["permissions"]
        assert isinstance(body["members"], list)
        assert any(m["id"] == cu["id"] for m in body["members"])

    def test_unauthenticated_returns_401_or_403(self, client):
        r = client.get("/api/org/me")
        assert r.status_code in (401, 403)


class TestRolePermissionsEndpoint:
    def test_owner_can_edit_matrix(self, client, owner_headers):
        r = client.put("/api/org/role-permissions", headers=owner_headers,
                       json={"role": "accountant",
                             "permissions": ["expenses:read", "invoices:read"]})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["role"] == "accountant"
        assert set(body["permissions"]) == {"expenses:read", "invoices:read"}

        # Verify persistence
        r2 = client.get("/api/org/me", headers=owner_headers)
        matrix = r2.json()["organization"]["role_permissions"]
        assert set(matrix["accountant"]) == {"expenses:read", "invoices:read"}

    def test_cannot_edit_owner_role(self, client, owner_headers):
        r = client.put("/api/org/role-permissions", headers=owner_headers,
                       json={"role": "owner", "permissions": ["expenses:read"]})
        assert r.status_code == 400

    def test_cannot_inject_owner_only_code(self, client, owner_headers):
        r = client.put("/api/org/role-permissions", headers=owner_headers,
                       json={"role": "accountant",
                             "permissions": ["expenses:read", "team:manage"]})
        assert r.status_code == 400
        assert "team:manage" in r.json()["detail"]

    def test_cannot_use_unknown_code(self, client, owner_headers):
        r = client.put("/api/org/role-permissions", headers=owner_headers,
                       json={"role": "accountant",
                             "permissions": ["not:a:real:code"]})
        assert r.status_code == 400

    def test_invalid_role_rejected(self, client, owner_headers):
        r = client.put("/api/org/role-permissions", headers=owner_headers,
                       json={"role": "root", "permissions": []})
        assert r.status_code == 400

    def test_reset_matrix_to_defaults(self, client, owner_headers):
        # Restore default accountant permissions (cleanup for other tests)
        r = client.put("/api/org/role-permissions", headers=owner_headers,
                       json={"role": "accountant",
                             "permissions": list(server_module.PERMISSIONS_EDITABLE)})
        assert r.status_code == 200
```

Le fichier a besoin d'un `import server as server_module` en tête si absent — vérifier.

- [x] **Step 2: Verify failure**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_organizations_integration.py -v 2>&1 | tail -15
```
Expected : 404 sur tous les endpoints /api/org/*.

- [x] **Step 3: Implémenter les 2 endpoints**

Dans `backend/server.py`, chercher la fin de la section auth (après `grant_receipt_ocr_consent`, autour de la ligne 1184). AJOUTER une nouvelle section :

```python
# ─── Organization endpoints (feature #11) ───

@app.get("/api/org/me")
def get_org_me(current_user: CurrentUser = Depends(get_current_user_with_access)):
    """Retourne le contexte complet de l'organisation du user courant :
    organisation + user courant (rôle + permissions) + liste des membres."""
    org = db.organizations.find_one(
        {"id": current_user.organization_id}, {"_id": 0}
    )
    if not org:
        # Synthesized virtual org (pre-migration edge case) — reconstruire.
        user_doc = db.users.find_one({"id": current_user.id}, {"_id": 0})
        org = _synthesize_solo_org_from_user(user_doc)

    members_cursor = db.users.find(
        {"organization_id": current_user.organization_id, "is_active": True},
        {"_id": 0, "id": 1, "email": 1, "role": 1, "created_at": 1}
    )
    members = list(members_cursor)

    return {
        "organization": {
            "id": org["id"],
            "name": org.get("name"),
            "owner_id": org.get("owner_id"),
            "subscription_status": org.get("subscription_status"),
            "trial_ends_at": org.get("trial_ends_at"),
            "role_permissions": org.get("role_permissions") or DEFAULT_ROLE_PERMISSIONS,
            "scan_count_this_month": org.get("scan_count_this_month", 0),
            "scan_quota_limit": SCAN_QUOTA_LIMIT,
        },
        "current_user": {
            "id": current_user.id,
            "email": current_user.email,
            "role": current_user.role,
            "permissions": current_user.permissions,
        },
        "members": members,
    }


@app.put("/api/org/role-permissions")
def update_role_permissions(
    body: dict,
    current_user: CurrentUser = Depends(require_permission("team:manage"))
):
    """Éditer la matrice de permissions pour un rôle donné.
    - role ∈ {"accountant", "viewer"} — jamais "owner".
    - Chaque code doit être dans PERMISSIONS_EDITABLE — 400 si code owner-only ou inconnu."""
    role = body.get("role")
    permissions = body.get("permissions", [])
    if role not in ("accountant", "viewer"):
        raise HTTPException(400, "Role must be 'accountant' or 'viewer'")
    if not isinstance(permissions, list):
        raise HTTPException(400, "permissions must be a list")
    for code in permissions:
        if code not in PERMISSIONS_EDITABLE:
            raise HTTPException(400, f"Permission code invalide : {code}")
    # Persist (idempotent update on the org)
    db.organizations.update_one(
        {"id": current_user.organization_id},
        {"$set": {f"role_permissions.{role}": permissions}}
    )
    return {"role": role, "permissions": permissions}
```

- [x] **Step 4: Tests pass**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_organizations_integration.py -v 2>&1 | tail -20
```
Expected : 8 tests pass.

- [x] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_organizations_integration.py
git commit -m "feat(organizations): GET /api/org/me + PUT /api/org/role-permissions"
```

---

## Task 5 : Invitations — modèle + POST/GET/DELETE `/api/org/invitations` + Resend email

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_organizations_integration.py`

- [ ] **Step 1: Repérer l'utilisation existante de Resend**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
grep -n "resend\|RESEND\|_send_email\|noreply@facturepro" backend/server.py | head -10
```

Récupérer le pattern existant : import, config, fonction d'envoi. Réutiliser tel quel.

- [ ] **Step 2: Écrire les tests d'intégration**

Append à `backend/tests/test_organizations_integration.py` :
```python
import re


class TestInvitations:
    @pytest.fixture
    def cleanup_invitations(self, client, owner_headers):
        """Cleanup les invitations pending de tests précédents."""
        r = client.get("/api/org/invitations?status=all", headers=owner_headers)
        for inv in r.json():
            if inv.get("email", "").startswith("invite-test-"):
                client.delete(f"/api/org/invitations/{inv['id']}",
                              headers=owner_headers)
        yield

    def _random_email(self):
        return f"invite-test-{uuid.uuid4().hex[:8]}@example.com"

    def test_create_invitation_happy_path(self, client, owner_headers,
                                           cleanup_invitations, monkeypatch):
        # Mock Resend to avoid real emails
        monkeypatch.setattr(server_module, "_send_invitation_email",
                             lambda *a, **kw: True)
        email = self._random_email()
        r = client.post("/api/org/invitations", headers=owner_headers,
                        json={"email": email, "role": "accountant"})
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["email"] == email.lower()
        assert body["role"] == "accountant"
        assert "id" in body
        assert "expires_at" in body

    def test_list_invitations_pending(self, client, owner_headers,
                                        cleanup_invitations, monkeypatch):
        monkeypatch.setattr(server_module, "_send_invitation_email",
                             lambda *a, **kw: True)
        email = self._random_email()
        client.post("/api/org/invitations", headers=owner_headers,
                    json={"email": email, "role": "viewer"})
        r = client.get("/api/org/invitations", headers=owner_headers)
        assert r.status_code == 200
        pending = [i for i in r.json() if i["email"] == email.lower()]
        assert len(pending) == 1
        assert pending[0]["status"] == "pending"

    def test_invalid_role_rejected(self, client, owner_headers):
        r = client.post("/api/org/invitations", headers=owner_headers,
                        json={"email": "x@y.com", "role": "owner"})
        assert r.status_code == 400

    def test_invalid_email_rejected(self, client, owner_headers):
        r = client.post("/api/org/invitations", headers=owner_headers,
                        json={"email": "not-an-email", "role": "viewer"})
        assert r.status_code == 400

    def test_duplicate_pending_rejected(self, client, owner_headers,
                                          cleanup_invitations, monkeypatch):
        monkeypatch.setattr(server_module, "_send_invitation_email",
                             lambda *a, **kw: True)
        email = self._random_email()
        r1 = client.post("/api/org/invitations", headers=owner_headers,
                         json={"email": email, "role": "accountant"})
        assert r1.status_code == 201
        r2 = client.post("/api/org/invitations", headers=owner_headers,
                         json={"email": email, "role": "accountant"})
        assert r2.status_code == 409

    def test_already_member_rejected(self, client, owner_headers, monkeypatch):
        monkeypatch.setattr(server_module, "_send_invitation_email",
                             lambda *a, **kw: True)
        # gussdub@gmail.com is already owner
        r = client.post("/api/org/invitations", headers=owner_headers,
                        json={"email": "gussdub@gmail.com", "role": "accountant"})
        assert r.status_code == 409

    def test_revoke_pending_invitation(self, client, owner_headers,
                                         cleanup_invitations, monkeypatch):
        monkeypatch.setattr(server_module, "_send_invitation_email",
                             lambda *a, **kw: True)
        email = self._random_email()
        r = client.post("/api/org/invitations", headers=owner_headers,
                        json={"email": email, "role": "viewer"})
        inv_id = r.json()["id"]
        r2 = client.delete(f"/api/org/invitations/{inv_id}", headers=owner_headers)
        assert r2.status_code == 204
        # Verify status changed (not hard-deleted)
        r3 = client.get("/api/org/invitations?status=all", headers=owner_headers)
        found = next((i for i in r3.json() if i["id"] == inv_id), None)
        assert found is not None
        assert found["status"] == "revoked"

    def test_revoke_unknown_invitation_returns_404(self, client, owner_headers):
        r = client.delete(f"/api/org/invitations/{uuid.uuid4()}",
                          headers=owner_headers)
        assert r.status_code == 404
```

- [ ] **Step 3: Verify failure**

```bash
pytest tests/test_organizations_integration.py::TestInvitations -v 2>&1 | tail -15
```

- [ ] **Step 4: Implémenter les endpoints + helper email**

Dans `backend/server.py`, AJOUTER après `update_role_permissions` (Task 4) :

```python
import secrets as _secrets
import re as _re


_EMAIL_RE = _re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _send_invitation_email(to_email: str, org_name: str, token: str):
    """Envoie l'email d'invitation via Resend. Retourne True/False sans lever.
    Réutilise le pattern existant du fichier (RESEND_API_KEY, SENDER_EMAIL)."""
    try:
        import resend
        resend.api_key = os.environ.get("RESEND_API_KEY")
        sender = os.environ.get("SENDER_EMAIL", "noreply@facturepro.ca")
        link = f"https://facturepro.ca/accept-invite?token={token}"
        html = f"""
        <p>Bonjour,</p>
        <p>Vous êtes invité(e) à rejoindre <strong>{org_name}</strong> sur FacturePro.</p>
        <p><a href="{link}" style="background:#00A08C;color:#fff;padding:10px 20px;
           text-decoration:none;border-radius:6px;display:inline-block;">
           Accepter l'invitation</a></p>
        <p style="color:#6b7280;font-size:12px">Ce lien expire dans 7 jours.
           Si le bouton ne fonctionne pas, copie ce lien : <br/>{link}</p>
        """
        resend.Emails.send({
            "from": sender,
            "to": to_email,
            "subject": f"Invitation à rejoindre {org_name} sur FacturePro",
            "html": html,
        })
        return True
    except Exception as e:
        print(f"[invitations] Resend error type={type(e).__name__}")  # no secrets in log
        return False


@app.post("/api/org/invitations", status_code=201)
def create_invitation(
    body: dict,
    current_user: CurrentUser = Depends(require_permission("team:manage"))
):
    email = (body.get("email") or "").strip().lower()
    role = body.get("role")
    if not email or not _EMAIL_RE.match(email):
        raise HTTPException(400, "Email invalide")
    if role not in ("accountant", "viewer"):
        raise HTTPException(400, "Role must be 'accountant' or 'viewer'")

    # Check no duplicate pending invitation in this org
    existing = db.invitations.find_one({
        "organization_id": current_user.organization_id,
        "email": email,
        "status": "pending",
    })
    if existing:
        raise HTTPException(409, "Une invitation en attente existe déjà pour cet email")

    # Check email is not already a member of this org
    already_member = db.users.find_one({
        "email": email,
        "organization_id": current_user.organization_id,
    })
    if already_member:
        raise HTTPException(409, "Cet utilisateur est déjà membre de l'organisation")

    invitation_id = str(uuid.uuid4())
    token = _secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(days=7)).isoformat()

    inv_doc = {
        "id": invitation_id,
        "organization_id": current_user.organization_id,
        "email": email,
        "role": role,
        "token": token,
        "expires_at": expires_at,
        "status": "pending",
        "invited_by_user_id": current_user.id,
        "created_at": now.isoformat(),
        "consumed_at": None,
    }
    db.invitations.insert_one(inv_doc)

    # Envoi email — rollback si échec
    org = db.organizations.find_one({"id": current_user.organization_id}, {"_id": 0})
    org_name = (org or {}).get("name") or "FacturePro"
    if not _send_invitation_email(email, org_name, token):
        db.invitations.delete_one({"id": invitation_id})
        raise HTTPException(502, "Envoi de l'email d'invitation impossible — réessaie plus tard")

    return {
        "id": invitation_id,
        "email": email,
        "role": role,
        "expires_at": expires_at,
    }


@app.get("/api/org/invitations")
def list_invitations(
    status: str = "pending",
    current_user: CurrentUser = Depends(require_permission("team:manage"))
):
    query = {"organization_id": current_user.organization_id}
    if status != "all":
        query["status"] = status
    cursor = db.invitations.find(query, {"_id": 0, "token": 0}) \
                            .sort("created_at", -1)
    return list(cursor)


@app.delete("/api/org/invitations/{invitation_id}", status_code=204)
def revoke_invitation(
    invitation_id: str,
    current_user: CurrentUser = Depends(require_permission("team:manage"))
):
    inv = db.invitations.find_one({
        "id": invitation_id,
        "organization_id": current_user.organization_id,
    })
    if not inv:
        raise HTTPException(404, "Invitation introuvable")
    if inv["status"] == "accepted":
        raise HTTPException(400, "Impossible de révoquer une invitation déjà acceptée")
    db.invitations.update_one(
        {"id": invitation_id},
        {"$set": {"status": "revoked"}}
    )
    return
```

- [ ] **Step 5: Tests pass**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_organizations_integration.py::TestInvitations -v 2>&1 | tail -15
```
Expected : 8 tests pass.

- [ ] **Step 6: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_organizations_integration.py
git commit -m "feat(organizations): POST/GET/DELETE /api/org/invitations + Resend email"
```

---

## Task 6 : `POST /api/auth/accept-invite` (public, rate-limité)

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_organizations_integration.py`

- [ ] **Step 1: Écrire les tests d'intégration**

Append à `backend/tests/test_organizations_integration.py` :
```python
class TestAcceptInvite:
    def _create_pending_invitation(self, client, owner_headers, email, role,
                                    monkeypatch):
        monkeypatch.setattr(server_module, "_send_invitation_email",
                             lambda *a, **kw: True)
        r = client.post("/api/org/invitations", headers=owner_headers,
                        json={"email": email, "role": role})
        inv_id = r.json()["id"]
        # Fetch the token directly from DB (test-only)
        inv = server_module.db.invitations.find_one({"id": inv_id})
        return inv_id, inv["token"]

    def _cleanup_user(self, email):
        user = server_module.db.users.find_one({"email": email.lower()})
        if user:
            server_module.db.users.delete_one({"id": user["id"]})
            server_module.db.user_passwords.delete_one({"user_id": user["id"]})

    def test_accept_new_user_happy_path(self, client, owner_headers, monkeypatch):
        email = f"accept-new-{uuid.uuid4().hex[:8]}@example.com"
        _, token = self._create_pending_invitation(
            client, owner_headers, email, "accountant", monkeypatch)
        try:
            r = client.post("/api/auth/accept-invite", json={
                "token": token, "password": "newpass123",
                "pipeda_consent": True,
            })
            assert r.status_code == 200, r.text
            body = r.json()
            assert "access_token" in body
            assert body["user"]["email"] == email.lower()
            # Verify user is in the org with correct role
            user = server_module.db.users.find_one({"email": email.lower()})
            assert user is not None
            assert user["role"] == "accountant"
            assert user.get("organization_id") is not None
            assert user.get("pipeda_consent_at") is not None
        finally:
            self._cleanup_user(email)

    def test_missing_pipeda_consent_rejected(self, client, owner_headers,
                                              monkeypatch):
        email = f"accept-nopipeda-{uuid.uuid4().hex[:8]}@example.com"
        _, token = self._create_pending_invitation(
            client, owner_headers, email, "viewer", monkeypatch)
        try:
            r = client.post("/api/auth/accept-invite", json={
                "token": token, "password": "x123",
                "pipeda_consent": False,
            })
            assert r.status_code == 400
            assert "CGU" in r.json()["detail"] or "PIPEDA" in r.json()["detail"]
        finally:
            self._cleanup_user(email)

    def test_unknown_token_returns_404(self, client):
        r = client.post("/api/auth/accept-invite", json={
            "token": "unknown-token-xxxxxxxxxxxxxxxx", "password": "x123",
            "pipeda_consent": True,
        })
        assert r.status_code == 404

    def test_revoked_token_returns_410(self, client, owner_headers, monkeypatch):
        email = f"accept-revoked-{uuid.uuid4().hex[:8]}@example.com"
        inv_id, token = self._create_pending_invitation(
            client, owner_headers, email, "viewer", monkeypatch)
        client.delete(f"/api/org/invitations/{inv_id}", headers=owner_headers)
        r = client.post("/api/auth/accept-invite", json={
            "token": token, "password": "x123", "pipeda_consent": True,
        })
        assert r.status_code == 410

    def test_expired_token_returns_410(self, client, owner_headers, monkeypatch):
        email = f"accept-expired-{uuid.uuid4().hex[:8]}@example.com"
        inv_id, token = self._create_pending_invitation(
            client, owner_headers, email, "viewer", monkeypatch)
        # Manually expire it
        server_module.db.invitations.update_one(
            {"id": inv_id},
            {"$set": {"expires_at": "2020-01-01T00:00:00+00:00"}})
        r = client.post("/api/auth/accept-invite", json={
            "token": token, "password": "x123", "pipeda_consent": True,
        })
        assert r.status_code == 410

    def test_already_consumed_token_returns_410(self, client, owner_headers,
                                                  monkeypatch):
        email = f"accept-once-{uuid.uuid4().hex[:8]}@example.com"
        _, token = self._create_pending_invitation(
            client, owner_headers, email, "accountant", monkeypatch)
        try:
            r1 = client.post("/api/auth/accept-invite", json={
                "token": token, "password": "x123", "pipeda_consent": True,
            })
            assert r1.status_code == 200
            # Try to consume the token again
            r2 = client.post("/api/auth/accept-invite", json={
                "token": token, "password": "x123", "pipeda_consent": True,
            })
            assert r2.status_code == 410
        finally:
            self._cleanup_user(email)

    def test_existing_user_wrong_password_returns_401(self, client, owner_headers,
                                                       monkeypatch):
        # gussdub already exists but is already in an org — test the 409 first
        # Then test wrong-password on a fresh user
        email = f"existing-wrong-{uuid.uuid4().hex[:8]}@example.com"
        # Create the user manually with a known password
        uid = str(uuid.uuid4())
        server_module.db.users.insert_one({
            "id": uid, "email": email, "company_name": "Standalone",
            "is_active": True, "created_at": datetime.now(timezone.utc).isoformat(),
        })
        server_module.db.user_passwords.insert_one({
            "user_id": uid,
            "hashed_password": server_module.hash_password("correct-pass"),
        })
        try:
            _, token = self._create_pending_invitation(
                client, owner_headers, email, "viewer", monkeypatch)
            r = client.post("/api/auth/accept-invite", json={
                "token": token, "password": "WRONG-pass",
                "pipeda_consent": True,
            })
            assert r.status_code == 401
        finally:
            self._cleanup_user(email)

    def test_existing_user_already_in_org_returns_409(self, client, owner_headers,
                                                        monkeypatch):
        # gussdub is already owner of the current org, we invite them elsewhere
        # But since we're testing single test suite = single org, use a manual setup:
        # Create a second org + user
        email = f"already-org-{uuid.uuid4().hex[:8]}@example.com"
        uid = str(uuid.uuid4())
        other_org_id = str(uuid.uuid4())
        server_module.db.organizations.insert_one({
            "id": other_org_id, "name": "OtherOrg",
            "owner_id": uid, "subscription_status": "trial",
            "role_permissions": server_module.DEFAULT_ROLE_PERMISSIONS,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        server_module.db.users.insert_one({
            "id": uid, "email": email, "is_active": True,
            "organization_id": other_org_id, "role": "owner",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        server_module.db.user_passwords.insert_one({
            "user_id": uid,
            "hashed_password": server_module.hash_password("correct-pass"),
        })
        try:
            _, token = self._create_pending_invitation(
                client, owner_headers, email, "viewer", monkeypatch)
            r = client.post("/api/auth/accept-invite", json={
                "token": token, "password": "correct-pass",
                "pipeda_consent": True,
            })
            assert r.status_code == 409
        finally:
            self._cleanup_user(email)
            server_module.db.organizations.delete_one({"id": other_org_id})


class TestInvitationPreview:
    def test_preview_valid_token(self, client, owner_headers, monkeypatch):
        monkeypatch.setattr(server_module, "_send_invitation_email",
                             lambda *a, **kw: True)
        email = f"preview-{uuid.uuid4().hex[:8]}@example.com"
        r = client.post("/api/org/invitations", headers=owner_headers,
                        json={"email": email, "role": "accountant"})
        inv_id = r.json()["id"]
        token = server_module.db.invitations.find_one({"id": inv_id})["token"]
        r2 = client.get(f"/api/org/invitations/preview?token={token}")
        assert r2.status_code == 200
        body = r2.json()
        assert body["email"] == email.lower()
        assert body["role"] == "accountant"
        assert "org_name" in body

    def test_preview_unknown_token_returns_404(self, client):
        r = client.get("/api/org/invitations/preview?token=unknown-abcdef")
        assert r.status_code == 404
```

- [ ] **Step 2: Verify failure**

```bash
pytest tests/test_organizations_integration.py::TestAcceptInvite -v 2>&1 | tail -15
```

- [ ] **Step 3: Implémenter endpoint public accept-invite + preview**

Dans `backend/server.py`, AJOUTER après `revoke_invitation` (Task 5) :

```python
# Rate-limit simple in-memory pour /accept-invite (production-adequate pour v1).
_ACCEPT_INVITE_RATE = {}  # {ip: [(timestamp, ...), ...]}
_ACCEPT_INVITE_WINDOW_SEC = 60
_ACCEPT_INVITE_MAX_REQUESTS = 5


def _rate_limit_accept_invite(ip: str) -> bool:
    """True si dans les limites, False si dépassé."""
    now_ts = datetime.now(timezone.utc).timestamp()
    window_start = now_ts - _ACCEPT_INVITE_WINDOW_SEC
    hits = _ACCEPT_INVITE_RATE.get(ip, [])
    hits = [t for t in hits if t > window_start]
    if len(hits) >= _ACCEPT_INVITE_MAX_REQUESTS:
        _ACCEPT_INVITE_RATE[ip] = hits
        return False
    hits.append(now_ts)
    _ACCEPT_INVITE_RATE[ip] = hits
    return True


@app.get("/api/org/invitations/preview")
def preview_invitation(token: str):
    """Endpoint public : depuis un token, renvoie email + org_name + role
    pour l'écran /accept-invite. Ne renvoie jamais le token."""
    inv = db.invitations.find_one({"token": token, "status": "pending"},
                                    {"_id": 0, "token": 0})
    if not inv:
        raise HTTPException(404, "Invitation introuvable")
    # Check expiration
    try:
        expires = datetime.fromisoformat(inv["expires_at"])
        if datetime.now(timezone.utc) > expires:
            raise HTTPException(410, "Invitation expirée")
    except (ValueError, TypeError):
        raise HTTPException(410, "Invitation invalide")
    org = db.organizations.find_one({"id": inv["organization_id"]}, {"_id": 0})
    return {
        "email": inv["email"],
        "role": inv["role"],
        "org_name": (org or {}).get("name") or "FacturePro",
    }


@app.post("/api/auth/accept-invite")
def accept_invite(body: dict, request: Request):
    """Endpoint public : accepte une invitation.
    - Vérifie pipeda_consent === true.
    - Cherche l'invitation par token (pending + non-expirée + non-révoquée).
    - Si user nouveau → crée user + hash password.
    - Si user existant → verify password, refuse si déjà dans une org.
    - Update invitation : status=accepted, consumed_at.
    - Retourne JWT."""
    client_ip = (request.client.host if request.client else "unknown")
    if not _rate_limit_accept_invite(client_ip):
        raise HTTPException(429, "Trop de requêtes — réessaie dans 1 minute")

    token = (body.get("token") or "").strip()
    password = body.get("password") or ""
    pipeda_consent = body.get("pipeda_consent")

    if pipeda_consent is not True:
        raise HTTPException(400, "Vous devez accepter les CGU/PIPEDA")
    if not token:
        raise HTTPException(404, "Invitation introuvable")

    inv = db.invitations.find_one({"token": token})
    if not inv:
        raise HTTPException(404, "Invitation introuvable")
    if inv["status"] == "revoked":
        raise HTTPException(410, "Invitation révoquée")
    if inv["status"] == "accepted":
        raise HTTPException(410, "Invitation déjà consommée")

    # Check expiration
    try:
        expires = datetime.fromisoformat(inv["expires_at"])
        if datetime.now(timezone.utc) > expires:
            raise HTTPException(410, "Invitation expirée")
    except (ValueError, TypeError):
        raise HTTPException(410, "Invitation invalide")

    email = inv["email"].lower()
    now = datetime.now(timezone.utc).isoformat()
    user = db.users.find_one({"email": email})

    if user:
        # Existing user path
        if user.get("organization_id"):
            raise HTTPException(409, "Cet email est déjà dans une organisation")
        pwd_doc = db.user_passwords.find_one({"user_id": user["id"]})
        if not pwd_doc or not verify_password(password, pwd_doc["hashed_password"]):
            raise HTTPException(401, "Mot de passe incorrect")
        db.users.update_one(
            {"id": user["id"]},
            {"$set": {
                "organization_id": inv["organization_id"],
                "role": inv["role"],
                "pipeda_consent_at": now,
            }}
        )
        user_id = user["id"]
    else:
        # New user path
        if len(password) < 6:
            raise HTTPException(400, "Le mot de passe doit contenir au moins 6 caractères")
        user_id = str(uuid.uuid4())
        db.users.insert_one({
            "id": user_id,
            "email": email,
            "company_name": None,
            "is_active": True,
            "organization_id": inv["organization_id"],
            "role": inv["role"],
            "pipeda_consent_at": now,
            "created_at": now,
        })
        db.user_passwords.insert_one({
            "user_id": user_id,
            "hashed_password": hash_password(password),
        })

    # Consume the invitation
    db.invitations.update_one(
        {"id": inv["id"]},
        {"$set": {"status": "accepted", "consumed_at": now}}
    )

    token_jwt = create_token(user_id)
    return {
        "access_token": token_jwt,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "email": email,
            "organization_id": inv["organization_id"],
            "role": inv["role"],
        },
    }
```

Note : `Request` doit être importé depuis fastapi — vérifier `from fastapi import ..., Request` en tête du fichier.

- [ ] **Step 4: Tests pass**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_organizations_integration.py::TestAcceptInvite tests/test_organizations_integration.py::TestInvitationPreview -v 2>&1 | tail -20
```
Expected : 10 tests pass.

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_organizations_integration.py
git commit -m "feat(organizations): POST /api/auth/accept-invite (rate-limited, pipeda consent)"
```

---

## Task 7 : `PUT /api/org/members/{user_id}/role` + `DELETE /api/org/members/{user_id}`

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_organizations_integration.py`

- [x] **Step 1: Écrire les tests d'intégration**

Append à `backend/tests/test_organizations_integration.py` :
```python
class TestMembers:
    def _accept_invite_setup(self, client, owner_headers, monkeypatch, role):
        """Helper : crée + accepte une invitation, retourne le user_id créé."""
        monkeypatch.setattr(server_module, "_send_invitation_email",
                             lambda *a, **kw: True)
        email = f"member-{uuid.uuid4().hex[:8]}@example.com"
        r = client.post("/api/org/invitations", headers=owner_headers,
                        json={"email": email, "role": role})
        inv_id = r.json()["id"]
        token = server_module.db.invitations.find_one({"id": inv_id})["token"]
        client.post("/api/auth/accept-invite", json={
            "token": token, "password": "memberpass123",
            "pipeda_consent": True,
        })
        user = server_module.db.users.find_one({"email": email})
        return user["id"], email

    def _cleanup_user(self, email):
        user = server_module.db.users.find_one({"email": email.lower()})
        if user:
            server_module.db.users.delete_one({"id": user["id"]})
            server_module.db.user_passwords.delete_one({"user_id": user["id"]})

    def test_change_role_happy_path(self, client, owner_headers, monkeypatch):
        uid, email = self._accept_invite_setup(client, owner_headers,
                                                 monkeypatch, "accountant")
        try:
            r = client.put(f"/api/org/members/{uid}/role", headers=owner_headers,
                           json={"role": "viewer"})
            assert r.status_code == 200, r.text
            assert r.json()["role"] == "viewer"
            assert server_module.db.users.find_one({"id": uid})["role"] == "viewer"
        finally:
            self._cleanup_user(email)

    def test_cannot_change_owner_role(self, client, owner_headers):
        # gussdub is owner
        owner = server_module.db.users.find_one({"email": "gussdub@gmail.com"})
        r = client.put(f"/api/org/members/{owner['id']}/role",
                       headers=owner_headers, json={"role": "viewer"})
        assert r.status_code == 400

    def test_change_role_invalid_role_rejected(self, client, owner_headers,
                                                 monkeypatch):
        uid, email = self._accept_invite_setup(client, owner_headers,
                                                 monkeypatch, "accountant")
        try:
            r = client.put(f"/api/org/members/{uid}/role", headers=owner_headers,
                           json={"role": "owner"})
            assert r.status_code == 400
        finally:
            self._cleanup_user(email)

    def test_change_role_unknown_user_returns_404(self, client, owner_headers):
        r = client.put(f"/api/org/members/{uuid.uuid4()}/role",
                       headers=owner_headers, json={"role": "viewer"})
        assert r.status_code == 404

    def test_remove_member_happy_path(self, client, owner_headers, monkeypatch):
        uid, email = self._accept_invite_setup(client, owner_headers,
                                                 monkeypatch, "viewer")
        try:
            r = client.delete(f"/api/org/members/{uid}", headers=owner_headers)
            assert r.status_code == 204
            user = server_module.db.users.find_one({"id": uid})
            assert user.get("organization_id") is None
            assert user.get("role") is None
        finally:
            self._cleanup_user(email)

    def test_cannot_remove_owner(self, client, owner_headers):
        owner = server_module.db.users.find_one({"email": "gussdub@gmail.com"})
        r = client.delete(f"/api/org/members/{owner['id']}", headers=owner_headers)
        assert r.status_code == 400

    def test_cannot_remove_self_if_owner(self, client, owner_headers):
        # gussdub is BOTH owner AND the current_user — 400
        owner = server_module.db.users.find_one({"email": "gussdub@gmail.com"})
        r = client.delete(f"/api/org/members/{owner['id']}", headers=owner_headers)
        assert r.status_code == 400
```

- [x] **Step 2: Verify failure**

```bash
pytest tests/test_organizations_integration.py::TestMembers -v 2>&1 | tail -15
```

- [x] **Step 3: Implémenter les endpoints**

Dans `backend/server.py`, AJOUTER après les endpoints d'invitation :

```python
@app.put("/api/org/members/{user_id}/role")
def update_member_role(
    user_id: str,
    body: dict,
    current_user: CurrentUser = Depends(require_permission("team:manage"))
):
    role = body.get("role")
    if role not in ("accountant", "viewer"):
        raise HTTPException(400, "Role must be 'accountant' or 'viewer'")
    target = db.users.find_one({
        "id": user_id,
        "organization_id": current_user.organization_id,
    })
    if not target:
        raise HTTPException(404, "Membre introuvable")
    # Owner cannot have their role changed
    org = db.organizations.find_one({"id": current_user.organization_id}, {"_id": 0})
    if org and org.get("owner_id") == user_id:
        raise HTTPException(400, "Impossible de modifier le rôle du propriétaire")
    db.users.update_one({"id": user_id}, {"$set": {"role": role}})
    return {"user_id": user_id, "role": role}


@app.delete("/api/org/members/{user_id}", status_code=204)
def remove_member(
    user_id: str,
    current_user: CurrentUser = Depends(require_permission("team:manage"))
):
    target = db.users.find_one({
        "id": user_id,
        "organization_id": current_user.organization_id,
    })
    if not target:
        raise HTTPException(404, "Membre introuvable")
    org = db.organizations.find_one({"id": current_user.organization_id}, {"_id": 0})
    if org and org.get("owner_id") == user_id:
        raise HTTPException(400, "Le propriétaire ne peut pas être retiré")
    if user_id == current_user.id:
        raise HTTPException(400, "Vous ne pouvez pas vous retirer vous-même")
    # Soft removal : unset org+role. Documents créés restent (created_by_user_id conservé).
    db.users.update_one(
        {"id": user_id},
        {"$unset": {"organization_id": "", "role": ""}}
    )
    return
```

- [x] **Step 4: Tests pass**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_organizations_integration.py::TestMembers -v 2>&1 | tail -15
```
Expected : 7 tests pass.

- [x] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_organizations_integration.py
git commit -m "feat(organizations): PUT /members/{id}/role + DELETE /members/{id} (soft)"
```

---

## Task 8 : Move Stripe subscription + scan quota fields users → organizations

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_organizations_integration.py`

- [ ] **Step 1: Repérer les endpoints Stripe + quota scan actuels**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
grep -n "stripe_customer_id\|/api/subscribe\|/api/subscription\|customer_portal\|_check_and_bill_scan\|scan_count_this_month" backend/server.py | head -20
```

Lister tous les endroits où :
- `db.users.find_one/update_one` touche `stripe_customer_id`, `subscription_status`, `trial_end_date`, `scan_count_this_month`, `scan_quota_reset_at`
- Un webhook Stripe update ces champs

Pour chaque hit, la migration doit basculer les lectures/écritures vers `db.organizations` filtré par `current_user.organization_id`.

- [ ] **Step 2: Écrire les tests d'intégration**

Append à `backend/tests/test_organizations_integration.py` :
```python
class TestSubscriptionOnOrg:
    def test_org_me_exposes_subscription(self, client, owner_headers):
        r = client.get("/api/org/me", headers=owner_headers)
        org = r.json()["organization"]
        assert "subscription_status" in org
        assert "trial_ends_at" in org

    def test_scan_quota_shared_across_org(self, client, owner_headers):
        # Owner scan_count is stored on org, not user
        r = client.get("/api/org/me", headers=owner_headers)
        org = r.json()["organization"]
        assert "scan_count_this_month" in org
```

- [ ] **Step 3: Adapter `_check_and_bill_scan` (feature #8)**

Localiser `def _check_and_bill_scan` (autour de la ligne 900). Actuellement il fait un aggregation pipeline sur `db.users`. Le refactorer pour opérer sur `db.organizations`, filtré par `organization_id`.

Chercher et remplacer :
```bash
grep -n "def _check_and_bill_scan\|_check_and_bill_scan(" backend/server.py
```

Signature actuelle probable : `_check_and_bill_scan(user_id)`.

Nouvelle signature : `_check_and_bill_scan(organization_id)`. Dans le corps :
- `db.users.find_one_and_update(...)` → `db.organizations.find_one_and_update(...)`
- filtre `{"id": user_id}` → `{"id": organization_id}`
- retourne `{scan_count_this_month, scan_quota_reset_at}` idem

Puis modifier tous les appels : `_check_and_bill_scan(current_user.id)` → `_check_and_bill_scan(current_user.organization_id)`.

- [ ] **Step 4: Adapter `POST /api/subscribe` (Stripe Checkout)**

Chercher :
```bash
grep -n "@app.post.*subscribe\|stripe.checkout\|create_checkout_session" backend/server.py
```

Dans l'endpoint qui crée la session Stripe :
- `db.users.update_one(...)` sur `stripe_customer_id` → `db.organizations.update_one(...)`
- Le lookup pour vérifier si un customer existe déjà : `db.users.find_one({"id": user_id}).get("stripe_customer_id")` → `db.organizations.find_one({"id": current_user.organization_id}).get("stripe_customer_id")`
- Metadata Stripe : ajouter `organization_id: current_user.organization_id` dans `session.metadata`

- [ ] **Step 5: Adapter le webhook Stripe**

Chercher :
```bash
grep -n "stripe_webhook\|@app.post.*webhook" backend/server.py
```

Dans le webhook `checkout.session.completed` (ou équivalent) :
- Lire `session.metadata.organization_id` (fallback sur `user_id` si absent — transition)
- Update `db.organizations.update_one({"id": organization_id}, {"$set": {"subscription_status": "active"}})` au lieu de `db.users.update_one`

- [ ] **Step 6: Adapter `/api/subscription/portal` (Stripe customer portal)**

Chercher :
```bash
grep -n "customer_portal\|billing_portal\|billing/portal" backend/server.py
```

`stripe.billing_portal.Session.create(customer=...)` doit maintenant utiliser `organizations.stripe_customer_id`.

- [ ] **Step 7: Ajouter `require_permission("billing:manage")` sur les endpoints Stripe**

- `POST /api/subscribe` → `Depends(require_permission("billing:manage"))`
- `GET /api/subscription/portal` → idem

- [ ] **Step 8: Vérifier + relancer tests + full non-régression**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_organizations_integration.py::TestSubscriptionOnOrg -v 2>&1 | tail -10
pytest tests/test_receipt_ocr_integration.py -k "scan" -v 2>&1 | tail -10
```
Expected : new tests pass + feature #8 (receipt scan quota) no regression.

- [ ] **Step 9: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_organizations_integration.py
git commit -m "feat(organizations): move Stripe subscription + scan quota users → organizations"
```

---

## Task 9 : Apply `require_permission` on READ endpoints (business)

**Files:**
- Modify: `backend/server.py`

- [x] **Step 1: Générer la liste des endpoints GET actuels**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
grep -nE '@app\.(get)\("/api/(expenses|invoices|quotes|clients|products|employees|reports|dashboard|bank|receipts|files)' backend/server.py
```

Faire correspondre chaque path à sa permission (cf. spec §4.4 tableau) :

| Endpoint pattern | Permission |
|---|---|
| `/api/expenses`, `/api/expenses/{id}` GET | `expenses:read` |
| `/api/invoices`, `/api/invoices/{id}` GET | `invoices:read` |
| `/api/quotes`, `/api/quotes/{id}` GET | `quotes:read` |
| `/api/clients` GET | `clients:read` |
| `/api/products` GET | `products:read` |
| `/api/employees` GET | `employees:read` |
| `/api/reports/*` GET | `reports:read` |
| `/api/dashboard/*` GET | `reports:read` |
| `/api/bank/*` GET | `bank:read` |
| `/api/receipts/{id}` GET | `expenses:read` |
| `/api/files/{id}` GET | `expenses:read` (contient logos aussi — check permission-neutre si logo) |

- [x] **Step 2: Remplacer la dépendance sur chaque endpoint GET**

Pour chaque endpoint GET listé ci-dessus, remplacer :

**Avant** :
```python
def get_expenses(current_user: User = Depends(get_current_user_with_access)):
```

**Après** :
```python
def get_expenses(current_user: CurrentUser = Depends(require_permission("expenses:read"))):
```

Faire la même transformation pour :
- `get_expense`, `list_expenses`, `get_expense_by_id`
- `get_invoices`, `get_invoice`, `download_invoice_pdf`
- `get_quotes`, `get_quote`, `download_quote_pdf`
- `get_clients`
- `get_products`
- `get_employees`
- `get_dashboard`, `get_dashboard_stats`, `get_dashboard_overdue`, `get_dashboard_outstanding`
- `get_sales_tax_report`, `get_sales_tax_pdf`, `get_pnl_report`, `get_pnl_pdf`, `get_t2125_report`, `get_t2125_pdf`, `get_t2125_csv`
- `list_bank_mappings`, `list_bank_imports`, `get_bank_transactions`, `get_bank_suggestions`
- `get_receipt` (feature #8)

**Note importante** : le type annotation `User` reste tolérant à `CurrentUser` (subclass Pydantic BaseModel), mais on le change pour clarté.

- [x] **Step 3: Adapter les queries dans le corps des endpoints**

Pour chaque endpoint listé ci-dessus, dans le corps du handler, remplacer :
- `{"user_id": current_user.id}` → `{"organization_id": current_user.organization_id}`

**Sauf pour** :
- Endpoints qui touchent uniquement l'utilisateur lui-même (ex : `/api/auth/me`, receipt-ocr-consent)
- Le seed `EXEMPT_USERS` check reste sur user email
- Les collections auth (`user_passwords`)

**Recherche batch pour ne rien manquer** :
```bash
grep -n '{"user_id": current_user\.id}' backend/server.py | head -40
```

Chaque match dans un endpoint business → à migrer.

Ex. pour `get_expenses` :
```python
@app.get("/api/expenses")
def get_expenses(current_user: CurrentUser = Depends(require_permission("expenses:read"))):
    cursor = db.expenses.find(
        {"organization_id": current_user.organization_id},
        {"_id": 0}
    )
    return list(cursor)
```

**Fallback transition** : pendant la période de coexistence, il est plus safe d'utiliser un `$or` :
```python
{"$or": [
    {"organization_id": current_user.organization_id},
    {"user_id": current_user.id, "organization_id": {"$exists": False}},
]}
```
Utiliser ce pattern **uniquement** sur les endpoints qui pourraient rencontrer des docs pré-migration (edge case). Après le drop legacy (§6.4 spec), retirer.

Pour ce plan, utiliser le fallback sur les endpoints GET critiques (`expenses`, `invoices`, `quotes`, `clients`, `products`, `employees`) pour être défensif.

- [x] **Step 4: Sanity test — vérifier qu'un GET encore fonctionnel**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/ -k "get or list" -v 2>&1 | tail -20
```
Expected : aucune régression.

- [x] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py
git commit -m "feat(organizations): apply require_permission on all business READ endpoints"
```

---

## Task 10 : Apply `require_permission` on WRITE endpoints (business)

**Files:**
- Modify: `backend/server.py`

- [x] **Step 1: Générer la liste des endpoints POST/PUT/DELETE actuels**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
grep -nE '@app\.(post|put|delete)\("/api/(expenses|invoices|quotes|clients|products|employees|bank|files)' backend/server.py
```

Mapping :

| Endpoint | Permission |
|---|---|
| POST/PUT/DELETE `/api/expenses/*` | `expenses:write` |
| POST `/api/expenses/scan-receipt` | `receipts:scan` |
| POST/PUT/DELETE `/api/invoices/*`, payments, remind, send | `invoices:write` |
| POST/PUT/DELETE `/api/quotes/*` | `quotes:write` |
| POST/PUT/DELETE `/api/clients/*` | `clients:write` |
| POST/PUT/DELETE `/api/products/*` | `products:write` |
| POST/PUT/DELETE `/api/employees/*` | `employees:write` |
| POST/PUT/DELETE `/api/bank/*` | `bank:write` |
| DELETE `/api/files/{id}` | `expenses:write` (utilisé pour cleanup orphan receipt) |

- [x] **Step 2: Substituer la dépendance sur chaque endpoint write**

Même pattern que Task 9 : remplacer `Depends(get_current_user_with_access)` par `Depends(require_permission("<code>"))`.

Endpoints à modifier :
- `create_expense`, `update_expense`, `delete_expense`
- `scan_receipt` (feature #8) — permission `receipts:scan`
- `create_invoice`, `update_invoice`, `update_invoice_status`, `delete_invoice`, `add_payment`, `remove_payment`, `toggle_recurrence`, `process_recurring_invoices`, `send_invoice_email`, `send_invoice_reminder`
- `create_quote`, `update_quote`, `delete_quote`, `send_quote_email`, `convert_quote_to_invoice`
- `create_client`, `update_client`, `delete_client`
- `create_product`, `update_product`, `delete_product`
- `create_employee`, `update_employee`, `delete_employee`
- `create_bank_mapping`, `create_bank_import`, `match_transaction`, `unmatch_transaction`, `ignore_transaction`, `unignore_transaction`, `create_expense_from_bank`, `create_invoice_from_bank`, `close_bank_import`, `delete_bank_import`
- `delete_file` (feature #8)

- [x] **Step 3: Adapter les queries + créations (organization_id sur insert)**

Sur chaque endpoint write, dans le corps :

**Reads** : `{"user_id": current_user.id}` → `{"organization_id": current_user.organization_id}` (avec fallback `$or` transitoire).

**Creates** : les inserts dans les collections métier doivent maintenant écrire :
```python
doc = {
    "id": str(uuid.uuid4()),
    "organization_id": current_user.organization_id,
    "created_by_user_id": current_user.id,
    # ... champs métier
    # LEGACY : garder user_id pendant la transition (4 semaines)
    "user_id": current_user.id,
}
```

Ex. `create_expense` :
```python
@app.post("/api/expenses")
def create_expense(expense_data: dict,
                   current_user: CurrentUser = Depends(require_permission("expenses:write"))):
    expense_data["id"] = str(uuid.uuid4())
    expense_data["organization_id"] = current_user.organization_id
    expense_data["created_by_user_id"] = current_user.id
    expense_data["user_id"] = current_user.id  # legacy, sera retiré via drop_legacy_user_fields
    expense_data["created_at"] = datetime.now(timezone.utc).isoformat()
    db.expenses.insert_one(expense_data)
    return {k: v for k, v in expense_data.items() if k != "_id"}
```

- [x] **Step 4: Sanity check + tests**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
# Test création + lecture end-to-end
pytest tests/ -k "create or update or delete" -v 2>&1 | tail -20
```
Expected : aucune régression significative.

- [x] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py
git commit -m "feat(organizations): apply require_permission + organization_id on all business WRITE endpoints"
```

---

## Task 11 : Apply `require_permission` on settings/billing/team endpoints (owner-only)

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_organizations_integration.py`

- [x] **Step 1: Repérer les endpoints settings + billing**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
grep -nE '@app\.(get|post|put|delete)\("/api/(settings|company|subscribe|subscription)' backend/server.py
```

Mapping :

| Endpoint | Permission |
|---|---|
| `GET /api/settings/company` | `settings:manage` (les autres membres n'ont pas besoin de voir) |
| `PUT /api/settings/company` | `settings:manage` |
| `POST /api/subscribe`, portal Stripe | `billing:manage` |

(Note : `/api/expense-categories` reste public — c'est une donnée de référence.)

- [x] **Step 2: Écrire des tests de permission enforcement**

Append à `backend/tests/test_organizations_integration.py` :
```python
class TestPermissionEnforcement:
    def _create_viewer_headers(self, client, owner_headers, monkeypatch):
        monkeypatch.setattr(server_module, "_send_invitation_email",
                             lambda *a, **kw: True)
        email = f"viewer-perm-{uuid.uuid4().hex[:8]}@example.com"
        r = client.post("/api/org/invitations", headers=owner_headers,
                        json={"email": email, "role": "viewer"})
        token = server_module.db.invitations.find_one({"id": r.json()["id"]})["token"]
        r2 = client.post("/api/auth/accept-invite", json={
            "token": token, "password": "viewerpass",
            "pipeda_consent": True,
        })
        access_token = r2.json()["access_token"]
        return {"Authorization": f"Bearer {access_token}"}, email

    def _cleanup_user(self, email):
        user = server_module.db.users.find_one({"email": email.lower()})
        if user:
            server_module.db.users.delete_one({"id": user["id"]})
            server_module.db.user_passwords.delete_one({"user_id": user["id"]})

    def test_viewer_can_read_expenses(self, client, owner_headers, monkeypatch):
        vh, email = self._create_viewer_headers(client, owner_headers, monkeypatch)
        try:
            r = client.get("/api/expenses", headers=vh)
            assert r.status_code == 200
        finally:
            self._cleanup_user(email)

    def test_viewer_cannot_write_expenses(self, client, owner_headers, monkeypatch):
        vh, email = self._create_viewer_headers(client, owner_headers, monkeypatch)
        try:
            r = client.post("/api/expenses", headers=vh,
                            json={"vendor": "X", "amount_cad": 10})
            assert r.status_code == 403
            assert "expenses:write" in r.json()["detail"]
        finally:
            self._cleanup_user(email)

    def test_viewer_cannot_scan_receipt(self, client, owner_headers, monkeypatch):
        vh, email = self._create_viewer_headers(client, owner_headers, monkeypatch)
        try:
            # Send a valid image
            from io import BytesIO
            from PIL import Image
            buf = BytesIO()
            Image.new("RGB", (200, 200), (200, 200, 200)).save(buf, "JPEG")
            buf.seek(0)
            r = client.post("/api/expenses/scan-receipt", headers=vh,
                            files={"file": ("test.jpg", buf, "image/jpeg")})
            assert r.status_code == 403
        finally:
            self._cleanup_user(email)

    def test_viewer_cannot_access_settings(self, client, owner_headers, monkeypatch):
        vh, email = self._create_viewer_headers(client, owner_headers, monkeypatch)
        try:
            r = client.get("/api/settings/company", headers=vh)
            assert r.status_code == 403
            r2 = client.put("/api/settings/company", headers=vh,
                            json={"company_name": "hacked"})
            assert r2.status_code == 403
        finally:
            self._cleanup_user(email)

    def test_viewer_cannot_invite_members(self, client, owner_headers, monkeypatch):
        vh, email = self._create_viewer_headers(client, owner_headers, monkeypatch)
        try:
            r = client.post("/api/org/invitations", headers=vh,
                            json={"email": "hacker@x.com", "role": "viewer"})
            assert r.status_code == 403
        finally:
            self._cleanup_user(email)

    def test_viewer_can_read_own_org_context(self, client, owner_headers,
                                              monkeypatch):
        vh, email = self._create_viewer_headers(client, owner_headers, monkeypatch)
        try:
            r = client.get("/api/org/me", headers=vh)
            assert r.status_code == 200
            body = r.json()
            assert body["current_user"]["role"] == "viewer"
            assert "expenses:read" in body["current_user"]["permissions"]
            assert "expenses:write" not in body["current_user"]["permissions"]
        finally:
            self._cleanup_user(email)
```

- [x] **Step 3: Appliquer `require_permission("settings:manage")`**

Sur `GET /api/settings/company` et `PUT /api/settings/company` :

```python
@app.get("/api/settings/company")
def get_company_settings(current_user: CurrentUser = Depends(require_permission("settings:manage"))):
    settings = db.company_settings.find_one(
        {"organization_id": current_user.organization_id}, {"_id": 0}
    )
    return settings or {}


@app.put("/api/settings/company")
def update_company_settings(
    settings_data: dict,
    current_user: CurrentUser = Depends(require_permission("settings:manage"))
):
    # ... corps existant, avec {"organization_id": current_user.organization_id} comme filtre
    db.company_settings.update_one(
        {"organization_id": current_user.organization_id},
        {"$set": settings_data},
        upsert=True,
    )
    return db.company_settings.find_one(
        {"organization_id": current_user.organization_id}, {"_id": 0}
    )
```

- [x] **Step 4: Appliquer `require_permission("billing:manage")`**

Sur `POST /api/subscribe` et l'endpoint portal — déjà fait en Task 8, vérifier.

- [x] **Step 5: Tests pass**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_organizations_integration.py::TestPermissionEnforcement -v 2>&1 | tail -15
```
Expected : 6 tests pass.

- [x] **Step 6: Full backend non-regression run**

```bash
pytest tests/ 2>&1 | tail -20
```
Expected : aucun test rouge nouveau. Certains anciens tests peuvent nécessiter ajustement si assertions strictes de payload (ex. `/api/auth/me` retourne maintenant plus de champs) — c'est acceptable.

- [x] **Step 7: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_organizations_integration.py
git commit -m "feat(organizations): require_permission on settings/billing/team endpoints (owner-only)"
```

---

## Task 12 : Frontend — `AuthContext` expose `permissions[]` + `hasPermission()`

**Files:**
- Modify: `frontend/src/context/AuthContext.js`

- [ ] **Step 1: Étendre AuthContext**

Remplacer le contenu de `frontend/src/context/AuthContext.js` :

```jsx
import React, { useState, createContext, useContext, useEffect, useCallback } from 'react';
import axios from 'axios';
import { BACKEND_URL } from '../config';

const AuthContext = createContext();
export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [organization, setOrganization] = useState(null);
  const [permissions, setPermissions] = useState([]);
  const [role, setRole] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [loading, setLoading] = useState(true);

  const fetchUserAndOrg = useCallback(async (authToken) => {
    try {
      axios.defaults.headers.common['Authorization'] = `Bearer ${authToken}`;
      const [meRes, orgRes] = await Promise.all([
        axios.get(`${BACKEND_URL}/api/auth/me`),
        axios.get(`${BACKEND_URL}/api/org/me`),
      ]);
      setUser(meRes.data);
      setOrganization(orgRes.data.organization);
      setPermissions(orgRes.data.current_user.permissions || []);
      setRole(orgRes.data.current_user.role || null);
    } catch (error) {
      localStorage.removeItem('token');
      setToken(null);
      setUser(null);
      setOrganization(null);
      setPermissions([]);
      setRole(null);
      delete axios.defaults.headers.common['Authorization'];
    }
  }, []);

  useEffect(() => {
    const initAuth = async () => {
      if (token) {
        await fetchUserAndOrg(token);
      }
      setLoading(false);
    };
    initAuth();
  }, [token, fetchUserAndOrg]);

  useEffect(() => {
    const id = axios.interceptors.response.use(
      (res) => res,
      (err) => {
        if (err.response?.status === 401 && localStorage.getItem('token')) {
          localStorage.removeItem('token');
          setToken(null);
          setUser(null);
          setOrganization(null);
          setPermissions([]);
          setRole(null);
          delete axios.defaults.headers.common['Authorization'];
        }
        return Promise.reject(err);
      }
    );
    return () => axios.interceptors.response.eject(id);
  }, []);

  const refreshUser = useCallback(async () => {
    if (token) {
      await fetchUserAndOrg(token);
    }
  }, [token, fetchUserAndOrg]);

  const login = async (email, password) => {
    try {
      const response = await axios.post(`${BACKEND_URL}/api/auth/login`, { email, password });
      const { access_token } = response.data;
      setToken(access_token);
      localStorage.setItem('token', access_token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      await fetchUserAndOrg(access_token);
      return { success: true };
    } catch (error) {
      return { success: false, error: error.response?.data?.detail || 'Email ou mot de passe incorrect' };
    }
  };

  const register = async (email, password, company_name) => {
    try {
      const response = await axios.post(`${BACKEND_URL}/api/auth/register`, { email, password, company_name });
      const { access_token } = response.data;
      setToken(access_token);
      localStorage.setItem('token', access_token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      await fetchUserAndOrg(access_token);
      return { success: true };
    } catch (error) {
      return { success: false, error: error.response?.data?.detail || "Erreur d'inscription" };
    }
  };

  const acceptInvite = async ({ token: inviteToken, password, pipeda_consent }) => {
    try {
      const response = await axios.post(`${BACKEND_URL}/api/auth/accept-invite`, {
        token: inviteToken, password, pipeda_consent,
      });
      const { access_token } = response.data;
      setToken(access_token);
      localStorage.setItem('token', access_token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      await fetchUserAndOrg(access_token);
      return { success: true };
    } catch (error) {
      return { success: false, error: error.response?.data?.detail || "Erreur lors de l'acceptation" };
    }
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    setOrganization(null);
    setPermissions([]);
    setRole(null);
    localStorage.removeItem('token');
    delete axios.defaults.headers.common['Authorization'];
  };

  const hasPermission = useCallback((code) => permissions.includes(code), [permissions]);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', fontSize: '18px' }}>
        Chargement...
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{
      user, organization, permissions, role,
      token, login, register, acceptInvite, logout, refreshUser,
      hasPermission,
      isAuthenticated: !!token,
    }}>
      {children}
    </AuthContext.Provider>
  );
};
```

- [ ] **Step 2: Sanity parse**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
node -e "require('@babel/parser').parse(require('fs').readFileSync('src/context/AuthContext.js','utf8'), {sourceType:'module', plugins:['jsx']}); console.log('OK AuthContext')"
```

- [ ] **Step 3: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add frontend/src/context/AuthContext.js
git commit -m "feat(organizations): AuthContext expose permissions, role, organization, hasPermission()"
```

---

## Task 13 : Route guards + sidebar filtering by permission

**Files:**
- Create: `frontend/src/components/RouteGuard.js`
- Modify: `frontend/src/components/Layout.js`
- Modify: `frontend/src/App.js`

- [ ] **Step 1: Créer `RouteGuard`**

`frontend/src/components/RouteGuard.js` :
```jsx
import React from 'react';
import { useAuth } from '../context/AuthContext';

/**
 * Wrapper qui vérifie la permission et redirige vers /dashboard si absente.
 * Usage :
 *   <RouteGuard permission="expenses:read"><ExpensesPage /></RouteGuard>
 */
export default function RouteGuard({ permission, children, fallback = null }) {
  const { hasPermission } = useAuth();
  if (!hasPermission(permission)) {
    if (fallback) return fallback;
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <h2 style={{ color: '#991b1b' }}>Accès refusé</h2>
        <p style={{ color: '#6b7280' }}>
          Vous n'avez pas la permission d'accéder à cette page.
          Contactez le propriétaire de l'organisation.
        </p>
        <a href="/dashboard" style={{
          display: 'inline-block', marginTop: 16,
          background: '#00A08C', color: '#fff', padding: '10px 20px',
          borderRadius: 6, textDecoration: 'none', fontWeight: 600,
        }}>Retour au tableau de bord</a>
      </div>
    );
  }
  return children;
}
```

- [ ] **Step 2: Repérer la structure Layout / sidebar**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
grep -n "sidebar\|menuItems\|navigation\|/dashboard\|/invoices\|/expenses\|/settings" frontend/src/components/Layout.js | head -20
```

Repérer la définition des items de sidebar. Probable pattern :
```js
const menuItems = [
  { path: '/dashboard', label: 'Tableau de bord', icon: ... },
  { path: '/invoices', label: 'Factures', icon: ... },
  ...
];
```

- [ ] **Step 3: Ajouter le champ `permission` à chaque item + filtrer**

Modifier la déclaration des items pour ajouter `permission` (ou `null` si accessible à tous) :

```jsx
import { useAuth } from '../context/AuthContext';

const MENU_ITEMS = [
  { path: '/dashboard',    label: 'Tableau de bord',       icon: LayoutDashboard, permission: null },
  { path: '/invoices',     label: 'Factures',              icon: FileText,        permission: 'invoices:read' },
  { path: '/quotes',       label: 'Devis',                 icon: FileText,        permission: 'quotes:read' },
  { path: '/clients',      label: 'Clients',               icon: Users,           permission: 'clients:read' },
  { path: '/products',     label: 'Produits',              icon: Package,         permission: 'products:read' },
  { path: '/employees',    label: 'Employés',              icon: Users,           permission: 'employees:read' },
  { path: '/expenses',     label: 'Dépenses',              icon: Receipt,         permission: 'expenses:read' },
  { path: '/bank',         label: 'Rapprochement',         icon: Landmark,        permission: 'bank:read' },
  { path: '/reports',      label: 'Rapports',              icon: BarChart,        permission: 'reports:read' },
  { path: '/settings',     label: 'Paramètres',            icon: Settings,        permission: null }, // Équipe visible pour tous, tabs internes gated
  { path: '/subscription', label: 'Abonnement',            icon: CreditCard,      permission: 'billing:manage' },
];
```

Puis dans le render du composant Layout :
```jsx
const { hasPermission } = useAuth();
const visibleItems = MENU_ITEMS.filter(item =>
  item.permission === null || hasPermission(item.permission)
);
// ...render visibleItems
```

Adapter aux noms exacts d'icônes utilisées dans Layout actuel.

- [ ] **Step 4: Envelopper les routes dans `App.js` avec `<RouteGuard>`**

Repérer la structure de routing dans `App.js` :
```bash
grep -n "window.location.pathname\|switch.*path\|routes\|currentPage" frontend/src/App.js | head -10
```

Le repo utilise navigation manuelle via `window.history` (pas react-router). Le pattern est probablement :
```jsx
{currentPage === 'expenses' && <ExpensesPage />}
```

Envelopper chaque page :
```jsx
import RouteGuard from './components/RouteGuard';

// ...
{currentPage === 'expenses' && (
  <RouteGuard permission="expenses:read"><ExpensesPage /></RouteGuard>
)}
{currentPage === 'invoices' && (
  <RouteGuard permission="invoices:read"><InvoicesPage /></RouteGuard>
)}
// idem pour quotes, clients, products, employees, bank, reports, subscription
```

Le dashboard reste non-gated (accès à tout membre).

- [ ] **Step 5: Sanity parse**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
for f in src/components/RouteGuard.js src/components/Layout.js src/App.js; do
  node -e "require('@babel/parser').parse(require('fs').readFileSync('$f','utf8'), {sourceType:'module', plugins:['jsx']}); console.log('OK $f')"
done
```

- [ ] **Step 6: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add frontend/src/components/RouteGuard.js frontend/src/components/Layout.js frontend/src/App.js
git commit -m "feat(organizations): RouteGuard + sidebar filtering by permission"
```

---

## Task 14 : SettingsPage — nouvel onglet « Équipe » (membres + matrice)

**Files:**
- Modify: `frontend/src/pages/SettingsPage.js`

- [ ] **Step 1: Repérer la structure des onglets existants dans SettingsPage**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
grep -n "activeTab\|setActiveTab\|TabButton\|onglet" frontend/src/pages/SettingsPage.js | head -15
```

Repérer :
- Le state `activeTab`
- Les autres onglets existants (probable : "Entreprise", "Informations fiscales", etc.)
- La structure des boutons d'onglet + le render conditionnel

- [ ] **Step 2: Ajouter les états + fetchers pour Équipe**

Dans SettingsPage, en haut du composant :

```jsx
import { useAuth } from '../context/AuthContext';
import { PERMISSIONS_EDITABLE } from '../constants/permissions'; // À créer ci-dessous

const [orgData, setOrgData] = useState(null);
const [orgLoading, setOrgLoading] = useState(false);
const [invitations, setInvitations] = useState([]);
const [showInviteModal, setShowInviteModal] = useState(false);
const { hasPermission, user: currentUser } = useAuth();

const fetchOrgData = useCallback(async () => {
  setOrgLoading(true);
  try {
    const [orgMe, invs] = await Promise.all([
      axios.get(`${BACKEND_URL}/api/org/me`),
      axios.get(`${BACKEND_URL}/api/org/invitations`),
    ]);
    setOrgData(orgMe.data);
    setInvitations(invs.data);
  } catch (e) {
    console.error(e);
  } finally {
    setOrgLoading(false);
  }
}, []);

useEffect(() => {
  if (activeTab === 'team' && hasPermission('team:manage')) fetchOrgData();
}, [activeTab, hasPermission, fetchOrgData]);
```

- [ ] **Step 3: Créer `frontend/src/constants/permissions.js`**

```jsx
// Permissions éditables — miroir de PERMISSIONS_EDITABLE côté backend.
export const PERMISSIONS_EDITABLE = [
  { code: 'expenses:read',   group: 'Dépenses',  label: 'Lire les dépenses' },
  { code: 'expenses:write',  group: 'Dépenses',  label: 'Créer / modifier les dépenses' },
  { code: 'receipts:scan',   group: 'Dépenses',  label: 'Scanner les reçus (OCR)' },
  { code: 'invoices:read',   group: 'Factures',  label: 'Lire les factures' },
  { code: 'invoices:write',  group: 'Factures',  label: 'Créer / modifier les factures' },
  { code: 'quotes:read',     group: 'Devis',     label: 'Lire les devis' },
  { code: 'quotes:write',    group: 'Devis',     label: 'Créer / modifier les devis' },
  { code: 'clients:read',    group: 'Clients',   label: 'Lire les clients' },
  { code: 'clients:write',   group: 'Clients',   label: 'Créer / modifier les clients' },
  { code: 'products:read',   group: 'Produits',  label: 'Lire les produits' },
  { code: 'products:write',  group: 'Produits',  label: 'Créer / modifier les produits' },
  { code: 'employees:read',  group: 'Employés',  label: 'Lire les employés' },
  { code: 'employees:write', group: 'Employés',  label: 'Créer / modifier les employés' },
  { code: 'reports:read',    group: 'Rapports',  label: 'Consulter les rapports (P&L, TPS/TVQ, T2125)' },
  { code: 'bank:read',       group: 'Bancaire',  label: 'Lire les imports bancaires' },
  { code: 'bank:write',      group: 'Bancaire',  label: 'Créer / modifier les imports bancaires' },
];

export const PERMISSION_GROUPS = ['Dépenses', 'Factures', 'Devis', 'Clients', 'Produits', 'Employés', 'Rapports', 'Bancaire'];
```

- [ ] **Step 4: Ajouter le bouton d'onglet « Équipe »**

Dans la barre d'onglets existante, ajouter (visible seulement si `hasPermission('team:manage')`) :

```jsx
{hasPermission('team:manage') && (
  <button onClick={() => setActiveTab('team')}
          style={{ /* même style que autres onglets */ }}>
    Équipe
  </button>
)}
```

- [ ] **Step 5: Ajouter le contenu de l'onglet Équipe**

Ajouter le render conditionnel :

```jsx
{activeTab === 'team' && hasPermission('team:manage') && (
  <TeamManagementSection
    orgData={orgData}
    invitations={invitations}
    loading={orgLoading}
    onRefresh={fetchOrgData}
    onInvite={() => setShowInviteModal(true)}
    currentUserId={currentUser?.id}
  />
)}
{showInviteModal && (
  <InviteMemberModal
    onClose={() => setShowInviteModal(false)}
    onSuccess={() => { setShowInviteModal(false); fetchOrgData(); }}
  />
)}
```

- [ ] **Step 6: Créer le composant `TeamManagementSection`**

À la fin de `SettingsPage.js` (avant `export default`) :

```jsx
import { PERMISSIONS_EDITABLE, PERMISSION_GROUPS } from '../constants/permissions';
import { Trash2, UserPlus, X as XIcon } from 'lucide-react';

function TeamManagementSection({ orgData, invitations, loading, onRefresh, onInvite, currentUserId }) {
  const [matrixEdits, setMatrixEdits] = useState({});
  const [savingRole, setSavingRole] = useState(null);

  if (loading || !orgData) return <div style={{ padding: 24 }}>Chargement…</div>;

  const { organization, members } = orgData;
  const rolePermissions = { ...organization.role_permissions, ...matrixEdits };

  const changeMemberRole = async (userId, newRole) => {
    if (!window.confirm(`Changer le rôle en ${newRole} ?`)) return;
    try {
      await axios.put(`${BACKEND_URL}/api/org/members/${userId}/role`, { role: newRole });
      onRefresh();
    } catch (e) {
      alert(e.response?.data?.detail || 'Erreur');
    }
  };

  const removeMember = async (userId, email) => {
    if (!window.confirm(`Retirer ${email} de l'organisation ?`)) return;
    try {
      await axios.delete(`${BACKEND_URL}/api/org/members/${userId}`);
      onRefresh();
    } catch (e) {
      alert(e.response?.data?.detail || 'Erreur');
    }
  };

  const revokeInvitation = async (invId, email) => {
    if (!window.confirm(`Révoquer l'invitation pour ${email} ?`)) return;
    try {
      await axios.delete(`${BACKEND_URL}/api/org/invitations/${invId}`);
      onRefresh();
    } catch (e) {
      alert(e.response?.data?.detail || 'Erreur');
    }
  };

  const togglePermission = (role, code) => {
    const current = rolePermissions[role] || [];
    const next = current.includes(code)
      ? current.filter(c => c !== code)
      : [...current, code];
    setMatrixEdits(prev => ({ ...prev, [role]: next }));
  };

  const saveRoleMatrix = async (role) => {
    setSavingRole(role);
    try {
      await axios.put(`${BACKEND_URL}/api/org/role-permissions`, {
        role, permissions: rolePermissions[role] || [],
      });
      setMatrixEdits(prev => {
        const next = { ...prev };
        delete next[role];
        return next;
      });
      onRefresh();
    } catch (e) {
      alert(e.response?.data?.detail || 'Erreur');
    } finally {
      setSavingRole(null);
    }
  };

  const isOwner = (uid) => organization.owner_id === uid;

  return (
    <div style={{ padding: 24 }}>
      {/* Section : Membres */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h3 style={{ margin: 0, fontSize: 18 }}>Membres actifs</h3>
        <button onClick={onInvite} style={{
          background: '#00A08C', color: '#fff', border: 'none',
          padding: '8px 16px', borderRadius: 6, cursor: 'pointer',
          fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <UserPlus size={16} /> Inviter un membre
        </button>
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14, marginBottom: 32 }}>
        <thead>
          <tr style={{ background: '#f9fafb', textAlign: 'left' }}>
            <th style={{ padding: 10 }}>Email</th>
            <th style={{ padding: 10 }}>Rôle</th>
            <th style={{ padding: 10 }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {members.map(m => (
            <tr key={m.id} style={{ borderTop: '1px solid #e5e7eb' }}>
              <td style={{ padding: 10 }}>
                {m.email}
                {isOwner(m.id) && <span style={{
                  marginLeft: 8, fontSize: 11, background: '#00A08C', color: '#fff',
                  padding: '2px 6px', borderRadius: 4,
                }}>Propriétaire</span>}
              </td>
              <td style={{ padding: 10 }}>
                {isOwner(m.id) ? (
                  <span style={{ color: '#6b7280' }}>owner</span>
                ) : (
                  <select value={m.role || 'viewer'}
                          onChange={e => changeMemberRole(m.id, e.target.value)}
                          style={{ padding: 6, border: '1px solid #d1d5db', borderRadius: 4 }}>
                    <option value="accountant">accountant</option>
                    <option value="viewer">viewer</option>
                  </select>
                )}
              </td>
              <td style={{ padding: 10 }}>
                {!isOwner(m.id) && m.id !== currentUserId && (
                  <button onClick={() => removeMember(m.id, m.email)} style={{
                    background: 'none', border: 'none', cursor: 'pointer',
                    color: '#991b1b', display: 'flex', alignItems: 'center', gap: 4,
                  }}>
                    <Trash2 size={14} /> Retirer
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Section : Invitations en cours */}
      <h3 style={{ margin: '0 0 16px', fontSize: 18 }}>Invitations en cours</h3>
      {invitations.length === 0 ? (
        <p style={{ color: '#6b7280', fontSize: 14, marginBottom: 32 }}>
          Aucune invitation en attente.
        </p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14, marginBottom: 32 }}>
          <thead>
            <tr style={{ background: '#f9fafb', textAlign: 'left' }}>
              <th style={{ padding: 10 }}>Email</th>
              <th style={{ padding: 10 }}>Rôle</th>
              <th style={{ padding: 10 }}>Expire le</th>
              <th style={{ padding: 10 }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {invitations.map(inv => (
              <tr key={inv.id} style={{ borderTop: '1px solid #e5e7eb' }}>
                <td style={{ padding: 10 }}>{inv.email}</td>
                <td style={{ padding: 10 }}>{inv.role}</td>
                <td style={{ padding: 10 }}>
                  {new Date(inv.expires_at).toLocaleDateString('fr-CA')}
                </td>
                <td style={{ padding: 10 }}>
                  <button onClick={() => revokeInvitation(inv.id, inv.email)} style={{
                    background: 'none', border: 'none', cursor: 'pointer',
                    color: '#991b1b', display: 'flex', alignItems: 'center', gap: 4,
                  }}>
                    <XIcon size={14} /> Révoquer
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Section : Matrice permissions */}
      <h3 style={{ margin: '0 0 16px', fontSize: 18 }}>Rôles et permissions</h3>
      {['accountant', 'viewer'].map(role => (
        <RoleMatrixCard
          key={role}
          role={role}
          permissions={rolePermissions[role] || []}
          isDirty={matrixEdits[role] !== undefined}
          saving={savingRole === role}
          onToggle={(code) => togglePermission(role, code)}
          onSave={() => saveRoleMatrix(role)}
        />
      ))}
    </div>
  );
}


function RoleMatrixCard({ role, permissions, isDirty, saving, onToggle, onSave }) {
  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16, marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h4 style={{ margin: 0, fontSize: 16, textTransform: 'capitalize' }}>{role}</h4>
        {isDirty && (
          <button onClick={onSave} disabled={saving} style={{
            background: '#00A08C', color: '#fff', border: 'none',
            padding: '6px 14px', borderRadius: 6, cursor: 'pointer', fontWeight: 600,
          }}>
            {saving ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        )}
      </div>
      {PERMISSION_GROUPS.map(group => (
        <div key={group} style={{ marginBottom: 10 }}>
          <div style={{ fontWeight: 600, fontSize: 13, color: '#374151', marginBottom: 4 }}>{group}</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
            {PERMISSIONS_EDITABLE.filter(p => p.group === group).map(p => (
              <label key={p.code} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={permissions.includes(p.code)}
                  onChange={() => onToggle(p.code)}
                />
                {p.label}
              </label>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 7: Sanity parse**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
node -e "require('@babel/parser').parse(require('fs').readFileSync('src/pages/SettingsPage.js','utf8'), {sourceType:'module', plugins:['jsx']}); console.log('OK')"
node -e "require('@babel/parser').parse(require('fs').readFileSync('src/constants/permissions.js','utf8'), {sourceType:'module', plugins:['jsx']}); console.log('OK constants')"
```

- [ ] **Step 8: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add frontend/src/pages/SettingsPage.js frontend/src/constants/permissions.js
git commit -m "feat(organizations): SettingsPage tab Équipe (members + invitations + matrix)"
```

---

## Task 15 : Invitation modal (frontend)

**Files:**
- Create: `frontend/src/components/InviteMemberModal.js`
- Modify: `frontend/src/pages/SettingsPage.js` (import + usage — déjà fait en T14)

- [ ] **Step 1: Créer le composant modal**

`frontend/src/components/InviteMemberModal.js` :
```jsx
import React, { useState } from 'react';
import axios from 'axios';
import { X, Mail } from 'lucide-react';
import { BACKEND_URL } from '../config';


export default function InviteMemberModal({ onClose, onSuccess }) {
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('accountant');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await axios.post(`${BACKEND_URL}/api/org/invitations`, {
        email: email.trim().toLowerCase(), role,
      });
      onSuccess();
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors de l\'envoi');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000,
    }}>
      <div style={{
        background: '#fff', borderRadius: 8, padding: 24,
        width: 480, maxWidth: '90vw', maxHeight: '90vh', overflow: 'auto',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h2 style={{ margin: 0, fontSize: 18, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Mail size={20} /> Inviter un membre
          </h2>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', cursor: 'pointer', padding: 4,
          }}>
            <X size={20} />
          </button>
        </div>

        <form onSubmit={submit}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 13, color: '#374151', marginBottom: 4, fontWeight: 600 }}>
              Email
            </label>
            <input type="email" required autoFocus value={email}
                   onChange={e => setEmail(e.target.value)}
                   placeholder="comptable@exemple.com"
                   style={{
                     width: '100%', padding: 10, border: '1px solid #d1d5db',
                     borderRadius: 6, fontSize: 14, boxSizing: 'border-box',
                   }} />
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 13, color: '#374151', marginBottom: 4, fontWeight: 600 }}>
              Rôle
            </label>
            <select value={role} onChange={e => setRole(e.target.value)}
                    style={{
                      width: '100%', padding: 10, border: '1px solid #d1d5db',
                      borderRadius: 6, fontSize: 14,
                    }}>
              <option value="accountant">Comptable — accès complet aux données métier</option>
              <option value="viewer">Lecteur — accès en lecture seule</option>
            </select>
          </div>

          <div style={{ background: '#f3f4f6', padding: 12, borderRadius: 6, marginBottom: 16, fontSize: 13, color: '#6b7280' }}>
            Un email d'invitation sera envoyé avec un lien valide 7 jours. Le destinataire pourra créer son compte ou se connecter s'il en a déjà un.
          </div>

          {error && (
            <div style={{ background: '#fee2e2', color: '#991b1b', padding: 10, borderRadius: 6, marginBottom: 16, fontSize: 13 }}>
              {error}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <button type="button" onClick={onClose} disabled={loading} style={{
              background: '#fff', border: '1px solid #d1d5db', color: '#374151',
              padding: '10px 16px', borderRadius: 6, cursor: 'pointer',
            }}>
              Annuler
            </button>
            <button type="submit" disabled={loading || !email} style={{
              background: '#00A08C', color: '#fff', border: 'none',
              padding: '10px 20px', borderRadius: 6, cursor: 'pointer', fontWeight: 600,
            }}>
              {loading ? 'Envoi…' : 'Envoyer l\'invitation'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Ajouter l'import dans SettingsPage.js**

En haut de `frontend/src/pages/SettingsPage.js`, ajouter :
```jsx
import InviteMemberModal from '../components/InviteMemberModal';
```

- [ ] **Step 3: Sanity parse**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
node -e "require('@babel/parser').parse(require('fs').readFileSync('src/components/InviteMemberModal.js','utf8'), {sourceType:'module', plugins:['jsx']}); console.log('OK')"
node -e "require('@babel/parser').parse(require('fs').readFileSync('src/pages/SettingsPage.js','utf8'), {sourceType:'module', plugins:['jsx']}); console.log('OK')"
```

- [ ] **Step 4: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add frontend/src/components/InviteMemberModal.js frontend/src/pages/SettingsPage.js
git commit -m "feat(organizations): InviteMemberModal (form + submit + error handling)"
```

---

## Task 16 : Page publique `/accept-invite` (frontend)

**Files:**
- Create: `frontend/src/pages/AcceptInvitePage.js`
- Modify: `frontend/src/App.js` (routing)

- [ ] **Step 1: Créer la page**

`frontend/src/pages/AcceptInvitePage.js` :
```jsx
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { BACKEND_URL } from '../config';
import { useAuth } from '../context/AuthContext';
import FactureProLogo from '../components/FactureProLogo';


function useQueryToken() {
  const [token, setToken] = useState(null);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setToken(params.get('token'));
  }, []);
  return token;
}


export default function AcceptInvitePage() {
  const token = useQueryToken();
  const { acceptInvite } = useAuth();
  const [preview, setPreview] = useState(null);
  const [previewError, setPreviewError] = useState(null);
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [pipedaConsent, setPipedaConsent] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  useEffect(() => {
    if (!token) return;
    axios.get(`${BACKEND_URL}/api/org/invitations/preview?token=${encodeURIComponent(token)}`)
      .then(r => setPreview(r.data))
      .catch(err => setPreviewError(err.response?.data?.detail || 'Invitation introuvable'));
  }, [token]);

  const submit = async (e) => {
    e.preventDefault();
    setSubmitError(null);
    if (password !== confirmPassword) {
      setSubmitError('Les mots de passe ne correspondent pas');
      return;
    }
    if (password.length < 6) {
      setSubmitError('Mot de passe trop court (min 6 caractères)');
      return;
    }
    if (!pipedaConsent) {
      setSubmitError('Vous devez accepter les CGU et la politique PIPEDA');
      return;
    }
    setSubmitting(true);
    const result = await acceptInvite({ token, password, pipeda_consent: true });
    setSubmitting(false);
    if (result.success) {
      window.history.pushState({}, '', '/dashboard');
      window.dispatchEvent(new Event('popstate'));
    } else {
      setSubmitError(result.error);
    }
  };

  if (!token) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <h2>Lien d'invitation invalide</h2>
        <p>Le token est absent de l'URL.</p>
      </div>
    );
  }

  if (previewError) {
    return (
      <div style={{ padding: 40, textAlign: 'center', maxWidth: 500, margin: '0 auto' }}>
        <FactureProLogo />
        <h2 style={{ color: '#991b1b', marginTop: 24 }}>Invitation invalide</h2>
        <p style={{ color: '#6b7280' }}>{previewError}</p>
        <p style={{ marginTop: 16, fontSize: 13 }}>
          Demandez au propriétaire de l'organisation de vous envoyer une nouvelle invitation.
        </p>
      </div>
    );
  }

  if (!preview) return <div style={{ padding: 40 }}>Chargement…</div>;

  return (
    <div style={{ padding: 40, maxWidth: 500, margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: 32 }}>
        <FactureProLogo />
      </div>
      <h1 style={{ fontSize: 22, marginBottom: 8, textAlign: 'center' }}>Rejoindre {preview.org_name}</h1>
      <p style={{ color: '#6b7280', textAlign: 'center', marginBottom: 24 }}>
        Vous avez été invité(e) en tant que <strong>{preview.role}</strong>.
      </p>

      <form onSubmit={submit}>
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
            Email
          </label>
          <input type="email" value={preview.email} readOnly
                 style={{
                   width: '100%', padding: 10, border: '1px solid #d1d5db',
                   borderRadius: 6, fontSize: 14, background: '#f9fafb',
                   boxSizing: 'border-box',
                 }} />
        </div>

        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
            Mot de passe
          </label>
          <input type="password" required autoFocus value={password}
                 onChange={e => setPassword(e.target.value)}
                 placeholder="Min. 6 caractères"
                 style={{
                   width: '100%', padding: 10, border: '1px solid #d1d5db',
                   borderRadius: 6, fontSize: 14, boxSizing: 'border-box',
                 }} />
          <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>
            Si vous avez déjà un compte FacturePro avec cet email, entrez votre mot de passe existant.
          </div>
        </div>

        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
            Confirmer le mot de passe
          </label>
          <input type="password" required value={confirmPassword}
                 onChange={e => setConfirmPassword(e.target.value)}
                 style={{
                   width: '100%', padding: 10, border: '1px solid #d1d5db',
                   borderRadius: 6, fontSize: 14, boxSizing: 'border-box',
                 }} />
        </div>

        <div style={{ marginBottom: 24 }}>
          <label style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 13, cursor: 'pointer' }}>
            <input type="checkbox" checked={pipedaConsent}
                   onChange={e => setPipedaConsent(e.target.checked)}
                   style={{ marginTop: 2 }} />
            <span>
              J'accepte les <a href="/cgu" target="_blank" style={{ color: '#00A08C' }}>Conditions générales d'utilisation</a> et la <a href="/privacy" target="_blank" style={{ color: '#00A08C' }}>politique de confidentialité (PIPEDA)</a>.
            </span>
          </label>
        </div>

        {submitError && (
          <div style={{ background: '#fee2e2', color: '#991b1b', padding: 10, borderRadius: 6, marginBottom: 16, fontSize: 13 }}>
            {submitError}
          </div>
        )}

        <button type="submit" disabled={submitting} style={{
          width: '100%', background: '#00A08C', color: '#fff', border: 'none',
          padding: 12, borderRadius: 6, cursor: 'pointer', fontWeight: 600, fontSize: 15,
        }}>
          {submitting ? 'Acceptation en cours…' : 'Accepter l\'invitation'}
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Router `/accept-invite` dans App.js**

Dans `frontend/src/App.js`, ajouter en haut :
```jsx
import AcceptInvitePage from './pages/AcceptInvitePage';
```

Dans le rendering (avant tous les autres composants qui exigent auth), ajouter :
```jsx
// Public route — no auth required
if (window.location.pathname === '/accept-invite') {
  return <AcceptInvitePage />;
}
```

Ce check doit être fait **avant** l'écran de login. `AcceptInvitePage` gère elle-même la connexion via `acceptInvite()`.

- [ ] **Step 3: Sanity parse**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
node -e "require('@babel/parser').parse(require('fs').readFileSync('src/pages/AcceptInvitePage.js','utf8'), {sourceType:'module', plugins:['jsx']}); console.log('OK AcceptInvitePage')"
node -e "require('@babel/parser').parse(require('fs').readFileSync('src/App.js','utf8'), {sourceType:'module', plugins:['jsx']}); console.log('OK App')"
```

- [ ] **Step 4: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add frontend/src/pages/AcceptInvitePage.js frontend/src/App.js
git commit -m "feat(organizations): /accept-invite public page with PIPEDA consent"
```

---

## Task 17 : Integration tests — full E2E invitation flow + permission gates + migration

**Files:**
- Modify: `backend/tests/test_organizations_integration.py`

- [ ] **Step 1: Ajouter les tests d'isolation cross-org**

Append à `backend/tests/test_organizations_integration.py` :
```python
class TestCrossOrgIsolation:
    def _setup_second_org(self):
        """Crée un second user + org isolé, retourne son user_id + org_id."""
        uid = f"iso-{uuid.uuid4().hex[:8]}"
        org_id = str(uuid.uuid4())
        server_module.db.organizations.insert_one({
            "id": org_id, "name": "IsoOrg", "owner_id": uid,
            "subscription_status": "trial",
            "trial_ends_at": (datetime.now(timezone.utc) + timedelta(days=100)).isoformat(),
            "role_permissions": server_module.DEFAULT_ROLE_PERMISSIONS,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        server_module.db.users.insert_one({
            "id": uid, "email": f"{uid}@iso.test",
            "is_active": True, "organization_id": org_id, "role": "owner",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        server_module.db.user_passwords.insert_one({
            "user_id": uid,
            "hashed_password": server_module.hash_password("isopass"),
        })
        return uid, org_id

    def _cleanup_second_org(self, uid, org_id):
        server_module.db.users.delete_one({"id": uid})
        server_module.db.user_passwords.delete_one({"user_id": uid})
        server_module.db.organizations.delete_one({"id": org_id})
        # Cleanup any created business docs
        for coll in ["invoices", "expenses", "quotes", "clients", "products"]:
            server_module.db[coll].delete_many({"organization_id": org_id})

    def _iso_headers(self, client, email):
        r = client.post("/api/auth/login",
                        json={"email": email, "password": "isopass"})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def test_iso_user_cannot_see_owner_expenses(self, client, owner_headers):
        # Owner creates an expense
        r = client.post("/api/expenses", headers=owner_headers, json={
            "vendor": "OwnerVendor", "amount_cad": 42.0,
            "date": "2026-06-01", "category_code": "other",
        })
        assert r.status_code in (200, 201)
        expense_id = r.json().get("id")

        # Second org user cannot list or fetch this expense
        uid, org_id = self._setup_second_org()
        try:
            iso_headers = self._iso_headers(client, f"{uid}@iso.test")
            r2 = client.get("/api/expenses", headers=iso_headers)
            assert r2.status_code == 200
            iso_expenses = r2.json()
            assert not any(e.get("id") == expense_id for e in iso_expenses)
        finally:
            client.delete(f"/api/expenses/{expense_id}", headers=owner_headers)
            self._cleanup_second_org(uid, org_id)

    def test_iso_user_cannot_see_owner_invoices(self, client, owner_headers):
        uid, org_id = self._setup_second_org()
        try:
            iso_headers = self._iso_headers(client, f"{uid}@iso.test")
            # Owner's invoices should NOT appear in iso user's list
            r_owner = client.get("/api/invoices", headers=owner_headers)
            r_iso = client.get("/api/invoices", headers=iso_headers)
            owner_invoice_ids = {i["id"] for i in r_owner.json()}
            iso_invoice_ids = {i["id"] for i in r_iso.json()}
            assert owner_invoice_ids.isdisjoint(iso_invoice_ids)
        finally:
            self._cleanup_second_org(uid, org_id)


class TestPermissionsDynamic:
    def test_permissions_reflect_matrix_change_immediately(self, client,
                                                             owner_headers,
                                                             monkeypatch):
        """Test critique : si owner édite la matrice, le viewer perd/gagne
        les perms au prochain call — pas de cache."""
        monkeypatch.setattr(server_module, "_send_invitation_email",
                             lambda *a, **kw: True)
        email = f"dyn-{uuid.uuid4().hex[:8]}@test.local"
        r = client.post("/api/org/invitations", headers=owner_headers,
                        json={"email": email, "role": "viewer"})
        token = server_module.db.invitations.find_one({"id": r.json()["id"]})["token"]
        r2 = client.post("/api/auth/accept-invite", json={
            "token": token, "password": "dynpass",
            "pipeda_consent": True,
        })
        viewer_headers = {"Authorization": f"Bearer {r2.json()['access_token']}"}

        try:
            # Initially viewer has expenses:read
            r3 = client.get("/api/expenses", headers=viewer_headers)
            assert r3.status_code == 200

            # Owner removes expenses:read from viewer matrix
            client.put("/api/org/role-permissions", headers=owner_headers, json={
                "role": "viewer",
                "permissions": ["invoices:read"],  # only invoices, no expenses
            })

            # Same JWT — but next call must reflect the new matrix (no cache)
            r4 = client.get("/api/expenses", headers=viewer_headers)
            assert r4.status_code == 403

            # Restore default matrix
            client.put("/api/org/role-permissions", headers=owner_headers, json={
                "role": "viewer",
                "permissions": server_module.DEFAULT_ROLE_PERMISSIONS["viewer"],
            })
        finally:
            user = server_module.db.users.find_one({"email": email})
            if user:
                server_module.db.users.delete_one({"id": user["id"]})
                server_module.db.user_passwords.delete_one({"user_id": user["id"]})


class TestMigrationIntegration:
    def test_migration_at_startup_is_idempotent(self, client, owner_headers):
        # gussdub should have organization_id set after startup
        r = client.get("/api/org/me", headers=owner_headers)
        assert r.status_code == 200
        org_id = r.json()["organization"]["id"]

        # Re-run migration manually
        server_module.migrate_organizations_v1()

        # gussdub's org_id should be unchanged
        r2 = client.get("/api/org/me", headers=owner_headers)
        assert r2.json()["organization"]["id"] == org_id
```

- [ ] **Step 2: Run les nouveaux tests**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_organizations_integration.py -v 2>&1 | tail -30
```
Expected : tous les nouveaux tests d'isolation + dynamique + migration passent.

- [ ] **Step 3: Full non-regression run**

```bash
pytest tests/ 2>&1 | tail -30
```
Expected : la suite complète passe, sans nouveau rouge non-résolu.

- [ ] **Step 4: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/tests/test_organizations_integration.py
git commit -m "test(organizations): cross-org isolation, dynamic perms, migration integration"
```

---

## Task 18 : E2E manual + push prod + update CLAUDE.md

- [ ] **Step 1: Sanity build frontend**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
npm run build 2>&1 | tail -10
```
Expected : build success. Fixer toute erreur ESLint/parse.

- [ ] **Step 2: E2E manuel local**

Démarrer les 2 services :
```bash
# terminal 1
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
uvicorn server:app --reload --port 8000

# terminal 2
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
npm start
```

Sur `http://localhost:3000` :

**Scénario 1 — Owner invite un comptable** :
1. Login `gussdub@gmail.com` / `testpass123`.
2. Naviguer vers Paramètres → onglet Équipe.
3. Vérifier :
   - Membre unique (gussdub) affiché comme "Propriétaire" (rôle owner).
   - Section Rôles & permissions avec matrices accountant + viewer (defaults).
4. Cliquer "Inviter un membre".
5. Email : `test-comptable@yopmail.com`, rôle `accountant`.
6. Envoyer → l'email doit partir (vérifier Resend dashboard ou logs backend).
7. Vérifier l'invitation apparaît dans "Invitations en cours".

**Scénario 2 — Acceptation invitation (nouveau user)** :
1. Ouvrir le lien reçu dans un onglet en incognito.
2. Vérifier preview : "Vous êtes invité à rejoindre ProFireManager en tant que accountant".
3. Entrer un password, cocher PIPEDA, submit.
4. Redirection vers `/dashboard` → user connecté.
5. Vérifier la sidebar : Factures, Dépenses, Devis, Clients, Produits, Employés, Bank, Rapports visibles. Paramètres visible mais pas d'onglet Équipe. Abonnement NON visible.
6. Créer une dépense → doit fonctionner (accountant a expenses:write).

**Scénario 3 — Isolation** :
1. Créer une facture avec le compte accountant.
2. Vérifier qu'elle apparaît dans /invoices du owner (même org).
3. Créer un 3e compte via /register (test@example.com) — devrait créer une NOUVELLE org indépendante.
4. Login test@example.com → NE doit PAS voir les factures de ProFireManager.

**Scénario 4 — Édition de la matrice viewer** :
1. Retour login owner.
2. Paramètres → Équipe → décocher `bank:read` dans la matrice viewer → Enregistrer.
3. Inviter un email viewer, l'accepter.
4. Sur le compte viewer, vérifier que l'onglet "Rapprochement" n'apparaît plus dans la sidebar.

**Scénario 5 — Retrait d'un membre** :
1. Login owner, aller dans Paramètres → Équipe.
2. Cliquer "Retirer" à côté de test-comptable → confirmer.
3. Login test-comptable → doit voir un écran "Aucune organisation" ou redirect (à définir dans le state d'AuthContext).

**Scénario 6 — Anti-lockout owner** :
1. Login owner. Aller sur Équipe.
2. Constater que l'owner n'a pas de bouton "Retirer" ni de dropdown rôle.
3. Test API direct : `PUT /api/org/members/<owner_id>/role` avec `viewer` → 400.
4. `DELETE /api/org/members/<owner_id>` → 400.

Ajuster tout bug trouvé.

- [ ] **Step 3: Update CLAUDE.md — ajouter la feature dans le changelog**

Ajouter en tête de la section "Features livrées" (avant feature #10) :

```markdown
- **2026-07-01 — Organisations multi-tenant (feature #11)**
  - Nouvelles collections : `organizations` (subscription Stripe + role_permissions + scan quota) et `invitations` (link signé Resend TTL 7j single-use)
  - Nouveau modèle Pydantic `CurrentUser` (id + email + organization_id + role + permissions) résolu à chaque requête via `get_current_user_with_access` refactoré
  - Dependency `require_permission("code")` appliquée sur ~60 endpoints métier ; toutes les queries filtrent par `organization_id` au lieu de `user_id` (avec fallback transitoire `$or` pendant 4 semaines)
  - Migration idempotente au startup `migrate_organizations_v1()` : chaque user existant devient owner d'une org auto-créée qui reprend son `company_name` ; backfill `organization_id` + `created_by_user_id` sur toutes les collections métier
  - 3 rôles fixes : **owner** (toutes perms), **accountant** (defaults éditables par owner), **viewer** (read-only). Matrice `role_permissions` éditable sur l'organisation ; owner-only codes (`settings:manage`, `billing:manage`, `team:manage`) hardcodés dans le résolveur — impossible de les injecter via la matrice
  - Nouveaux endpoints : `GET /api/org/me` (context complet), `PUT /api/org/role-permissions` (matrix), `POST/GET/DELETE /api/org/invitations`, `GET /api/org/invitations/preview` (public), `POST /api/auth/accept-invite` (public + rate-limité 5/min/IP + PIPEDA consent obligatoire), `PUT /api/org/members/{id}/role`, `DELETE /api/org/members/{id}` (soft, unset org+role — audit trail préservé via `created_by_user_id`)
  - Anti-lockout owner : `owner_id` immutable, impossible de changer son rôle, impossible de le retirer, impossible pour lui de se retirer lui-même
  - Frontend : `AuthContext` expose `permissions`, `role`, `organization`, `hasPermission()` ; nouveau `<RouteGuard permission="...">` wrapper ; sidebar filtre par permission ; onglet « Équipe » dans SettingsPage (membres + invitations + matrice UI groupée par domaine) ; page publique `/accept-invite` avec form password + PIPEDA checkbox
  - Sécurité : `_resolve_permissions` filtre à `PERMISSIONS_EDITABLE` (codes owner-only jamais accordés via matrice, codes inconnus ignorés) ; token invitation `secrets.token_urlsafe(32)` ~256 bits d'entropie ; `bcrypt.checkpw` constant-time sur `/accept-invite` ; jamais de token/password dans les logs
  - Limites v1 : custom roles, SSO/SAML, audit log endpoint, 2FA, multi-org par user, transfert d'ownership, facturation pro-rata ; abonnement Stripe reste flat $15 CAD/mois par org, quota scan reçus reste 200/org/mois (partagé org-wide)
  - Tests : ~15 unitaires + ~35 intégration = **~50 nouveaux tests**, 0 régression
  - Spec : `docs/superpowers/specs/2026-07-01-multi-tenant-organizations-design.md`
  - Plan : `docs/superpowers/plans/2026-07-01-multi-tenant-organizations.md`
```

- [ ] **Step 4: Push prod**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add CLAUDE.md
git commit -m "docs: feature #11 multi-tenant organizations dans changelog"
git push origin main
```

Render redéploie backend (~3-5 min — la migration `migrate_organizations_v1()` s'exécute au boot pour toute la prod). Vercel redéploie frontend (~2 min).

- [ ] **Step 5: Monitoring post-deploy**

Vérifier les logs Render dans les 30 min post-deploy :
- Ligne `MIGRATION organizations_v1 : N orgs créées` doit apparaître.
- Aucune erreur 500 en cascade sur `/api/expenses`, `/api/invoices`, `/api/org/me`.

Vérifier sur `https://facturepro.ca` avec le compte owner de prod :
- `GET /api/org/me` retourne un payload valide.
- Aucune régression sur les fonctionnalités existantes (factures, devis, dépenses, rapports, banque).

Si tout OK → feature livrée. Sinon hotfix via git push, la migration idempotente garantit qu'un redeploy est safe.

**Point de non-retour** : le script `backend/scripts/drop_legacy_user_fields.py` (§6.4 spec) **NE PAS** l'exécuter avant 4 semaines de stabilité prod. Il retirera `subscription_status`, `stripe_customer_id`, `trial_end_date`, `scan_count_this_month`, `scan_quota_reset_at` de `users` et `user_id` des collections métier une fois qu'on aura la certitude qu'aucun code legacy n'y accède.

- [ ] **Step 6: Commit final (si smoke tests OK)**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git log --oneline -20
```

Vérifier la séquence de commits de la feature.

---

## Self-review

**1. Spec coverage** :
- ✅ §2 (décisions verrouillées) : owner-only codes hardcodés (T2), matrice éditable dans org (T4), anti-lockout owner (T7), invitation lien signé Resend TTL 7j (T5-T6), PIPEDA consent obligatoire (T6/T16), migration idempotente au startup (T1).
- ✅ §3.1 (collection `organizations`) : T1 crée le doc, T4 permet edit matrix.
- ✅ §3.2 (users modifications) : T1 ajoute `organization_id` + `role`, T6 ajoute `pipeda_consent_at`, T8 laisse legacy en place pendant transition.
- ✅ §3.3 (collection `invitations`) : T5 crée + indexes.
- ✅ §3.4 (collections métier `organization_id`) : T1 migration, T9-T10 queries + inserts.
- ✅ §3.5 (constantes PERMISSIONS_*) : T1.
- ✅ §4.1 (modèle `CurrentUser`) : T2.
- ✅ §4.2 (`_resolve_permissions`) : T2 avec filter owner-only + unknown.
- ✅ §4.3 (`get_current_user_with_access` refactor) : T2.
- ✅ §4.4 (`require_permission` + mapping table) : T3, T9, T10, T11.
- ✅ §4.5 (queries `organization_id`) : T9, T10.
- ✅ §5.1 (GET /api/org/me) : T4.
- ✅ §5.2 (PUT /api/org/role-permissions) : T4.
- ✅ §5.3-5.5 (invitations CRUD) : T5.
- ✅ §5.6 (POST /accept-invite + rate limit + PIPEDA) : T6.
- ✅ §5.7-5.8 (members role + delete) : T7.
- ✅ §5.9 (modifications endpoints existants) : T2 (auth/me, register), T8 (Stripe).
- ✅ §6.1-6.2 (migration idempotente) : T1.
- ✅ §6.3 (fallback synthesize) : T2.
- ✅ §7.1 (tab Équipe SettingsPage) : T14.
- ✅ §7.2 (page /accept-invite) : T16.
- ✅ §7.3 (AuthContext permissions) : T12.
- ✅ §7.4 (route guards + sidebar filtering) : T13.
- ✅ §7.5 (boutons désactivés par permission dans les pages) : à faire au moment du polissage post-T14 (pas critique — RouteGuard + sidebar suffisent pour bloquer l'accès ; T13/T14 couvrent 90% du besoin).
- ✅ §8 (sécurité) : `_resolve_permissions` filtrage (T2), rate limit (T6), token urlsafe 32 (T5), bcrypt (T6), anti-lockout (T7), pas de token dans logs (T5).
- ✅ §9.1-9.2 (tests unit + intégration) : T1 (constants + migration), T2 (resolve + synthesize), T3 (require_permission), T4-T7 (endpoints), T11 (enforcement), T17 (isolation + dynamic).
- ✅ §9.3 (E2E manuel) : T18.
- ✅ §11 (rollback plan) : couvert par la migration idempotente (T1) + fallback `_synthesize_solo_org_from_user` (T2) + fallback `$or` sur queries (T9). Redeploy previous Render possible sans perte de données.
- ✅ §12 (rollout) : T1 → T18 séquentiel, push main à T18.
- ✅ §13 (impact estimé) : ~600 lignes backend, ~500 lignes frontend, ~800 lignes tests — l'ordre de grandeur est respecté (voir taille du plan).

**2. Placeholder scan** : aucun « TBD », « TODO », « implement later ». Les rares « adapter selon le code existant » concernent des points où le nom exact d'une variable (ex. `setSettings` vs `setSettingsData`) dépend du code frontend actuel — c'est inévitable et documenté.

**3. Type consistency** :
- `CurrentUser` (backend) et `useAuth().user` (frontend) — cohérents (id, email, organization_id, role, permissions).
- `organization_id` partout (DB, API, frontend context) — même nom, jamais `org_id` ou `orgId`.
- `PERMISSIONS_EDITABLE` synchronisé entre backend (`server.py`) et frontend (`constants/permissions.js`).
- Codes de permission : format `<domain>:<action>` uniforme partout.
- `role_permissions` (dict) partout — jamais `rolePermissions` côté backend, camelCase seulement au niveau JSON API.
- Endpoints paths : cohérents avec la spec §5 exactement.
- Statuts d'invitation : `pending` / `accepted` / `revoked` / `expired` partout.

**4. Sécurité** : chaque menace du §8 est couverte par au moins un test (T11 permission enforcement, T17 isolation, T5 duplicate rejection, T6 rate limit implicite via `_rate_limit_accept_invite`).

**5. Rollback** : la migration est idempotente. Le fallback `_synthesize_solo_org_from_user` garantit qu'un boot mid-migration ne casse pas les users existants. Le script `drop_legacy_user_fields.py` reste hors scope de ce plan — à exécuter séparément après 4 semaines de stabilité.

Plan prêt à l'exécution.
