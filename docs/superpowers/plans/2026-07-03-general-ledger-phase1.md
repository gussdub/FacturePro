# Grand Livre Phase 1 (MVP) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Fondation d'un grand livre en partie double : charte des comptes, écritures manuelles, apport, balance de vérification, bilan, assistant d'ouverture.

**Architecture:** Collections `chart_of_accounts` + `journal_entries` (lines[] Dr/Cr, équilibre forcé), org-scopées ; RBAC accounting:read/write ; PDF FR-CA ; migration comptes par défaut par org.

**Tech Stack:** FastAPI + pymongo + Pydantic ; ReportLab (PDF) ; React 18.

**Spec source:** [docs/superpowers/specs/2026-07-03-general-ledger-design.md](../specs/2026-07-03-general-ledger-design.md)

---

## File Structure

**Backend** (`backend/server.py` — nouvelle section « Grand livre (feature #12) ») :
- Constantes : `ACCOUNT_TYPES`, `ACCOUNT_NUMBER_RANGES`, `DEFAULT_BASE_ACCOUNTS`, `EXPENSE_ACCOUNT_NUMBERS`
- Helpers : `_normal_balance_for_type`, `_account_type_for_number`, `_build_default_accounts`, `_ensure_chart_seeded`, `_next_entry_number`, `_validate_entry_balance`, `_account_balance`, `_current_fiscal_year`, `migrate_general_ledger_v1`, `_ledger_pdf_money`
- Endpoints nouveaux (`/api/ledger/*`) : accounts CRUD, journal entries CRUD + post + reverse, opening-balance, owner-contribution, general-ledger, trial-balance, balance-sheet, + 2 PDF
- Modifications : `PERMISSIONS_EDITABLE` (+accounting), `DEFAULT_ROLE_PERMISSIONS` (viewer +read), `migrate_organizations_v1`/`migrate_general_ledger_v1` backfill perms, champs fiscaux sur `company_settings`, `PUT /api/settings/company`

**Tests** (`backend/tests/`) :
- `test_general_ledger.py` — unitaires (validation équilibre, solde, plan par défaut, normal_balance, fiscal year, trial balance, bilan)
- `test_general_ledger_integration.py` — intégration HTTP (seed lazy, CRUD, journal équilibre forcé, ouverture, apport, trial balance, bilan, RBAC, isolation cross-org, PDF)

**Frontend** (`frontend/src/`) :
- `context/AuthContext.js` / `components/Layout.js` — entrée sidebar « Grand livre » gatée `accounting:read` + RouteGuard
- `pages/LedgerPage.js` — page à onglets (Plan comptable, Journal, Assistant ouverture, Apport, Grand livre, Balance de vérification, Bilan)
- `App.js` — route `/ledger`

---

## Task 0 : Setup test stubs

**Files:**
- Read: `docs/superpowers/specs/2026-07-03-general-ledger-design.md`
- Create: `backend/tests/test_general_ledger.py`
- Create: `backend/tests/test_general_ledger_integration.py`

> **[COMPTA] — invariants comptables à couvrir par T1+ (note du reviewer, rien à vérifier en T0).**
> T0 ne contient que des stubs (imports + fixtures), donc aucune logique comptable. Les tâches suivantes DOIVENT garantir, et tester explicitement :
> 1. **Équilibre débit = crédit forcé par écriture** (`_validate_entry_balance`, T5 ; rejet 400 > 0,005 $) — cf. §5.1.
> 2. **Prise en compte de TOUS les `posted`** — la contre-passation ne casse rien : origine ET miroir restent `posted`, net = 0, jamais de statut `reversed` (`_account_balance`, T5/T6) — cf. §5.2/§5.3.
> 3. **Équation du bilan** : `total_assets == total_liabilities + total_equity` (`balanced`, T9) — cf. §7.2.
> 4. **Pas de double comptage du résultat net** : `net_income_current_year = revenus − dépenses` sur `[fy_start, as_of]`, dérivé une seule fois, jamais cumulé depuis toujours (T9) — cf. §7.2.
> 5. **Signe correct des soldes par type** : débiteur pour actif/charges, créditeur pour passif/capitaux/produits (`_normal_balance_for_type`, T1 ; balance de vérification T8) — cf. §3.1/§7.1.

- [ ] **Step 1: Lire la spec complète**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
sed -n '1,260p' docs/superpowers/specs/2026-07-03-general-ledger-design.md
```

Se concentrer sur : §2 (décisions verrouillées — ne pas dévier), §3 (modèle de données), §4 (plan par défaut), §5 (logique partie double), §6 (API REST — signatures + codes retour), §7 (formules bilan/balance), §8 (RBAC + migration).

- [ ] **Step 2: Créer le stub unitaire**

`backend/tests/test_general_ledger.py` :
```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uuid
import pytest
from datetime import datetime, timezone
```

- [ ] **Step 3: Créer le stub intégration**

`backend/tests/test_general_ledger_integration.py` :
```python
import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))

import uuid
import pytest
from datetime import datetime, timezone, timedelta
import server as server_module
from fastapi.testclient import TestClient


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

- [ ] **Step 4: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/tests/test_general_ledger.py backend/tests/test_general_ledger_integration.py
git commit -m "test(ledger): stubs for feature #12 general ledger"
```

---

## Task 1 : Constantes plan comptable + helpers de dérivation

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_general_ledger.py`

- [ ] **Step 1: Écrire les tests des constantes + helpers**

Append à `backend/tests/test_general_ledger.py` :
```python
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
```

- [ ] **Step 2: Verify failure**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
pytest tests/test_general_ledger.py -v 2>&1 | tail -15
```
Expected : ImportError sur `ACCOUNT_TYPES` (constantes absentes).

- [ ] **Step 3: Ajouter les constantes + helpers dans `server.py`**

Localiser la fin de la section RBAC / `migrate_organizations_v1` (autour de la ligne 1350, après `_ORG_SCOPED_COLLECTIONS`). AJOUTER une nouvelle section AVANT `def migrate_organizations_v1():` :

```python
# ─── Grand livre — comptabilité en partie double (feature #12) ───

ACCOUNT_TYPES = ["asset", "liability", "equity", "revenue", "expense"]

ACCOUNT_NUMBER_RANGES = {
    "asset":     (1000, 1999),
    "liability": (2000, 2999),
    "equity":    (3000, 3999),
    "revenue":   (4000, 4999),
    "expense":   (5000, 5999),
}

_NORMAL_BALANCE_BY_TYPE = {
    "asset": "debit",
    "liability": "credit",
    "equity": "credit",
    "revenue": "credit",
    "expense": "debit",
}


def _normal_balance_for_type(account_type: str) -> str:
    """Solde normal dérivé du type de compte (§3.1 spec)."""
    return _NORMAL_BALANCE_BY_TYPE.get(account_type, "debit")


def _account_type_for_number(account_number) -> str:
    """Déduit le type de compte à partir de la plage du numéro (§ décision #4).
    Retourne None si hors des plages canoniques 1000-5999."""
    try:
        n = int(str(account_number))
    except (TypeError, ValueError):
        return None
    for account_type, (lo, hi) in ACCOUNT_NUMBER_RANGES.items():
        if lo <= n <= hi:
            return account_type
    return None


# 12 comptes de base (is_system=true) — société canadienne QC (§4.1)
DEFAULT_BASE_ACCOUNTS = [
    {"account_number": "1000", "name": "Encaisse",                 "sub_type": "current_asset"},
    {"account_number": "1100", "name": "Comptes clients",          "sub_type": "current_asset"},
    {"account_number": "1200", "name": "TPS à recouvrer",          "sub_type": "tax_recoverable"},
    {"account_number": "1210", "name": "TVQ à recouvrer",          "sub_type": "tax_recoverable"},
    {"account_number": "2000", "name": "Comptes fournisseurs",     "sub_type": "current_liability"},
    {"account_number": "2100", "name": "TPS à payer",              "sub_type": "tax_payable"},
    {"account_number": "2110", "name": "TVQ à payer",              "sub_type": "tax_payable"},
    {"account_number": "3000", "name": "Capital-actions",          "sub_type": "share_capital"},
    {"account_number": "3100", "name": "Apport du propriétaire",   "sub_type": "contributed_capital"},
    {"account_number": "3200", "name": "Bénéfices non répartis",   "sub_type": "retained_earnings"},
    {"account_number": "4000", "name": "Revenus de services",      "sub_type": "operating_revenue"},
    {"account_number": "5900", "name": "Dépenses diverses",        "sub_type": "operating_expense"},
]

# Numérotation des comptes de dépenses par catégorie ARC (§4.2).
# "other" est couvert par 5900 (Dépenses diverses) ci-dessus.
EXPENSE_ACCOUNT_NUMBERS = {
    "office_expenses":     "5000",
    "office_supplies":     "5010",
    "professional_fees":   "5020",
    "bank_charges":        "5030",
    "subscriptions":       "5040",
    "advertising":         "5100",
    "meals_entertainment": "5110",
    "rent":                "5200",
    "utilities":           "5210",
    "insurance":           "5220",
    "repairs_maintenance": "5230",
    "travel":              "5300",
    "vehicle_expenses":    "5310",
    "delivery":            "5320",
    "salaries":            "5400",
    "subcontracts":        "5410",
    "management_fees":     "5420",
}


def _build_default_accounts(organization_id: str, user_id: str) -> list:
    """Retourne les 29 comptes du plan par défaut (12 base + 17 dépenses),
    scopés org, is_system=true. Comptes de dépenses générés depuis
    EXPENSE_CATEGORIES (§4.3) pour rester synchronisés avec la feature #3."""
    now = datetime.now(timezone.utc).isoformat()
    accounts = []

    def _make(account_number, name, sub_type, expense_category_code=None):
        account_type = _account_type_for_number(account_number)
        return {
            "id": str(uuid.uuid4()),
            "organization_id": organization_id,
            "created_by_user_id": user_id,
            "account_number": account_number,
            "name": name,
            "account_type": account_type,
            "sub_type": sub_type,
            "normal_balance": _normal_balance_for_type(account_type),
            "is_active": True,
            "is_system": True,
            "expense_category_code": expense_category_code,
            "description": "",
            "created_at": now,
        }

    for base in DEFAULT_BASE_ACCOUNTS:
        accounts.append(_make(base["account_number"], base["name"], base["sub_type"]))

    for cat in EXPENSE_CATEGORIES:
        code = cat["code"]
        if code == "other":
            continue  # couvert par 5900
        number = EXPENSE_ACCOUNT_NUMBERS.get(code)
        if not number:
            continue
        accounts.append(_make(number, cat["label_fr"], "operating_expense",
                              expense_category_code=code))

    return accounts
```

- [ ] **Step 4: Tests pass**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
pytest tests/test_general_ledger.py -v 2>&1 | tail -25
```
Expected : tous les tests de Task 1 passent (constantes + normal_balance + type_for_number + build_default).

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_general_ledger.py
git commit -m "feat(ledger): chart of accounts constants + normal_balance/type helpers"
```

---

## Task 2 : RBAC accounting:read/write

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_general_ledger.py`

- [ ] **Step 1: Écrire les tests RBAC**

Append à `backend/tests/test_general_ledger.py` :
```python
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

    def test_viewer_cannot_get_write_via_matrix(self):
        # matrice polluée : viewer tente accounting:write → doit rester filtré
        org = {"role_permissions": {"viewer": ["accounting:read", "accounting:write"]}}
        perms = _resolve_permissions(org, "viewer")
        # accounting:write est editable donc PASSE le filtre PERMISSIONS_EDITABLE ;
        # ce test documente que la matrice owner-controlee peut l'accorder volontairement.
        assert "accounting:write" in perms
```

- [ ] **Step 2: Verify failure**

```bash
pytest tests/test_general_ledger.py::TestAccountingPermissions -v 2>&1 | tail -12
```
Expected : `accounting:read` absent de `PERMISSIONS_EDITABLE`.

- [ ] **Step 3: Ajouter les codes dans `PERMISSIONS_EDITABLE`**

Dans `backend/server.py`, section `PERMISSIONS_EDITABLE` (ligne 1197). AJOUTER la ligne `accounting` à la fin de la liste, avant le `]` :

```python
    "settings:read",   "settings:write",  # infos entreprise, num fiscaux, province, %
    "accounting:read", "accounting:write",  # feature #12 — grand livre
]
```

- [ ] **Step 4: Ajouter `accounting:read` au viewer par défaut**

Dans `DEFAULT_ROLE_PERMISSIONS["viewer"]` (ligne 1217), ajouter `"accounting:read"` :

```python
    "viewer": [
        "expenses:read", "invoices:read", "quotes:read",
        "clients:read", "products:read", "employees:read",
        "reports:read", "bank:read", "settings:read",
        "accounting:read",
    ],
```

`accountant` reçoit `accounting:read`+`accounting:write` automatiquement (`list(PERMISSIONS_EDITABLE)`). `owner` via `_resolve_permissions`.

- [ ] **Step 5: Backfill perms dans `migrate_organizations_v1` (idempotent)**

Dans `migrate_organizations_v1`, repérer le bloc de backfill perms settings (autour de la ligne 1398, boucle `for org in db.organizations.find(...)`). Ce bloc ajoute déjà `settings:*` si absent. AJOUTER la logique `accounting` dans la même boucle. Chercher :

```python
    for org in db.organizations.find({}, {"id": 1, "role_permissions": 1}):
        rp = org.get("role_permissions") or {}
        changed = False
```

et compléter le corps de la boucle avec (après les blocs settings existants, avant le `if changed:`) :

```python
        # Feature #12 — accounting:read/write (comptable) ; accounting:read (lecteur)
        acc = set(rp.get("accountant", []))
        if "accounting:read" not in acc or "accounting:write" not in acc:
            acc.update({"accounting:read", "accounting:write"})
            rp["accountant"] = sorted(acc)
            changed = True
        vw = set(rp.get("viewer", []))
        if "accounting:read" not in vw:
            vw.add("accounting:read")
            rp["viewer"] = sorted(vw)
            changed = True
```

> Note : on n'ajoute que si absent. Un owner qui retire volontairement `accounting:*` ne se le verra pas ré-imposer tant que le code reste présent (la clé est présente → pas de re-ajout). Cohérent avec le backfill settings feature #11.1.

- [ ] **Step 6: Tests pass**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
pytest tests/test_general_ledger.py::TestAccountingPermissions -v 2>&1 | tail -12
```
Expected : 6 tests pass.

- [ ] **Step 7: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_general_ledger.py
git commit -m "feat(ledger): RBAC accounting:read/write + backfill perms migration"
```

---

## Task 3 : Migration `migrate_general_ledger_v1` + champs fiscaux

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_general_ledger.py`

- [ ] **Step 1: Écrire les tests de la migration**

Append à `backend/tests/test_general_ledger.py` :
```python
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
```

- [ ] **Step 2: Verify failure**

```bash
pytest tests/test_general_ledger.py::TestMigrateGeneralLedgerV1 -v 2>&1 | tail -12
```
Expected : ImportError `migrate_general_ledger_v1`.

- [ ] **Step 3: Implémenter la migration**

Dans `backend/server.py`, AJOUTER après `migrate_organizations_v1` (la fonction se termine autour de la ligne 1440 ; repérer sa fin puis insérer juste après) :

```python
def migrate_general_ledger_v1():
    """Idempotente. Safe à chaque boot (feature #12).
    1. Backfill des champs fiscaux sur company_settings (défaut 31 déc.).
    2. Backfill accounting:read/write dans role_permissions des orgs existantes.
    3. Indexes des nouvelles collections.
    Le plan comptable par défaut est seedé au 1er accès GL (lazy, PAS ici)."""
    # 1. Champs fiscaux — n'écrase jamais une valeur existante
    db.company_settings.update_many(
        {"fiscal_year_end_month": {"$exists": False}},
        {"$set": {"fiscal_year_end_month": 12}}
    )
    db.company_settings.update_many(
        {"fiscal_year_end_day": {"$exists": False}},
        {"$set": {"fiscal_year_end_day": 31}}
    )
    # 2. Backfill perms accounting (accountant → read+write ; viewer → read)
    for org in db.organizations.find({}, {"id": 1, "role_permissions": 1}):
        rp = org.get("role_permissions") or {}
        changed = False
        acc = set(rp.get("accountant", []))
        if "accounting:read" not in acc or "accounting:write" not in acc:
            acc.update({"accounting:read", "accounting:write"})
            rp["accountant"] = sorted(acc)
            changed = True
        vw = set(rp.get("viewer", []))
        if "accounting:read" not in vw:
            vw.add("accounting:read")
            rp["viewer"] = sorted(vw)
            changed = True
        if changed:
            db.organizations.update_one({"id": org["id"]},
                                        {"$set": {"role_permissions": rp}})
    # 3. Indexes idempotents
    db.chart_of_accounts.create_index(
        [("organization_id", 1), ("account_number", 1)], unique=True)
    db.chart_of_accounts.create_index([("organization_id", 1), ("account_type", 1)])
    db.chart_of_accounts.create_index([("organization_id", 1), ("is_active", 1)])
    db.journal_entries.create_index([("organization_id", 1), ("entry_date", 1)])
    db.journal_entries.create_index(
        [("organization_id", 1), ("entry_number", 1)], unique=True)
    db.journal_entries.create_index([("organization_id", 1), ("status", 1)])
    db.journal_entries.create_index(
        [("organization_id", 1), ("source_type", 1), ("source_id", 1)])
    db.ledger_counters.create_index("id", unique=True)
```

- [ ] **Step 4: Brancher au startup**

Dans le bloc `@app.on_event("startup") def seed_data()` (ligne 5555), AJOUTER après l'appel `migrate_organizations_v1()` (ligne 5582) :

```python
        # Migration feature #12 — grand livre (idempotente)
        migrate_general_ledger_v1()
```

- [ ] **Step 5: Ajouter les champs fiscaux à `PUT /api/settings/company`**

Localiser le endpoint settings company :
```bash
grep -n "settings/company\|def update_company_settings\|def get_company_settings" backend/server.py | head
```
Dans le handler PUT (`update_company_settings`), après la validation des champs existants (`home_office_percentage` etc.), AJOUTER la validation + persistance des champs fiscaux. Chercher le dict de `$set` construit à partir du body et ajouter :

```python
    # Feature #12 — exercice financier (validation stricte)
    if "fiscal_year_end_month" in body:
        m = body["fiscal_year_end_month"]
        if not isinstance(m, int) or not (1 <= m <= 12):
            raise HTTPException(400, "fiscal_year_end_month doit être entre 1 et 12")
        update_fields["fiscal_year_end_month"] = m
    if "fiscal_year_end_day" in body:
        d = body["fiscal_year_end_day"]
        if not isinstance(d, int) or not (1 <= d <= 31):
            raise HTTPException(400, "fiscal_year_end_day doit être entre 1 et 31")
        update_fields["fiscal_year_end_day"] = d
```

> Adapter le nom de la variable d'accumulation (`update_fields` / `update_data` / `set_fields`) au code existant du handler. Le `PUT` reste gaté `settings:write`.

- [ ] **Step 6: Tests pass**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_general_ledger.py::TestMigrateGeneralLedgerV1 -v 2>&1 | tail -12
```
Expected : 4 tests pass.

- [ ] **Step 7: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_general_ledger.py
git commit -m "feat(ledger): migrate_general_ledger_v1 + fiscal fields on company_settings"
```

---

## Task 4 : Endpoints CRUD comptes + seed lazy

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_general_ledger_integration.py`

- [ ] **Step 1: Écrire les tests d'intégration CRUD**

Append à `backend/tests/test_general_ledger_integration.py` :
```python
class TestChartOfAccounts:
    def test_seed_lazy_on_first_access(self, client, owner_headers):
        r = client.get("/api/ledger/accounts", headers=owner_headers)
        assert r.status_code == 200, r.text
        accounts = r.json()
        assert len(accounts) >= 29
        numbers = [a["account_number"] for a in accounts]
        assert "1000" in numbers and "3100" in numbers and "5900" in numbers
        # trié par account_number
        assert numbers == sorted(numbers)

    def test_seed_idempotent(self, client, owner_headers):
        r1 = client.get("/api/ledger/accounts", headers=owner_headers)
        n1 = len(r1.json())
        r2 = client.get("/api/ledger/accounts", headers=owner_headers)
        assert len(r2.json()) == n1  # pas de doublon au 2e appel

    def test_create_account_happy_path(self, client, owner_headers):
        num = "1500"
        client.delete_by_number = None  # noqa
        r = client.post("/api/ledger/accounts", headers=owner_headers, json={
            "account_number": num, "name": "Équipement", "sub_type": "fixed_asset",
        })
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["account_type"] == "asset"
        assert body["normal_balance"] == "debit"
        assert body["is_system"] is False
        # cleanup
        client.delete(f"/api/ledger/accounts/{body['id']}", headers=owner_headers)

    def test_create_out_of_range_type_mismatch(self, client, owner_headers):
        # 6xxx hors plages canoniques
        r = client.post("/api/ledger/accounts", headers=owner_headers, json={
            "account_number": "6000", "name": "Bidon",
        })
        assert r.status_code == 400

    def test_create_duplicate_number_409(self, client, owner_headers):
        r = client.post("/api/ledger/accounts", headers=owner_headers, json={
            "account_number": "1000", "name": "Doublon encaisse",
        })
        assert r.status_code == 409

    def test_delete_system_account_forbidden(self, client, owner_headers):
        accounts = client.get("/api/ledger/accounts", headers=owner_headers).json()
        cash = next(a for a in accounts if a["account_number"] == "1000")
        r = client.delete(f"/api/ledger/accounts/{cash['id']}", headers=owner_headers)
        assert r.status_code == 400

    def test_put_cannot_change_number_or_type(self, client, owner_headers):
        r = client.post("/api/ledger/accounts", headers=owner_headers, json={
            "account_number": "1510", "name": "Mobilier", "sub_type": "fixed_asset",
        })
        acc_id = r.json()["id"]
        try:
            r2 = client.put(f"/api/ledger/accounts/{acc_id}", headers=owner_headers,
                            json={"account_number": "1520"})
            assert r2.status_code == 400
            r3 = client.put(f"/api/ledger/accounts/{acc_id}", headers=owner_headers,
                            json={"name": "Mobilier de bureau"})
            assert r3.status_code == 200
            assert r3.json()["name"] == "Mobilier de bureau"
        finally:
            client.delete(f"/api/ledger/accounts/{acc_id}", headers=owner_headers)
```

- [ ] **Step 2: Verify failure**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_general_ledger_integration.py::TestChartOfAccounts -v 2>&1 | tail -15
```
Expected : 404 sur tous `/api/ledger/accounts`.

- [ ] **Step 3: Implémenter le seed lazy + les endpoints CRUD**

Dans `backend/server.py`, chercher la fin de la section RBAC endpoints (`/api/org/*`, autour de `revoke_invitation`) et AJOUTER une nouvelle section « Grand livre — endpoints (feature #12) ». Commencer par le helper de seed lazy et le CRUD comptes :

```python
# ─── Grand livre — endpoints (feature #12) ───

def _ensure_chart_seeded(organization_id: str, user_id: str):
    """Seed lazy du plan comptable par défaut au 1er accès GL (§8.3).
    Idempotent : ne seed que si zéro compte pour l'org."""
    if db.chart_of_accounts.count_documents({"organization_id": organization_id}) == 0:
        db.chart_of_accounts.insert_many(
            _build_default_accounts(organization_id, user_id))


@app.get("/api/ledger/accounts")
def list_accounts(
    type: str = None,
    active: bool = None,
    current_user: CurrentUser = Depends(require_permission("accounting:read")),
):
    _ensure_chart_seeded(current_user.organization_id, current_user.id)
    query = {"organization_id": current_user.organization_id}
    if type:
        query["account_type"] = type
    if active is not None:
        query["is_active"] = active
    cursor = db.chart_of_accounts.find(query, {"_id": 0}).sort("account_number", 1)
    return list(cursor)


@app.post("/api/ledger/accounts", status_code=201)
def create_account(
    body: dict,
    current_user: CurrentUser = Depends(require_permission("accounting:write")),
):
    _ensure_chart_seeded(current_user.organization_id, current_user.id)
    account_number = str(body.get("account_number") or "").strip()
    name = (body.get("name") or "").strip()
    if not account_number or not name:
        raise HTTPException(400, "account_number et name requis")
    if not (account_number.isdigit() and len(account_number) == 4):
        raise HTTPException(400, "account_number doit être 4 chiffres (1000-5999)")
    account_type = _account_type_for_number(account_number)
    if account_type is None:
        raise HTTPException(400, "account_number hors des plages canoniques 1000-5999")
    existing = db.chart_of_accounts.find_one({
        "organization_id": current_user.organization_id,
        "account_number": account_number,
    })
    if existing:
        raise HTTPException(409, "Un compte porte déjà ce numéro")
    doc = {
        "id": str(uuid.uuid4()),
        "organization_id": current_user.organization_id,
        "created_by_user_id": current_user.id,
        "account_number": account_number,
        "name": name,
        "account_type": account_type,
        "sub_type": body.get("sub_type"),
        "normal_balance": _normal_balance_for_type(account_type),
        "is_active": True,
        "is_system": False,
        "expense_category_code": body.get("expense_category_code"),
        "description": (body.get("description") or "").strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.chart_of_accounts.insert_one(dict(doc))
    return {k: v for k, v in doc.items() if k != "_id"}


@app.put("/api/ledger/accounts/{account_id}")
def update_account(
    account_id: str,
    body: dict,
    current_user: CurrentUser = Depends(require_permission("accounting:write")),
):
    acc = db.chart_of_accounts.find_one({
        "id": account_id, "organization_id": current_user.organization_id,
    }, {"_id": 0})
    if not acc:
        raise HTTPException(404, "Compte introuvable")
    if "account_number" in body or "account_type" in body:
        raise HTTPException(400, "Numéro et type de compte non modifiables")
    set_fields = {}
    if "name" in body:
        name = (body.get("name") or "").strip()
        if not name:
            raise HTTPException(400, "name ne peut être vide")
        set_fields["name"] = name
    if "sub_type" in body:
        set_fields["sub_type"] = body["sub_type"]
    if "description" in body:
        set_fields["description"] = (body.get("description") or "").strip()
    if "expense_category_code" in body:
        set_fields["expense_category_code"] = body["expense_category_code"]
    if "is_active" in body:
        want_active = bool(body["is_active"])
        if acc.get("is_system") and not want_active:
            raise HTTPException(400, "Un compte système ne peut être désactivé")
        set_fields["is_active"] = want_active
    if set_fields:
        db.chart_of_accounts.update_one(
            {"id": account_id, "organization_id": current_user.organization_id},
            {"$set": set_fields})
    return db.chart_of_accounts.find_one(
        {"id": account_id, "organization_id": current_user.organization_id}, {"_id": 0})


@app.delete("/api/ledger/accounts/{account_id}", status_code=204)
def delete_account(
    account_id: str,
    current_user: CurrentUser = Depends(require_permission("accounting:write")),
):
    acc = db.chart_of_accounts.find_one({
        "id": account_id, "organization_id": current_user.organization_id,
    })
    if not acc:
        raise HTTPException(404, "Compte introuvable")
    if acc.get("is_system"):
        raise HTTPException(400, "Compte système protégé — désactivez-le plutôt")
    used = db.journal_entries.count_documents({
        "organization_id": current_user.organization_id,
        "lines.account_id": account_id,
    })
    if used > 0:
        raise HTTPException(400, "Compte utilisé par des écritures — désactivez-le plutôt")
    db.chart_of_accounts.delete_one(
        {"id": account_id, "organization_id": current_user.organization_id})
    return
```

- [ ] **Step 4: Tests pass**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_general_ledger_integration.py::TestChartOfAccounts -v 2>&1 | tail -15
```
Expected : 8 tests pass.

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_general_ledger_integration.py
git commit -m "feat(ledger): accounts CRUD endpoints + lazy chart seed"
```

---

## Task 5 : Helpers partie double — validation équilibre + calcul de solde

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_general_ledger.py`

- [ ] **Step 1: Écrire les tests des helpers**

Append à `backend/tests/test_general_ledger.py` :
```python
from server import _validate_entry_balance, _account_balance
from fastapi import HTTPException as _HTTPExc


class TestValidateEntryBalance:
    def test_balanced_ok(self):
        lines = [
            {"debit": 100.0, "credit": 0.0},
            {"debit": 0.0, "credit": 100.0},
        ]
        _validate_entry_balance(lines)  # no raise

    def test_less_than_two_lines(self):
        with pytest.raises(_HTTPExc) as e:
            _validate_entry_balance([{"debit": 100.0, "credit": 0.0}])
        assert e.value.status_code == 400

    def test_unbalanced(self):
        with pytest.raises(_HTTPExc) as e:
            _validate_entry_balance([
                {"debit": 100.0, "credit": 0.0},
                {"debit": 0.0, "credit": 90.0},
            ])
        assert e.value.status_code == 400

    def test_line_with_both_debit_and_credit(self):
        with pytest.raises(_HTTPExc) as e:
            _validate_entry_balance([
                {"debit": 50.0, "credit": 50.0},
                {"debit": 0.0, "credit": 0.0},
            ])
        assert e.value.status_code == 400

    def test_negative_line(self):
        with pytest.raises(_HTTPExc) as e:
            _validate_entry_balance([
                {"debit": -100.0, "credit": 0.0},
                {"debit": 0.0, "credit": -100.0},
            ])
        assert e.value.status_code == 400

    def test_tolerance_half_cent(self):
        # écart 0,004 $ < 0,005 → accepté
        _validate_entry_balance([
            {"debit": 100.004, "credit": 0.0},
            {"debit": 0.0, "credit": 100.0},
        ])
```

- [ ] **Step 2: Verify failure**

```bash
pytest tests/test_general_ledger.py::TestValidateEntryBalance -v 2>&1 | tail -12
```

- [ ] **Step 3: Implémenter `_validate_entry_balance` + `_account_balance`**

Dans `backend/server.py`, dans la section helpers du grand livre (après `_build_default_accounts`, Task 1), AJOUTER :

```python
def _validate_entry_balance(lines: list) -> None:
    """Force la partie double (§5.1). Raise HTTPException(400) si invalide."""
    if not lines or len(lines) < 2:
        raise HTTPException(400, "Une écriture doit avoir au moins 2 lignes")
    total_debit = 0.0
    total_credit = 0.0
    for ln in lines:
        d = round(float(ln.get("debit", 0) or 0), 2)
        c = round(float(ln.get("credit", 0) or 0), 2)
        if d < 0 or c < 0:
            raise HTTPException(400, "Débit et crédit doivent être >= 0")
        if (d > 0) == (c > 0):
            raise HTTPException(
                400, "Chaque ligne doit avoir soit un débit soit un crédit, pas les deux")
        total_debit += d
        total_credit += c
    if abs(round(total_debit, 2) - round(total_credit, 2)) > 0.005:
        raise HTTPException(
            400,
            f"Écriture déséquilibrée : débits {total_debit:.2f} ≠ crédits {total_credit:.2f}")


def _account_balance(organization_id: str, account_id: str, normal_balance: str,
                     start_date: str = None, as_of_date: str = None) -> float:
    """Solde d'un compte, orienté par le solde normal (§5.2).
    Compte TOUTES les écritures status='posted', SANS EXCEPTION — y compris
    les écritures d'origine contre-passées ET leurs miroirs de contre-passation
    (les deux restent 'posted', cf. §5.3). Ne filtre JAMAIS sur reverses_entry_id
    ni reversed_by_entry_id (champs d'audit seulement). Il n'existe pas de statut
    'reversed' : une écriture contre-passée n'est pas retirée du solde, sinon
    double effet → solde faux. Optionnellement borné [start_date, as_of_date]
    (dates ISO 'YYYY-MM-DD' incluses)."""
    match = {"organization_id": organization_id, "status": "posted",
             "lines.account_id": account_id}
    date_filter = {}
    if start_date:
        date_filter["$gte"] = start_date
    if as_of_date:
        date_filter["$lte"] = as_of_date
    if date_filter:
        match["entry_date"] = date_filter
    total_debit = 0.0
    total_credit = 0.0
    for entry in db.journal_entries.find(match, {"_id": 0, "lines": 1}):
        for ln in entry["lines"]:
            if ln["account_id"] == account_id:
                total_debit += float(ln.get("debit", 0) or 0)
                total_credit += float(ln.get("credit", 0) or 0)
    if normal_balance == "debit":
        return round(total_debit - total_credit, 2)
    return round(total_credit - total_debit, 2)
```

- [ ] **Step 4: Tests pass**

```bash
pytest tests/test_general_ledger.py::TestValidateEntryBalance -v 2>&1 | tail -12
```
Expected : 6 tests pass.

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_general_ledger.py
git commit -m "feat(ledger): _validate_entry_balance + _account_balance helpers"
```

---

## Task 6 : Endpoints journal — équilibre forcé + post + contre-passation

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_general_ledger_integration.py`

- [ ] **Step 1: Écrire les tests d'intégration journal**

Append à `backend/tests/test_general_ledger_integration.py` :
```python
class TestJournalEntries:
    def _accounts(self, client, owner_headers):
        accounts = client.get("/api/ledger/accounts", headers=owner_headers).json()
        by_num = {a["account_number"]: a for a in accounts}
        return by_num

    def _balanced_body(self, by_num, amount=250.0, status="posted"):
        return {
            "entry_date": "2026-06-15",
            "description": "Test écriture",
            "status": status,
            "lines": [
                {"account_id": by_num["1000"]["id"], "debit": amount, "credit": 0},
                {"account_id": by_num["4000"]["id"], "debit": 0, "credit": amount},
            ],
        }

    def test_post_balanced_entry_creates_je_number(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        r = client.post("/api/ledger/entries", headers=owner_headers,
                        json=self._balanced_body(by_num))
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["entry_number"].startswith("JE-")
        assert body["status"] == "posted"
        assert body["posted_at"] is not None
        assert round(body["total_debit"], 2) == round(body["total_credit"], 2)
        # snapshot des lignes
        assert body["lines"][0]["account_number"] == "1000"
        client.delete(f"/api/ledger/entries/{body['id']}", headers=owner_headers)

    def test_post_unbalanced_400(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        body = self._balanced_body(by_num)
        body["lines"][1]["credit"] = 100.0  # déséquilibre
        r = client.post("/api/ledger/entries", headers=owner_headers, json=body)
        assert r.status_code == 400

    def test_draft_then_post(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        r = client.post("/api/ledger/entries", headers=owner_headers,
                        json=self._balanced_body(by_num, status="draft"))
        assert r.status_code == 201
        entry_id = r.json()["id"]
        assert r.json()["status"] == "draft"
        assert r.json()["posted_at"] is None
        r2 = client.post(f"/api/ledger/entries/{entry_id}/post", headers=owner_headers)
        assert r2.status_code == 200
        assert r2.json()["status"] == "posted"
        client.delete(f"/api/ledger/entries/{entry_id}", headers=owner_headers)

    def test_put_on_posted_forbidden(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        r = client.post("/api/ledger/entries", headers=owner_headers,
                        json=self._balanced_body(by_num))
        entry_id = r.json()["id"]
        try:
            r2 = client.put(f"/api/ledger/entries/{entry_id}", headers=owner_headers,
                            json={"description": "modifié"})
            assert r2.status_code == 400
            r3 = client.delete(f"/api/ledger/entries/{entry_id}", headers=owner_headers)
            assert r3.status_code == 400  # posted → DELETE interdit
        finally:
            # reverse pour nettoyer proprement puis rien (piste d'audit)
            pass

    def test_reverse_creates_mirror(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        r = client.post("/api/ledger/entries", headers=owner_headers,
                        json=self._balanced_body(by_num, amount=333.0))
        entry_id = r.json()["id"]
        r2 = client.post(f"/api/ledger/entries/{entry_id}/reverse",
                         headers=owner_headers, json={})
        assert r2.status_code == 201, r2.text
        rev = r2.json()
        assert rev["entry_type"] == "reversal"
        assert rev["status"] == "posted"           # le miroir est POSTED
        assert rev["reverses_entry_id"] == entry_id
        # lignes inversées : ce qui était débit devient crédit
        assert rev["lines"][0]["credit"] == 333.0
        assert rev["lines"][0]["debit"] == 0
        # origine : RESTE 'posted', SEUL le lien d'audit est posé (pas de statut 'reversed')
        origin = client.get(f"/api/ledger/entries/{entry_id}",
                            headers=owner_headers).json()
        assert origin["status"] == "posted"        # ⚠️ reste posted, JAMAIS 'reversed'
        assert origin["reversed_by_entry_id"] == rev["id"]

    def test_reverse_nets_to_zero_and_stays_balanced(self, client, owner_headers):
        """Le test qui manquait (§5.3) : Dr Encaisse 100 / Cr Revenus 100 →
        solde Encaisse = 100 ; après contre-passation → Encaisse = 0 ET Revenus = 0
        ET la balance de vérification reste équilibrée. C'est l'invariant net zéro
        garanti par le fait que l'origine ET le miroir restent 'posted'."""
        by_num = self._accounts(client, owner_headers)

        def _bal(num, as_of="2030-12-31"):
            tb = client.get(f"/api/ledger/trial-balance?as_of={as_of}",
                            headers=owner_headers).json()
            row = next((a for a in tb["accounts"]
                        if a["account_number"] == num), None)
            if not row:
                return 0.0
            return round(row["debit_balance"] - row["credit_balance"], 2)

        cash0 = _bal("1000")
        rev0 = _bal("4000")
        # Dr Encaisse (1000) 100 / Cr Revenus (4000) 100
        r = client.post("/api/ledger/entries", headers=owner_headers, json={
            "entry_date": "2029-06-15", "description": "Vente à contre-passer",
            "status": "posted",
            "lines": [
                {"account_id": by_num["1000"]["id"], "debit": 100.0, "credit": 0},
                {"account_id": by_num["4000"]["id"], "debit": 0, "credit": 100.0},
            ],
        })
        entry_id = r.json()["id"]
        # après post : Encaisse +100 (débit), Revenus +100 (crédit → -100 en net Dr-Cr)
        assert round(_bal("1000") - cash0, 2) == 100.0
        assert round(_bal("4000") - rev0, 2) == -100.0
        # contre-passation
        r2 = client.post(f"/api/ledger/entries/{entry_id}/reverse",
                         headers=owner_headers, json={"entry_date": "2029-06-16"})
        assert r2.status_code == 201, r2.text
        # net zéro : les deux comptes reviennent EXACTEMENT à leur solde d'avant
        assert round(_bal("1000") - cash0, 2) == 0.0   # Encaisse nette = 0
        assert round(_bal("4000") - rev0, 2) == 0.0    # Revenus nets = 0
        # balance de vérification toujours équilibrée
        tb = client.get("/api/ledger/trial-balance?as_of=2030-12-31",
                        headers=owner_headers).json()
        assert tb["balanced"] is True
        assert round(tb["total_debit"], 2) == round(tb["total_credit"], 2)

    def test_reverse_twice_forbidden(self, client, owner_headers):
        """Double contre-passation interdite : le 2e reverse sur la même origine
        (reversed_by_entry_id déjà posé) → 400."""
        by_num = self._accounts(client, owner_headers)
        r = client.post("/api/ledger/entries", headers=owner_headers,
                        json=self._balanced_body(by_num, amount=42.0))
        entry_id = r.json()["id"]
        r1 = client.post(f"/api/ledger/entries/{entry_id}/reverse",
                         headers=owner_headers, json={})
        assert r1.status_code == 201
        r2 = client.post(f"/api/ledger/entries/{entry_id}/reverse",
                         headers=owner_headers, json={})
        assert r2.status_code == 400   # déjà contre-passée

    def test_reverse_non_posted_400(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        r = client.post("/api/ledger/entries", headers=owner_headers,
                        json=self._balanced_body(by_num, status="draft"))
        entry_id = r.json()["id"]
        r2 = client.post(f"/api/ledger/entries/{entry_id}/reverse",
                         headers=owner_headers, json={})
        assert r2.status_code == 400
        client.delete(f"/api/ledger/entries/{entry_id}", headers=owner_headers)
```

- [ ] **Step 2: Verify failure**

```bash
pytest tests/test_general_ledger_integration.py::TestJournalEntries -v 2>&1 | tail -15
```
Expected : 404.

- [ ] **Step 3: Implémenter le compteur atomique + les endpoints journal**

Dans `backend/server.py`, dans la section endpoints GL (après le CRUD comptes), AJOUTER le helper de numérotation puis les endpoints. D'abord le helper dans la section helpers (à côté de `_account_balance`) :

```python
def _next_entry_number(organization_id: str, prefix: str = "JE") -> str:
    """Attribue un numéro d'écriture atomique par org (§3.3).
    Zéro race via find_one_and_update $inc upsert."""
    from pymongo import ReturnDocument
    counter_id = f"{organization_id}:journal_entry"
    doc = db.ledger_counters.find_one_and_update(
        {"id": counter_id},
        {"$inc": {"value": 1},
         "$setOnInsert": {"organization_id": organization_id,
                          "counter_type": "journal_entry"}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return f"{prefix}-{doc['value']:04d}"


def _snapshot_lines(organization_id: str, lines: list) -> list:
    """Valide que chaque account_id est actif + même org, et dénormalise
    account_number/account_name sur chaque ligne. Retourne les lignes enrichies."""
    enriched = []
    for ln in lines:
        account_id = ln.get("account_id")
        acc = db.chart_of_accounts.find_one({
            "id": account_id, "organization_id": organization_id, "is_active": True,
        }, {"_id": 0})
        if not acc:
            raise HTTPException(400, f"Compte inactif ou introuvable : {account_id}")
        enriched.append({
            "line_id": str(uuid.uuid4()),
            "account_id": account_id,
            "account_number": acc["account_number"],
            "account_name": acc["name"],
            "debit": round(float(ln.get("debit", 0) or 0), 2),
            "credit": round(float(ln.get("credit", 0) or 0), 2),
            "line_description": ln.get("line_description"),
        })
    return enriched


def _create_journal_entry(organization_id: str, user_id: str, entry_date: str,
                          description: str, lines: list, status: str = "posted",
                          reference: str = None, entry_type: str = "manual",
                          reverses_entry_id: str = None,
                          entry_number: str = None) -> dict:
    """Factory interne d'écriture (partagée par journal manuel, ouverture,
    apport, contre-passation). Valide l'équilibre + snapshot les lignes."""
    _validate_entry_balance(lines)
    enriched = _snapshot_lines(organization_id, lines)
    total_debit = round(sum(l["debit"] for l in enriched), 2)
    total_credit = round(sum(l["credit"] for l in enriched), 2)
    now = datetime.now(timezone.utc).isoformat()
    if entry_number is None:
        entry_number = _next_entry_number(organization_id)
    doc = {
        "id": str(uuid.uuid4()),
        "organization_id": organization_id,
        "created_by_user_id": user_id,
        "entry_number": entry_number,
        "entry_date": entry_date,
        "description": description,
        "reference": reference,
        "entry_type": entry_type,
        "status": status,
        "lines": enriched,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "reverses_entry_id": reverses_entry_id,
        "reversed_by_entry_id": None,
        "source_type": None,
        "source_id": None,
        "created_at": now,
        "posted_at": now if status == "posted" else None,
    }
    db.journal_entries.insert_one(dict(doc))
    return {k: v for k, v in doc.items() if k != "_id"}


@app.get("/api/ledger/entries")
def list_entries(
    start: str = None, end: str = None, account_id: str = None, status: str = None,
    current_user: CurrentUser = Depends(require_permission("accounting:read")),
):
    _ensure_chart_seeded(current_user.organization_id, current_user.id)
    query = {"organization_id": current_user.organization_id}
    if status:
        query["status"] = status
    if account_id:
        query["lines.account_id"] = account_id
    if start or end:
        df = {}
        if start:
            df["$gte"] = start
        if end:
            df["$lte"] = end
        query["entry_date"] = df
    cursor = db.journal_entries.find(query, {"_id": 0}) \
        .sort([("entry_date", -1), ("entry_number", -1)])
    return list(cursor)


@app.get("/api/ledger/entries/{entry_id}")
def get_entry(
    entry_id: str,
    current_user: CurrentUser = Depends(require_permission("accounting:read")),
):
    entry = db.journal_entries.find_one({
        "id": entry_id, "organization_id": current_user.organization_id,
    }, {"_id": 0})
    if not entry:
        raise HTTPException(404, "Écriture introuvable")
    return entry


@app.post("/api/ledger/entries", status_code=201)
def create_entry(
    body: dict,
    current_user: CurrentUser = Depends(require_permission("accounting:write")),
):
    _ensure_chart_seeded(current_user.organization_id, current_user.id)
    status = body.get("status", "draft")
    if status not in ("draft", "posted"):
        raise HTTPException(400, "status doit être 'draft' ou 'posted'")
    return _create_journal_entry(
        current_user.organization_id, current_user.id,
        entry_date=body.get("entry_date"),
        description=(body.get("description") or "").strip(),
        lines=body.get("lines") or [],
        status=status,
        reference=body.get("reference"),
        entry_type="manual",
    )


@app.put("/api/ledger/entries/{entry_id}")
def update_entry(
    entry_id: str,
    body: dict,
    current_user: CurrentUser = Depends(require_permission("accounting:write")),
):
    entry = db.journal_entries.find_one({
        "id": entry_id, "organization_id": current_user.organization_id,
    }, {"_id": 0})
    if not entry:
        raise HTTPException(404, "Écriture introuvable")
    if entry["status"] == "posted":
        raise HTTPException(400, "Écriture figée — contre-passez-la")
    lines = body.get("lines", entry["lines"])
    _validate_entry_balance(lines)
    enriched = _snapshot_lines(current_user.organization_id, lines)
    set_fields = {
        "entry_date": body.get("entry_date", entry["entry_date"]),
        "description": (body.get("description", entry["description"]) or "").strip(),
        "reference": body.get("reference", entry["reference"]),
        "lines": enriched,
        "total_debit": round(sum(l["debit"] for l in enriched), 2),
        "total_credit": round(sum(l["credit"] for l in enriched), 2),
    }
    db.journal_entries.update_one(
        {"id": entry_id, "organization_id": current_user.organization_id},
        {"$set": set_fields})
    return db.journal_entries.find_one(
        {"id": entry_id, "organization_id": current_user.organization_id}, {"_id": 0})


@app.post("/api/ledger/entries/{entry_id}/post")
def post_entry(
    entry_id: str,
    current_user: CurrentUser = Depends(require_permission("accounting:write")),
):
    entry = db.journal_entries.find_one({
        "id": entry_id, "organization_id": current_user.organization_id,
    }, {"_id": 0})
    if not entry:
        raise HTTPException(404, "Écriture introuvable")
    if entry["status"] != "draft":
        raise HTTPException(400, "Seule une écriture brouillon peut être postée")
    _validate_entry_balance(entry["lines"])
    now = datetime.now(timezone.utc).isoformat()
    db.journal_entries.update_one(
        {"id": entry_id, "organization_id": current_user.organization_id},
        {"$set": {"status": "posted", "posted_at": now}})
    return db.journal_entries.find_one(
        {"id": entry_id, "organization_id": current_user.organization_id}, {"_id": 0})


@app.post("/api/ledger/entries/{entry_id}/reverse", status_code=201)
def reverse_entry(
    entry_id: str,
    body: dict,
    current_user: CurrentUser = Depends(require_permission("accounting:write")),
):
    entry = db.journal_entries.find_one({
        "id": entry_id, "organization_id": current_user.organization_id,
    }, {"_id": 0})
    if not entry:
        raise HTTPException(404, "Écriture introuvable")
    if entry["status"] != "posted":
        raise HTTPException(400, "Seule une écriture postée peut être contre-passée")
    if entry.get("reversed_by_entry_id"):
        # Déjà contre-passée : empêche la double contre-passation (§5.3).
        raise HTTPException(400, "Écriture déjà contre-passée")
    # Miroir exact : débits ↔ crédits inversés, ligne par ligne.
    mirror_lines = [
        {"account_id": ln["account_id"], "debit": ln["credit"], "credit": ln["debit"],
         "line_description": ln.get("line_description")}
        for ln in entry["lines"]
    ]
    rev_date = body.get("entry_date") or datetime.now(timezone.utc).date().isoformat()
    rev_desc = body.get("description") or f"Contre-passation de {entry['entry_number']}"
    # Le miroir est une NOUVELLE écriture 'posted'. L'origine reste 'posted'.
    # Les deux comptent dans _account_balance → net zéro automatique (§5.2/§5.3).
    reversal = _create_journal_entry(
        current_user.organization_id, current_user.id,
        entry_date=rev_date, description=rev_desc, lines=mirror_lines,
        status="posted", entry_type="reversal", reverses_entry_id=entry_id)
    # On pose UNIQUEMENT le lien d'audit sur l'origine. On NE change PAS son status
    # (surtout pas vers un 'reversed' qui l'exclurait du solde → double effet, bug).
    db.journal_entries.update_one(
        {"id": entry_id, "organization_id": current_user.organization_id},
        {"$set": {"reversed_by_entry_id": reversal["id"]}})
    return reversal


@app.delete("/api/ledger/entries/{entry_id}", status_code=204)
def delete_entry(
    entry_id: str,
    current_user: CurrentUser = Depends(require_permission("accounting:write")),
):
    entry = db.journal_entries.find_one({
        "id": entry_id, "organization_id": current_user.organization_id,
    }, {"_id": 0})
    if not entry:
        raise HTTPException(404, "Écriture introuvable")
    if entry["status"] == "posted":
        raise HTTPException(400, "Écriture figée — seuls les brouillons sont supprimables")
    db.journal_entries.delete_one(
        {"id": entry_id, "organization_id": current_user.organization_id})
    return
```

- [ ] **Step 4: Tests pass**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_general_ledger_integration.py::TestJournalEntries -v 2>&1 | tail -20
```
Expected : 8 tests pass — dont `test_reverse_nets_to_zero_and_stays_balanced` (net zéro après contre-passation + balance de vérification équilibrée) et `test_reverse_twice_forbidden` (double contre-passation refusée en 400).

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_general_ledger_integration.py
git commit -m "feat(ledger): journal entries CRUD + post + immutable reversal + atomic JE numbering"
```

---

## Task 7 : Assistant bilan d'ouverture

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_general_ledger_integration.py`

- [ ] **Step 1: Écrire les tests d'ouverture**

Append à `backend/tests/test_general_ledger_integration.py` :
```python
class TestOpeningBalance:
    @pytest.fixture(autouse=True)
    def _clean_ob(self, client, owner_headers):
        """Supprime toute écriture OB existante avant chaque test (isolation)."""
        server_module.db.journal_entries.delete_many({
            "organization_id": self._org_id(client, owner_headers),
            "entry_type": "opening",
        })
        server_module.db.company_settings.update_many(
            {}, {"$unset": {"ledger_start_date": ""}})
        yield

    def _org_id(self, client, owner_headers):
        return client.get("/api/org/me", headers=owner_headers).json()["organization"]["id"]

    def _accounts(self, client, owner_headers):
        accounts = client.get("/api/ledger/accounts", headers=owner_headers).json()
        return {a["account_number"]: a for a in accounts}

    def test_post_balanced_creates_ob(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        r = client.post("/api/ledger/opening-balance", headers=owner_headers, json={
            "opening_date": "2026-01-01",
            "balances": [
                {"account_id": by_num["1000"]["id"], "debit": 5000.0, "credit": 0},
                {"account_id": by_num["3200"]["id"], "debit": 0, "credit": 5000.0},
            ],
        })
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["entry_number"] == "OB-0001"
        assert body["entry_type"] == "opening"
        assert body["status"] == "posted"
        # ledger_start_date posée
        g = client.get("/api/ledger/opening-balance", headers=owner_headers).json()
        assert g["exists"] is True
        assert g["opening_date"] == "2026-01-01"

    def test_post_unbalanced_400(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        r = client.post("/api/ledger/opening-balance", headers=owner_headers, json={
            "opening_date": "2026-01-01",
            "balances": [
                {"account_id": by_num["1000"]["id"], "debit": 5000.0, "credit": 0},
                {"account_id": by_num["3200"]["id"], "debit": 0, "credit": 4000.0},
            ],
        })
        assert r.status_code == 400

    def test_second_post_409(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        payload = {
            "opening_date": "2026-01-01",
            "balances": [
                {"account_id": by_num["1000"]["id"], "debit": 5000.0, "credit": 0},
                {"account_id": by_num["3200"]["id"], "debit": 0, "credit": 5000.0},
            ],
        }
        r1 = client.post("/api/ledger/opening-balance", headers=owner_headers, json=payload)
        assert r1.status_code == 201
        r2 = client.post("/api/ledger/opening-balance", headers=owner_headers, json=payload)
        assert r2.status_code == 409

    def test_put_replaces(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        client.post("/api/ledger/opening-balance", headers=owner_headers, json={
            "opening_date": "2026-01-01",
            "balances": [
                {"account_id": by_num["1000"]["id"], "debit": 5000.0, "credit": 0},
                {"account_id": by_num["3200"]["id"], "debit": 0, "credit": 5000.0},
            ],
        })
        r = client.put("/api/ledger/opening-balance", headers=owner_headers, json={
            "opening_date": "2026-01-01",
            "balances": [
                {"account_id": by_num["1000"]["id"], "debit": 8000.0, "credit": 0},
                {"account_id": by_num["3200"]["id"], "debit": 0, "credit": 8000.0},
            ],
        })
        assert r.status_code == 200
        assert r.json()["total_debit"] == 8000.0
```

- [ ] **Step 2: Verify failure**

```bash
pytest tests/test_general_ledger_integration.py::TestOpeningBalance -v 2>&1 | tail -15
```

- [ ] **Step 3: Implémenter les endpoints ouverture**

Dans `backend/server.py`, section endpoints GL, AJOUTER après les endpoints journal :

```python
@app.get("/api/ledger/opening-balance")
def get_opening_balance(
    current_user: CurrentUser = Depends(require_permission("accounting:read")),
):
    entry = db.journal_entries.find_one({
        "organization_id": current_user.organization_id, "entry_type": "opening",
    }, {"_id": 0})
    settings = db.company_settings.find_one(
        {"organization_id": current_user.organization_id}, {"_id": 0}) or {}
    return {
        "exists": entry is not None,
        "opening_date": settings.get("ledger_start_date"),
        "entry": entry,
    }


@app.post("/api/ledger/opening-balance", status_code=201)
def create_opening_balance(
    body: dict,
    current_user: CurrentUser = Depends(require_permission("accounting:write")),
):
    _ensure_chart_seeded(current_user.organization_id, current_user.id)
    existing = db.journal_entries.find_one({
        "organization_id": current_user.organization_id, "entry_type": "opening",
    })
    if existing:
        raise HTTPException(409, "Bilan d'ouverture déjà saisi — modifiez-le")
    opening_date = body.get("opening_date")
    if not opening_date:
        raise HTTPException(400, "opening_date requise")
    entry = _create_journal_entry(
        current_user.organization_id, current_user.id,
        entry_date=opening_date, description="Bilan d'ouverture",
        lines=body.get("balances") or [], status="posted",
        entry_type="opening", entry_number="OB-0001")
    db.company_settings.update_one(
        {"organization_id": current_user.organization_id},
        {"$set": {"ledger_start_date": opening_date}})
    return entry


@app.put("/api/ledger/opening-balance")
def update_opening_balance(
    body: dict,
    current_user: CurrentUser = Depends(require_permission("accounting:write")),
):
    existing = db.journal_entries.find_one({
        "organization_id": current_user.organization_id, "entry_type": "opening",
    }, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Aucun bilan d'ouverture à modifier")
    opening_date = body.get("opening_date") or existing["entry_date"]
    _validate_entry_balance(body.get("balances") or [])
    enriched = _snapshot_lines(current_user.organization_id, body.get("balances") or [])
    db.journal_entries.update_one(
        {"id": existing["id"], "organization_id": current_user.organization_id},
        {"$set": {
            "entry_date": opening_date,
            "lines": enriched,
            "total_debit": round(sum(l["debit"] for l in enriched), 2),
            "total_credit": round(sum(l["credit"] for l in enriched), 2),
        }})
    db.company_settings.update_one(
        {"organization_id": current_user.organization_id},
        {"$set": {"ledger_start_date": opening_date}})
    return db.journal_entries.find_one(
        {"id": existing["id"], "organization_id": current_user.organization_id},
        {"_id": 0})
```

- [ ] **Step 4: Tests pass**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_general_ledger_integration.py::TestOpeningBalance -v 2>&1 | tail -15
```
Expected : 4 tests pass.

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_general_ledger_integration.py
git commit -m "feat(ledger): opening-balance wizard (GET/POST/PUT, OB-0001, ledger_start_date)"
```

---

## Task 8 : Apport du propriétaire (formulaire guidé)

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_general_ledger_integration.py`

- [ ] **Step 1: Écrire les tests apport**

Append à `backend/tests/test_general_ledger_integration.py` :
```python
class TestOwnerContribution:
    def _accounts(self, client, owner_headers):
        accounts = client.get("/api/ledger/accounts", headers=owner_headers).json()
        return {a["account_number"]: a for a in accounts}

    def test_contribution_creates_dr_cash_cr_equity(self, client, owner_headers):
        r = client.post("/api/ledger/owner-contribution", headers=owner_headers, json={
            "amount": 5000.0, "date": "2026-06-20",
        })
        assert r.status_code == 201, r.text
        body = r.json()
        by_line = {l["account_number"]: l for l in body["lines"]}
        assert by_line["1000"]["debit"] == 5000.0   # Encaisse débitée
        assert by_line["3100"]["credit"] == 5000.0  # Apport crédité
        assert body["status"] == "posted"
        # reverse pour ne pas polluer les soldes des autres tests
        client.post(f"/api/ledger/entries/{body['id']}/reverse",
                    headers=owner_headers, json={})

    def test_amount_zero_400(self, client, owner_headers):
        r = client.post("/api/ledger/owner-contribution", headers=owner_headers, json={
            "amount": 0, "date": "2026-06-20",
        })
        assert r.status_code == 400

    def test_negative_amount_400(self, client, owner_headers):
        r = client.post("/api/ledger/owner-contribution", headers=owner_headers, json={
            "amount": -100.0, "date": "2026-06-20",
        })
        assert r.status_code == 400
```

- [ ] **Step 2: Verify failure**

```bash
pytest tests/test_general_ledger_integration.py::TestOwnerContribution -v 2>&1 | tail -12
```

- [ ] **Step 3: Implémenter l'endpoint apport**

Dans `backend/server.py`, section endpoints GL, AJOUTER :

```python
@app.post("/api/ledger/owner-contribution", status_code=201)
def owner_contribution(
    body: dict,
    current_user: CurrentUser = Depends(require_permission("accounting:write")),
):
    _ensure_chart_seeded(current_user.organization_id, current_user.id)
    try:
        amount = round(float(body.get("amount", 0) or 0), 2)
    except (TypeError, ValueError):
        raise HTTPException(400, "Montant invalide")
    if amount <= 0:
        raise HTTPException(400, "Le montant doit être supérieur à 0")

    def _resolve(default_number, override_id):
        if override_id:
            acc = db.chart_of_accounts.find_one({
                "id": override_id, "organization_id": current_user.organization_id,
                "is_active": True}, {"_id": 0})
            if not acc:
                raise HTTPException(400, "Compte spécifié introuvable ou inactif")
            return acc
        acc = db.chart_of_accounts.find_one({
            "organization_id": current_user.organization_id,
            "account_number": default_number, "is_active": True}, {"_id": 0})
        if not acc:
            raise HTTPException(400, f"Compte par défaut {default_number} introuvable")
        return acc

    cash = _resolve("1000", body.get("cash_account_id"))
    equity = _resolve("3100", body.get("equity_account_id"))
    description = (body.get("description") or "").strip() or "Apport du propriétaire"
    return _create_journal_entry(
        current_user.organization_id, current_user.id,
        entry_date=body.get("date"), description=description,
        lines=[
            {"account_id": cash["id"], "debit": amount, "credit": 0},
            {"account_id": equity["id"], "debit": 0, "credit": amount},
        ],
        status="posted", entry_type="manual")
```

- [ ] **Step 4: Tests pass**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_general_ledger_integration.py::TestOwnerContribution -v 2>&1 | tail -12
```
Expected : 3 tests pass.

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_general_ledger_integration.py
git commit -m "feat(ledger): owner-contribution guided form (Dr 1000 / Cr 3100)"
```

---

## Task 9 : Balance de vérification

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_general_ledger.py` + `backend/tests/test_general_ledger_integration.py`

- [ ] **Step 1: Écrire un test unitaire de la formule + un test d'intégration**

Append à `backend/tests/test_general_ledger_integration.py` :
```python
class TestTrialBalance:
    def _accounts(self, client, owner_headers):
        accounts = client.get("/api/ledger/accounts", headers=owner_headers).json()
        return {a["account_number"]: a for a in accounts}

    def test_trial_balance_balanced(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        # une écriture équilibrée
        r = client.post("/api/ledger/entries", headers=owner_headers, json={
            "entry_date": "2026-05-10", "description": "TB test", "status": "posted",
            "lines": [
                {"account_id": by_num["1000"]["id"], "debit": 1200.0, "credit": 0},
                {"account_id": by_num["4000"]["id"], "debit": 0, "credit": 1200.0},
            ],
        })
        entry_id = r.json()["id"]
        try:
            tb = client.get("/api/ledger/trial-balance?as_of=2026-12-31",
                            headers=owner_headers).json()
            assert tb["balanced"] is True
            assert round(tb["total_debit"], 2) == round(tb["total_credit"], 2)
            # comptes à solde nul exclus
            for a in tb["accounts"]:
                assert (a["debit_balance"] > 0) or (a["credit_balance"] > 0)
        finally:
            client.post(f"/api/ledger/entries/{entry_id}/reverse",
                        headers=owner_headers, json={})

    def test_as_of_excludes_future_entries(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        r = client.post("/api/ledger/entries", headers=owner_headers, json={
            "entry_date": "2027-01-15", "description": "Future", "status": "posted",
            "lines": [
                {"account_id": by_num["1000"]["id"], "debit": 999.0, "credit": 0},
                {"account_id": by_num["4000"]["id"], "debit": 0, "credit": 999.0},
            ],
        })
        entry_id = r.json()["id"]
        try:
            tb = client.get("/api/ledger/trial-balance?as_of=2026-12-31",
                            headers=owner_headers).json()
            cash_row = next((a for a in tb["accounts"]
                             if a["account_number"] == "1000"), None)
            # l'écriture 2027 ne doit pas compter dans le solde au 2026-12-31
            if cash_row:
                assert cash_row["debit_balance"] < 999.0
        finally:
            client.post(f"/api/ledger/entries/{entry_id}/reverse",
                        headers=owner_headers, json={})
```

- [ ] **Step 2: Verify failure**

```bash
pytest tests/test_general_ledger_integration.py::TestTrialBalance -v 2>&1 | tail -12
```

- [ ] **Step 3: Implémenter l'endpoint balance de vérification**

Dans `backend/server.py`, section endpoints GL, AJOUTER. D'abord un helper de projection dans la section helpers :

```python
def _trial_balance_rows(organization_id: str, as_of: str = None) -> dict:
    """Construit la balance de vérification (§7.1). Chaque compte apparaît dans
    la colonne de son solde net ; comptes à solde 0 exclus."""
    # Comptes actifs + inactifs ayant des lignes
    accounts = list(db.chart_of_accounts.find(
        {"organization_id": organization_id}, {"_id": 0}))
    rows = []
    total_debit = 0.0
    total_credit = 0.0
    for acc in accounts:
        net = _account_balance(organization_id, acc["id"], acc["normal_balance"],
                               as_of_date=as_of)
        if abs(net) < 0.005:
            continue
        if acc["normal_balance"] == "debit":
            debit_balance = net if net >= 0 else 0.0
            credit_balance = -net if net < 0 else 0.0
        else:
            credit_balance = net if net >= 0 else 0.0
            debit_balance = -net if net < 0 else 0.0
        total_debit += debit_balance
        total_credit += credit_balance
        rows.append({
            "account_number": acc["account_number"],
            "name": acc["name"],
            "account_type": acc["account_type"],
            "debit_balance": round(debit_balance, 2),
            "credit_balance": round(credit_balance, 2),
        })
    rows.sort(key=lambda r: r["account_number"])
    total_debit = round(total_debit, 2)
    total_credit = round(total_credit, 2)
    return {
        "as_of": as_of,
        "accounts": rows,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "balanced": abs(total_debit - total_credit) <= 0.01,
    }


@app.get("/api/ledger/trial-balance")
def trial_balance(
    as_of: str = None,
    current_user: CurrentUser = Depends(require_permission("accounting:read")),
):
    _ensure_chart_seeded(current_user.organization_id, current_user.id)
    if not as_of:
        as_of = datetime.now(timezone.utc).date().isoformat()
    return _trial_balance_rows(current_user.organization_id, as_of)
```

- [ ] **Step 4: Tests pass**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_general_ledger_integration.py::TestTrialBalance -v 2>&1 | tail -12
```
Expected : 2 tests pass.

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_general_ledger_integration.py
git commit -m "feat(ledger): trial-balance endpoint (net per normal_balance, balanced invariant)"
```

---

## Task 10 : Bilan (état de la situation financière)

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_general_ledger.py` + `backend/tests/test_general_ledger_integration.py`

- [ ] **Step 1: Écrire les tests fiscal year (unitaire) + bilan (intégration)**

Append à `backend/tests/test_general_ledger.py` :
```python
from server import _current_fiscal_year
from datetime import date


class TestCurrentFiscalYear:
    def test_dec_31_year_end(self):
        fy_start, fy_end = _current_fiscal_year(date(2026, 6, 15), 12, 31)
        assert fy_start == date(2026, 1, 1)
        assert fy_end == date(2026, 12, 31)

    def test_march_31_year_end(self):
        # as_of après le 31 mars → exercice se termine 31 mars de l'année suivante
        fy_start, fy_end = _current_fiscal_year(date(2026, 6, 15), 3, 31)
        assert fy_end == date(2027, 3, 31)
        assert fy_start == date(2026, 4, 1)

    def test_march_31_before_year_end(self):
        fy_start, fy_end = _current_fiscal_year(date(2026, 2, 10), 3, 31)
        assert fy_end == date(2026, 3, 31)
        assert fy_start == date(2025, 4, 1)
```

Append à `backend/tests/test_general_ledger_integration.py` :
```python
class TestBalanceSheet:
    def _accounts(self, client, owner_headers):
        accounts = client.get("/api/ledger/accounts", headers=owner_headers).json()
        return {a["account_number"]: a for a in accounts}

    def test_balance_sheet_balanced_after_contribution(self, client, owner_headers):
        # apport 4000 : Dr Encaisse (actif) / Cr Apport (CP) → Actif = CP
        r = client.post("/api/ledger/owner-contribution", headers=owner_headers, json={
            "amount": 4000.0, "date": "2026-03-01",
        })
        contrib_id = r.json()["id"]
        try:
            bs = client.get("/api/ledger/balance-sheet?as_of=2026-12-31",
                            headers=owner_headers).json()
            assert bs["balanced"] is True
            assert round(bs["total_assets"], 2) == round(
                bs["total_liabilities_and_equity"], 2)
        finally:
            client.post(f"/api/ledger/entries/{contrib_id}/reverse",
                        headers=owner_headers, json={})

    def test_net_income_current_year_reflected(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        # revenu 1000 : Dr Encaisse / Cr Revenus → net income +1000
        r = client.post("/api/ledger/entries", headers=owner_headers, json={
            "entry_date": "2026-04-01", "description": "Vente", "status": "posted",
            "lines": [
                {"account_id": by_num["1000"]["id"], "debit": 1000.0, "credit": 0},
                {"account_id": by_num["4000"]["id"], "debit": 0, "credit": 1000.0},
            ],
        })
        entry_id = r.json()["id"]
        try:
            bs = client.get("/api/ledger/balance-sheet?as_of=2026-12-31",
                            headers=owner_headers).json()
            assert bs["equity"]["net_income_current_year"] >= 1000.0
            assert bs["balanced"] is True
        finally:
            client.post(f"/api/ledger/entries/{entry_id}/reverse",
                        headers=owner_headers, json={})
```

- [ ] **Step 2: Verify failure**

```bash
pytest tests/test_general_ledger.py::TestCurrentFiscalYear -v 2>&1 | tail -8
pytest tests/test_general_ledger_integration.py::TestBalanceSheet -v 2>&1 | tail -8
```

- [ ] **Step 3: Implémenter `_current_fiscal_year` + l'endpoint bilan**

Vérifier que `relativedelta` est disponible :
```bash
grep -n "from dateutil" backend/server.py | head
python3 -c "from dateutil.relativedelta import relativedelta; print('ok')"
```
Si `dateutil` absent, ajouter `python-dateutil` à `requirements.txt` et `pip install python-dateutil`. Sinon `_current_fiscal_year` peut se passer de `relativedelta` (calcul par soustraction d'année manuelle — voir ci-dessous, version sans dépendance).

Dans `backend/server.py`, section helpers GL, AJOUTER :

```python
def _current_fiscal_year(as_of: "date", fy_end_month: int, fy_end_day: int):
    """Retourne (fy_start, fy_end) encadrant as_of (§7.2). Sans dépendance externe."""
    from datetime import date as _date, timedelta as _td
    y = as_of.year
    try:
        fy_end_this = _date(y, fy_end_month, fy_end_day)
    except ValueError:
        # ex. 31 fév. → dernier jour valide du mois ; fallback 28
        fy_end_this = _date(y, fy_end_month, 28)
    if as_of <= fy_end_this:
        fy_end = fy_end_this
    else:
        try:
            fy_end = _date(y + 1, fy_end_month, fy_end_day)
        except ValueError:
            fy_end = _date(y + 1, fy_end_month, 28)
    # début d'exercice = lendemain de la fin de l'exercice précédent
    try:
        prev_end = _date(fy_end.year - 1, fy_end_month, fy_end_day)
    except ValueError:
        prev_end = _date(fy_end.year - 1, fy_end_month, 28)
    fy_start = prev_end + _td(days=1)
    return fy_start, fy_end


@app.get("/api/ledger/balance-sheet")
def balance_sheet(
    as_of: str = None,
    current_user: CurrentUser = Depends(require_permission("accounting:read")),
):
    from datetime import date as _date
    _ensure_chart_seeded(current_user.organization_id, current_user.id)
    org_id = current_user.organization_id
    if not as_of:
        as_of = datetime.now(timezone.utc).date().isoformat()
    as_of_date = _date.fromisoformat(as_of)

    settings = db.company_settings.find_one({"organization_id": org_id}, {"_id": 0}) or {}
    fy_end_month = settings.get("fiscal_year_end_month", 12)
    fy_end_day = settings.get("fiscal_year_end_day", 31)
    fy_start, fy_end = _current_fiscal_year(as_of_date, fy_end_month, fy_end_day)
    fy_start_iso = fy_start.isoformat()

    accounts = list(db.chart_of_accounts.find({"organization_id": org_id}, {"_id": 0}))

    def _section(account_type):
        rows = []
        total = 0.0
        for acc in accounts:
            if acc["account_type"] != account_type:
                continue
            bal = _account_balance(org_id, acc["id"], acc["normal_balance"],
                                   as_of_date=as_of)
            if abs(bal) < 0.005:
                continue
            rows.append({"account_number": acc["account_number"],
                         "name": acc["name"], "balance": round(bal, 2)})
            total += bal
        rows.sort(key=lambda r: r["account_number"])
        return rows, round(total, 2)

    asset_rows, total_assets = _section("asset")
    liability_rows, total_liabilities = _section("liability")
    equity_rows, equity_accounts_total = _section("equity")

    # Résultat net de l'exercice = revenus - dépenses sur [fy_start, as_of]
    revenue_total = 0.0
    expense_total = 0.0
    for acc in accounts:
        if acc["account_type"] == "revenue":
            revenue_total += _account_balance(org_id, acc["id"], "credit",
                                              start_date=fy_start_iso, as_of_date=as_of)
        elif acc["account_type"] == "expense":
            expense_total += _account_balance(org_id, acc["id"], "debit",
                                              start_date=fy_start_iso, as_of_date=as_of)
    net_income = round(revenue_total - expense_total, 2)
    total_equity = round(equity_accounts_total + net_income, 2)
    total_liab_and_equity = round(total_liabilities + total_equity, 2)

    return {
        "as_of": as_of,
        "fiscal_year_start": fy_start_iso,
        "fiscal_year_end": fy_end.isoformat(),
        "assets": {"accounts": asset_rows, "total": total_assets},
        "liabilities": {"accounts": liability_rows, "total": total_liabilities},
        "equity": {
            "accounts": equity_rows,
            "net_income_current_year": net_income,
            "total": total_equity,
        },
        "total_assets": total_assets,
        "total_liabilities_and_equity": total_liab_and_equity,
        "balanced": abs(total_assets - total_liab_and_equity) <= 0.01,
    }
```

- [ ] **Step 4: Tests pass**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_general_ledger.py::TestCurrentFiscalYear tests/test_general_ledger_integration.py::TestBalanceSheet -v 2>&1 | tail -15
```
Expected : 3 + 2 = 5 tests pass.

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_general_ledger.py backend/tests/test_general_ledger_integration.py
git commit -m "feat(ledger): balance-sheet endpoint + _current_fiscal_year (net income derived)"
```

---

## Task 11 : Grand livre par compte

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_general_ledger_integration.py`

- [ ] **Step 1: Écrire les tests grand livre**

Append à `backend/tests/test_general_ledger_integration.py` :
```python
class TestGeneralLedgerDetail:
    def _accounts(self, client, owner_headers):
        accounts = client.get("/api/ledger/accounts", headers=owner_headers).json()
        return {a["account_number"]: a for a in accounts}

    def test_running_balance_progression(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        cash_id = by_num["1000"]["id"]
        ids = []
        for amt, day in [(100.0, "05"), (250.0, "12")]:
            r = client.post("/api/ledger/entries", headers=owner_headers, json={
                "entry_date": f"2026-07-{day}", "description": f"Mvt {amt}",
                "status": "posted",
                "lines": [
                    {"account_id": cash_id, "debit": amt, "credit": 0},
                    {"account_id": by_num["4000"]["id"], "debit": 0, "credit": amt},
                ],
            })
            ids.append(r.json()["id"])
        try:
            gl = client.get(
                f"/api/ledger/general-ledger?account_id={cash_id}"
                f"&start=2026-07-01&end=2026-07-31", headers=owner_headers).json()
            assert gl["account"]["account_number"] == "1000"
            balances = [ln["running_balance"] for ln in gl["lines"]]
            # solde progressif croissant sur ces 2 débits
            assert balances == sorted(balances)
            assert gl["closing_balance"] >= gl["opening_balance"]
        finally:
            for eid in ids:
                client.post(f"/api/ledger/entries/{eid}/reverse",
                            headers=owner_headers, json={})

    def test_unknown_account_404(self, client, owner_headers):
        r = client.get(f"/api/ledger/general-ledger?account_id={uuid.uuid4()}",
                       headers=owner_headers)
        assert r.status_code == 404
```

- [ ] **Step 2: Verify failure**

```bash
pytest tests/test_general_ledger_integration.py::TestGeneralLedgerDetail -v 2>&1 | tail -12
```

- [ ] **Step 3: Implémenter l'endpoint grand livre**

Dans `backend/server.py`, section endpoints GL, AJOUTER :

```python
@app.get("/api/ledger/general-ledger")
def general_ledger(
    account_id: str,
    start: str = None, end: str = None,
    current_user: CurrentUser = Depends(require_permission("accounting:read")),
):
    org_id = current_user.organization_id
    acc = db.chart_of_accounts.find_one({
        "id": account_id, "organization_id": org_id}, {"_id": 0})
    if not acc:
        raise HTTPException(404, "Compte introuvable")
    normal = acc["normal_balance"]

    # Solde d'ouverture = solde avant `start`
    opening_balance = 0.0
    if start:
        from datetime import date as _date, timedelta as _td
        day_before = (_date.fromisoformat(start) - _td(days=1)).isoformat()
        opening_balance = _account_balance(org_id, account_id, normal,
                                           as_of_date=day_before)

    match = {"organization_id": org_id, "status": "posted",
             "lines.account_id": account_id}
    if start or end:
        df = {}
        if start:
            df["$gte"] = start
        if end:
            df["$lte"] = end
        match["entry_date"] = df
    entries = list(db.journal_entries.find(match, {"_id": 0})
                   .sort([("entry_date", 1), ("entry_number", 1)]))

    running = opening_balance
    lines = []
    for entry in entries:
        for ln in entry["lines"]:
            if ln["account_id"] != account_id:
                continue
            debit = float(ln.get("debit", 0) or 0)
            credit = float(ln.get("credit", 0) or 0)
            if normal == "debit":
                running += debit - credit
            else:
                running += credit - debit
            lines.append({
                "entry_id": entry["id"],
                "entry_number": entry["entry_number"],
                "entry_date": entry["entry_date"],
                "description": entry["description"],
                "reference": entry.get("reference"),
                "debit": round(debit, 2),
                "credit": round(credit, 2),
                "running_balance": round(running, 2),
            })
    return {
        "account": {
            "id": acc["id"], "account_number": acc["account_number"],
            "name": acc["name"], "account_type": acc["account_type"],
            "normal_balance": normal,
        },
        "opening_balance": round(opening_balance, 2),
        "lines": lines,
        "closing_balance": round(running, 2),
    }
```

- [ ] **Step 4: Tests pass**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_general_ledger_integration.py::TestGeneralLedgerDetail -v 2>&1 | tail -12
```
Expected : 2 tests pass.

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_general_ledger_integration.py
git commit -m "feat(ledger): general-ledger per-account detail with running balance"
```

---

## Task 12 : PDF balance de vérification + bilan (FR-CA)

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_general_ledger_integration.py`

- [ ] **Step 1: Écrire les tests PDF**

Append à `backend/tests/test_general_ledger_integration.py` :
```python
class TestLedgerPDF:
    def test_trial_balance_pdf(self, client, owner_headers):
        r = client.get("/api/ledger/trial-balance/pdf?as_of=2026-12-31",
                       headers=owner_headers)
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf"
        assert "no-store" in r.headers.get("cache-control", "")
        assert r.content[:4] == b"%PDF"

    def test_balance_sheet_pdf(self, client, owner_headers):
        r = client.get("/api/ledger/balance-sheet/pdf?as_of=2026-12-31",
                       headers=owner_headers)
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf"
        assert r.content[:4] == b"%PDF"
```

- [ ] **Step 2: Verify failure**

```bash
pytest tests/test_general_ledger_integration.py::TestLedgerPDF -v 2>&1 | tail -10
```

- [ ] **Step 3: Implémenter les 2 PDF**

Réutiliser `_t2125_format_money` (`server.py:5352`) et le pattern `Response` no-cache (`server.py:5548`). Dans `backend/server.py`, section endpoints GL, AJOUTER un helper commun + les 2 endpoints :

```python
def _ledger_pdf_money(value):
    """Format FR-CA (réutilise le formatteur T2125)."""
    return _t2125_format_money(value)


def _render_ledger_table_pdf(title, subtitle, sections, org_id):
    """Génère un PDF FR-CA générique (balance de vérification ou bilan).
    sections = liste de (titre_section, [(label, montant_str, is_total_bool), ...])."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from html import escape as html_escape

    teal = HexColor("#008F7A")
    dark = HexColor("#1f2937")
    gray = HexColor("#6b7280")

    settings = db.company_settings.find_one({"organization_id": org_id}, {"_id": 0}) or {}
    company_name = html_escape(settings.get("company_name") or "(sans nom)")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            topMargin=0.6*inch, bottomMargin=0.6*inch,
                            leftMargin=0.6*inch, rightMargin=0.6*inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("T", parent=styles["Heading1"], fontSize=18,
                                 textColor=teal, spaceAfter=4)
    h2_style = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12,
                              textColor=dark, spaceBefore=10, spaceAfter=4)
    small_style = ParagraphStyle("S", parent=styles["Normal"], fontSize=9,
                                 textColor=gray, leading=11)

    elements = [Paragraph(html_escape(title), title_style),
                Paragraph(f"<b>{company_name}</b> &nbsp;·&nbsp; {html_escape(subtitle)}",
                          small_style),
                Paragraph(
                    f"Généré le {datetime.now(timezone.utc).strftime('%Y-%m-%d à %H:%M UTC')} "
                    "— État non audité, usage interne", small_style),
                Spacer(1, 0.2*inch)]

    for section_title, rows in sections:
        if section_title:
            elements.append(Paragraph(html_escape(section_title), h2_style))
        table_data = [[html_escape(str(label)), amount_str] for (label, amount_str, _) in rows]
        if not table_data:
            table_data = [["(aucun)", ""]]
        t = Table(table_data, colWidths=[5.0*inch, 2.0*inch])
        style = [
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("TEXTCOLOR", (0, 0), (-1, -1), dark),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, HexColor("#e5e7eb")),
        ]
        for i, (_, _, is_total) in enumerate(rows):
            if is_total:
                style.append(("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"))
                style.append(("LINEABOVE", (0, i), (-1, i), 0.75, dark))
        t.setStyle(TableStyle(style))
        elements.append(t)

    doc.build(elements)
    buf.seek(0)
    return buf.read()


@app.get("/api/ledger/trial-balance/pdf")
def trial_balance_pdf(
    as_of: str = None,
    current_user: CurrentUser = Depends(require_permission("accounting:read")),
):
    from fastapi import Response
    _ensure_chart_seeded(current_user.organization_id, current_user.id)
    if not as_of:
        as_of = datetime.now(timezone.utc).date().isoformat()
    tb = _trial_balance_rows(current_user.organization_id, as_of)
    rows = []
    for a in tb["accounts"]:
        amount = a["debit_balance"] if a["debit_balance"] > 0 else -a["credit_balance"]
        side = "Dr" if a["debit_balance"] > 0 else "Cr"
        rows.append((f"{a['account_number']} — {a['name']} ({side})",
                     _ledger_pdf_money(abs(amount)), False))
    rows.append(("Total débits", _ledger_pdf_money(tb["total_debit"]), True))
    rows.append(("Total crédits", _ledger_pdf_money(tb["total_credit"]), True))
    equilibre = "équilibrée" if tb["balanced"] else "DÉSÉQUILIBRÉE"
    pdf = _render_ledger_table_pdf(
        "Balance de vérification", f"Au {as_of} — Balance {equilibre}",
        [(None, rows)], current_user.organization_id)
    return Response(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="balance-verification-{as_of}.pdf"',
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    })


@app.get("/api/ledger/balance-sheet/pdf")
def balance_sheet_pdf(
    as_of: str = None,
    current_user: CurrentUser = Depends(require_permission("accounting:read")),
):
    from fastapi import Response
    _ensure_chart_seeded(current_user.organization_id, current_user.id)
    if not as_of:
        as_of = datetime.now(timezone.utc).date().isoformat()
    bs = balance_sheet(as_of=as_of, current_user=current_user)

    asset_rows = [(f"{a['account_number']} — {a['name']}",
                   _ledger_pdf_money(a["balance"]), False)
                  for a in bs["assets"]["accounts"]]
    asset_rows.append(("Total de l'actif", _ledger_pdf_money(bs["total_assets"]), True))

    liab_rows = [(f"{a['account_number']} — {a['name']}",
                  _ledger_pdf_money(a["balance"]), False)
                 for a in bs["liabilities"]["accounts"]]
    liab_rows.append(("Total du passif",
                      _ledger_pdf_money(bs["liabilities"]["total"]), True))

    equity_rows = [(f"{a['account_number']} — {a['name']}",
                    _ledger_pdf_money(a["balance"]), False)
                   for a in bs["equity"]["accounts"]]
    equity_rows.append(("Résultat net de l'exercice",
                        _ledger_pdf_money(bs["equity"]["net_income_current_year"]), False))
    equity_rows.append(("Total des capitaux propres",
                        _ledger_pdf_money(bs["equity"]["total"]), True))
    equity_rows.append(("Total passif + capitaux propres",
                        _ledger_pdf_money(bs["total_liabilities_and_equity"]), True))

    equilibre = "équilibré" if bs["balanced"] else "DÉSÉQUILIBRÉ"
    pdf = _render_ledger_table_pdf(
        "Bilan — État de la situation financière",
        f"Au {as_of} — Bilan {equilibre}",
        [("Actif", asset_rows), ("Passif", liab_rows),
         ("Capitaux propres", equity_rows)],
        current_user.organization_id)
    from fastapi import Response as _Resp
    return _Resp(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="bilan-{as_of}.pdf"',
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    })
```

- [ ] **Step 4: Tests pass**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_general_ledger_integration.py::TestLedgerPDF -v 2>&1 | tail -10
```
Expected : 2 tests pass.

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_general_ledger_integration.py
git commit -m "feat(ledger): trial-balance + balance-sheet PDF (FR-CA, no-cache)"
```

---

## Task 13 : Frontend — sidebar « Grand livre » + route guard

**Files:**
- Modify: `frontend/src/components/Layout.js`
- Modify: `frontend/src/App.js`
- Create: `frontend/src/pages/LedgerPage.js` (stub)

- [ ] **Step 1: Repérer le pattern de la sidebar + RouteGuard**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
grep -n "hasPermission\|RouteGuard\|BookOpen\|import.*lucide-react\|navItems\|sidebar" frontend/src/components/Layout.js | head -20
grep -n "RouteGuard\|/ledger\|'/reports'\|pathname" frontend/src/App.js | head -20
```
Récupérer : comment les entrées de nav sont déclarées (label + path + icône + permission), comment `RouteGuard` wrappe une route dans `App.js`, et le pattern de rendu par `window.location.pathname`.

- [ ] **Step 2: Créer le stub `LedgerPage.js`**

`frontend/src/pages/LedgerPage.js` :
```jsx
import React, { useState } from 'react';

const TABS = [
  { key: 'accounts', label: 'Plan comptable' },
  { key: 'journal', label: 'Journal' },
  { key: 'opening', label: 'Bilan d\'ouverture' },
  { key: 'contribution', label: 'Apport' },
  { key: 'ledger', label: 'Grand livre' },
  { key: 'trial', label: 'Balance de vérification' },
  { key: 'balancesheet', label: 'Bilan' },
];

export default function LedgerPage() {
  const [tab, setTab] = useState('accounts');
  return (
    <div style={{ padding: 24 }}>
      <h1 style={{ fontSize: 24, marginBottom: 16 }}>Grand livre</h1>
      <div style={{ display: 'flex', gap: 8, borderBottom: '1px solid #e5e7eb', marginBottom: 24, flexWrap: 'wrap' }}>
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} style={{
            background: 'none', border: 'none', padding: '10px 14px', cursor: 'pointer',
            fontSize: 14, fontWeight: tab === t.key ? 700 : 500,
            color: tab === t.key ? '#00A08C' : '#6b7280',
            borderBottom: tab === t.key ? '2px solid #00A08C' : '2px solid transparent',
          }}>
            {t.label}
          </button>
        ))}
      </div>
      <div>{/* Onglets remplis aux Tasks 14-17 */}
        {tab === 'accounts' && <div>Plan comptable (à venir)</div>}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Ajouter l'entrée sidebar gatée `accounting:read`**

Dans `frontend/src/components/Layout.js`, importer l'icône :
```jsx
import { BookOpen } from 'lucide-react';
```
Ajouter l'entrée à la liste de nav (calquer la forme exacte des entrées voisines, ex. Rapports). Elle doit être filtrée par `hasPermission('accounting:read')` comme le sont les autres. Exemple à adapter :
```jsx
{ label: 'Grand livre', path: '/ledger', icon: BookOpen, permission: 'accounting:read' },
```

- [ ] **Step 4: Router `/ledger` protégé dans App.js**

Dans `frontend/src/App.js`, importer et brancher la route avec `RouteGuard` (calquer la route `/reports`) :
```jsx
import LedgerPage from './pages/LedgerPage';
```
```jsx
if (path === '/ledger') {
  return <RouteGuard permission="accounting:read"><LedgerPage /></RouteGuard>;
}
```
Adapter à la mécanique exacte de routing (le repo navigue via `window.history`, pas de router lib — cf. CLAUDE.md).

- [ ] **Step 5: Sanity parse**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
node -e "require('@babel/parser').parse(require('fs').readFileSync('src/pages/LedgerPage.js','utf8'), {sourceType:'module', plugins:['jsx']}); console.log('OK LedgerPage')"
node -e "require('@babel/parser').parse(require('fs').readFileSync('src/components/Layout.js','utf8'), {sourceType:'module', plugins:['jsx']}); console.log('OK Layout')"
node -e "require('@babel/parser').parse(require('fs').readFileSync('src/App.js','utf8'), {sourceType:'module', plugins:['jsx']}); console.log('OK App')"
```

- [ ] **Step 6: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add frontend/src/pages/LedgerPage.js frontend/src/components/Layout.js frontend/src/App.js
git commit -m "feat(ledger): sidebar entry + /ledger route guard + LedgerPage tab shell"
```

---

## Task 14 : Page Plan comptable (liste + CRUD)

**Files:**
- Modify: `frontend/src/pages/LedgerPage.js`

- [ ] **Step 1: Implémenter l'onglet Plan comptable**

Dans `frontend/src/pages/LedgerPage.js`, ajouter les imports en tête :
```jsx
import axios from 'axios';
import { useEffect } from 'react';
import { BACKEND_URL } from '../config';
import { useAuth } from '../context/AuthContext';
```
Puis un composant `AccountsTab` (dans le même fichier) :
```jsx
function AccountsTab() {
  const { hasPermission } = useAuth();
  const canWrite = hasPermission('accounting:write');
  const [accounts, setAccounts] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ account_number: '', name: '', sub_type: '' });
  const [error, setError] = useState(null);

  const load = () => {
    axios.get(`${BACKEND_URL}/api/ledger/accounts`)
      .then(r => setAccounts(r.data)).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  const create = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      await axios.post(`${BACKEND_URL}/api/ledger/accounts`, form);
      setShowModal(false);
      setForm({ account_number: '', name: '', sub_type: '' });
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur');
    }
  };

  const remove = async (id) => {
    if (!window.confirm('Supprimer ce compte ?')) return;
    try { await axios.delete(`${BACKEND_URL}/api/ledger/accounts/${id}`); load(); }
    catch (err) { alert(err.response?.data?.detail || 'Erreur'); }
  };

  const toggleActive = async (a) => {
    try {
      await axios.put(`${BACKEND_URL}/api/ledger/accounts/${a.id}`,
                      { is_active: !a.is_active });
      load();
    } catch (err) { alert(err.response?.data?.detail || 'Erreur'); }
  };

  const TYPE_FR = { asset: 'Actif', liability: 'Passif', equity: 'Capitaux propres',
                    revenue: 'Revenus', expense: 'Dépenses' };

  return (
    <div>
      {canWrite && (
        <button onClick={() => setShowModal(true)} style={{
          background: '#00A08C', color: '#fff', border: 'none', padding: '8px 16px',
          borderRadius: 6, cursor: 'pointer', marginBottom: 16, fontWeight: 600,
        }}>+ Nouveau compte</button>
      )}
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
        <thead>
          <tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
            <th style={{ padding: 8 }}>Numéro</th>
            <th style={{ padding: 8 }}>Nom</th>
            <th style={{ padding: 8 }}>Type</th>
            <th style={{ padding: 8 }}>Solde normal</th>
            <th style={{ padding: 8 }}>Actif</th>
            {canWrite && <th style={{ padding: 8 }}></th>}
          </tr>
        </thead>
        <tbody>
          {accounts.map(a => (
            <tr key={a.id} style={{ borderBottom: '1px solid #f3f4f6',
                                    opacity: a.is_active ? 1 : 0.5 }}>
              <td style={{ padding: 8, fontFamily: 'monospace' }}>{a.account_number}</td>
              <td style={{ padding: 8 }}>{a.name}</td>
              <td style={{ padding: 8 }}>{TYPE_FR[a.account_type]}</td>
              <td style={{ padding: 8 }}>{a.normal_balance === 'debit' ? 'Débit' : 'Crédit'}</td>
              <td style={{ padding: 8 }}>{a.is_active ? 'Oui' : 'Non'}</td>
              {canWrite && (
                <td style={{ padding: 8 }}>
                  <button onClick={() => toggleActive(a)} style={{ marginRight: 8,
                    background: 'none', border: '1px solid #d1d5db', borderRadius: 4,
                    padding: '2px 8px', cursor: 'pointer', fontSize: 12 }}>
                    {a.is_active ? 'Désactiver' : 'Activer'}
                  </button>
                  {!a.is_system && (
                    <button onClick={() => remove(a.id)} style={{
                      background: 'none', border: '1px solid #fca5a5', color: '#991b1b',
                      borderRadius: 4, padding: '2px 8px', cursor: 'pointer', fontSize: 12 }}>
                      Suppr.
                    </button>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>

      {showModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
          display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 }}>
          <form onSubmit={create} style={{ background: '#fff', borderRadius: 8,
            padding: 24, width: 420, maxWidth: '90vw' }}>
            <h2 style={{ marginTop: 0 }}>Nouveau compte</h2>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
              Numéro (1000-5999)</label>
            <input required value={form.account_number}
                   onChange={e => setForm({ ...form, account_number: e.target.value })}
                   placeholder="1500"
                   style={{ width: '100%', padding: 8, marginBottom: 12,
                            border: '1px solid #d1d5db', borderRadius: 6, boxSizing: 'border-box' }} />
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
              Nom</label>
            <input required value={form.name}
                   onChange={e => setForm({ ...form, name: e.target.value })}
                   style={{ width: '100%', padding: 8, marginBottom: 12,
                            border: '1px solid #d1d5db', borderRadius: 6, boxSizing: 'border-box' }} />
            {error && <div style={{ color: '#991b1b', fontSize: 13, marginBottom: 12 }}>{error}</div>}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button type="button" onClick={() => setShowModal(false)} style={{
                background: '#fff', border: '1px solid #d1d5db', padding: '8px 16px',
                borderRadius: 6, cursor: 'pointer' }}>Annuler</button>
              <button type="submit" style={{ background: '#00A08C', color: '#fff',
                border: 'none', padding: '8px 16px', borderRadius: 6, cursor: 'pointer',
                fontWeight: 600 }}>Créer</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
```
Brancher dans le rendu des onglets : `{tab === 'accounts' && <AccountsTab />}`.

- [ ] **Step 2: Sanity parse**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
node -e "require('@babel/parser').parse(require('fs').readFileSync('src/pages/LedgerPage.js','utf8'), {sourceType:'module', plugins:['jsx']}); console.log('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add frontend/src/pages/LedgerPage.js
git commit -m "feat(ledger): ChartOfAccounts tab (list + create + activate + delete)"
```

---

## Task 15 : Page Journal (liste + modal création équilibre live)

**Files:**
- Modify: `frontend/src/pages/LedgerPage.js`

- [ ] **Step 1: Implémenter l'onglet Journal**

Dans `frontend/src/pages/LedgerPage.js`, ajouter le composant `JournalTab` :
```jsx
function JournalTab() {
  const { hasPermission } = useAuth();
  const canWrite = hasPermission('accounting:write');
  const [entries, setEntries] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [entryDate, setEntryDate] = useState(new Date().toISOString().slice(0, 10));
  const [description, setDescription] = useState('');
  const [lines, setLines] = useState([
    { account_id: '', debit: '', credit: '' },
    { account_id: '', debit: '', credit: '' },
  ]);
  const [error, setError] = useState(null);

  const load = () => {
    axios.get(`${BACKEND_URL}/api/ledger/entries`).then(r => setEntries(r.data)).catch(() => {});
    axios.get(`${BACKEND_URL}/api/ledger/accounts?active=true`)
      .then(r => setAccounts(r.data)).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  const totalDebit = lines.reduce((s, l) => s + (parseFloat(l.debit) || 0), 0);
  const totalCredit = lines.reduce((s, l) => s + (parseFloat(l.credit) || 0), 0);
  const diff = Math.round((totalDebit - totalCredit) * 100) / 100;
  const balanced = Math.abs(diff) < 0.005 && totalDebit > 0;

  const setLine = (i, field, value) => {
    const next = [...lines];
    next[i] = { ...next[i], [field]: value };
    // débit et crédit mutuellement exclusifs
    if (field === 'debit' && value) next[i].credit = '';
    if (field === 'credit' && value) next[i].debit = '';
    setLines(next);
  };
  const addLine = () => setLines([...lines, { account_id: '', debit: '', credit: '' }]);

  const submit = async (status) => {
    setError(null);
    try {
      await axios.post(`${BACKEND_URL}/api/ledger/entries`, {
        entry_date: entryDate, description, status,
        lines: lines.filter(l => l.account_id).map(l => ({
          account_id: l.account_id,
          debit: parseFloat(l.debit) || 0,
          credit: parseFloat(l.credit) || 0,
        })),
      });
      setShowModal(false);
      setLines([{ account_id: '', debit: '', credit: '' }, { account_id: '', debit: '', credit: '' }]);
      setDescription('');
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur');
    }
  };

  const reverse = async (id) => {
    if (!window.confirm('Contre-passer cette écriture ?')) return;
    try { await axios.post(`${BACKEND_URL}/api/ledger/entries/${id}/reverse`, {}); load(); }
    catch (err) { alert(err.response?.data?.detail || 'Erreur'); }
  };

  // Statuts d'écriture = draft | posted UNIQUEMENT (pas de 'reversed', §5.3).
  // Une écriture contre-passée reste 'posted' ; on la signale via reversed_by_entry_id.
  const STATUS_FR = { draft: 'Brouillon', posted: 'Postée' };
  const statusLabel = (e) =>
    e.reversed_by_entry_id ? 'Postée (contre-passée)'
      : e.entry_type === 'reversal' ? 'Postée (contre-passation)'
      : (STATUS_FR[e.status] || e.status);

  return (
    <div>
      {/* ⚠️ Avertissement Clôture annuelle (spec §7.2.1) — toujours visible */}
      <div style={{ background: '#FEF3C7', border: '1px solid #F59E0B',
        borderRadius: 6, padding: '10px 14px', marginBottom: 16, fontSize: 13,
        color: '#92400E' }}>
        <strong>Clôture annuelle</strong> — Le système ne clôture pas l'exercice
        automatiquement. À (ou après) la fin de votre exercice, passez une écriture
        de clôture manuelle (Dr Revenus / Cr Dépenses / vers Bénéfices non répartis 3200).
        Ne clôturez <strong>jamais en cours d'exercice</strong>. Un oubli
        <strong> déséquilibrera le bilan de l'exercice suivant</strong>.
      </div>
      {canWrite && (
        <button onClick={() => setShowModal(true)} style={{
          background: '#00A08C', color: '#fff', border: 'none', padding: '8px 16px',
          borderRadius: 6, cursor: 'pointer', marginBottom: 16, fontWeight: 600 }}>
          + Nouvelle écriture</button>
      )}
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
        <thead>
          <tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
            <th style={{ padding: 8 }}>N°</th><th style={{ padding: 8 }}>Date</th>
            <th style={{ padding: 8 }}>Description</th>
            <th style={{ padding: 8, textAlign: 'right' }}>Débit total</th>
            <th style={{ padding: 8 }}>Statut</th>
            {canWrite && <th></th>}
          </tr>
        </thead>
        <tbody>
          {entries.map(e => (
            <tr key={e.id} style={{ borderBottom: '1px solid #f3f4f6' }}>
              <td style={{ padding: 8, fontFamily: 'monospace' }}>{e.entry_number}</td>
              <td style={{ padding: 8 }}>{e.entry_date}</td>
              <td style={{ padding: 8 }}>{e.description}</td>
              <td style={{ padding: 8, textAlign: 'right' }}>{e.total_debit.toFixed(2)} $</td>
              <td style={{ padding: 8 }}>{statusLabel(e)}</td>
              {canWrite && (
                <td style={{ padding: 8 }}>
                  {/* Contre-passer seulement si postée ET pas déjà contre-passée */}
                  {e.status === 'posted' && !e.reversed_by_entry_id
                    && e.entry_type !== 'reversal' && (
                    <button onClick={() => reverse(e.id)} style={{
                      background: 'none', border: '1px solid #d1d5db', borderRadius: 4,
                      padding: '2px 8px', cursor: 'pointer', fontSize: 12 }}>
                      Contre-passer</button>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>

      {showModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
          display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 }}>
          <div style={{ background: '#fff', borderRadius: 8, padding: 24,
            width: 720, maxWidth: '95vw', maxHeight: '90vh', overflow: 'auto' }}>
            <h2 style={{ marginTop: 0 }}>Nouvelle écriture</h2>
            <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
              <input type="date" value={entryDate} onChange={e => setEntryDate(e.target.value)}
                     style={{ padding: 8, border: '1px solid #d1d5db', borderRadius: 6 }} />
              <input placeholder="Description" value={description}
                     onChange={e => setDescription(e.target.value)}
                     style={{ flex: 1, padding: 8, border: '1px solid #d1d5db', borderRadius: 6 }} />
            </div>
            <table style={{ width: '100%', fontSize: 13, marginBottom: 8 }}>
              <thead><tr><th style={{ textAlign: 'left' }}>Compte</th>
                <th>Débit</th><th>Crédit</th></tr></thead>
              <tbody>
                {lines.map((l, i) => (
                  <tr key={i}>
                    <td>
                      <select value={l.account_id}
                              onChange={e => setLine(i, 'account_id', e.target.value)}
                              style={{ width: '100%', padding: 6 }}>
                        <option value="">— compte —</option>
                        {accounts.map(a => (
                          <option key={a.id} value={a.id}>{a.account_number} — {a.name}</option>
                        ))}
                      </select>
                    </td>
                    <td><input type="number" step="0.01" value={l.debit}
                               onChange={e => setLine(i, 'debit', e.target.value)}
                               style={{ width: 100, padding: 6 }} /></td>
                    <td><input type="number" step="0.01" value={l.credit}
                               onChange={e => setLine(i, 'credit', e.target.value)}
                               style={{ width: 100, padding: 6 }} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <button onClick={addLine} style={{ background: 'none', border: '1px dashed #d1d5db',
              borderRadius: 6, padding: '4px 12px', cursor: 'pointer', fontSize: 13,
              marginBottom: 12 }}>+ Ligne</button>

            <div style={{ display: 'flex', gap: 24, padding: 12,
              background: balanced ? '#ecfdf5' : '#fef2f2', borderRadius: 6, marginBottom: 12 }}>
              <span>Total Dr : <strong>{totalDebit.toFixed(2)} $</strong></span>
              <span>Total Cr : <strong>{totalCredit.toFixed(2)} $</strong></span>
              <span>Écart : <strong style={{ color: balanced ? '#059669' : '#dc2626' }}>
                {diff.toFixed(2)} $</strong></span>
            </div>
            {error && <div style={{ color: '#991b1b', fontSize: 13, marginBottom: 12 }}>{error}</div>}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button onClick={() => setShowModal(false)} style={{ background: '#fff',
                border: '1px solid #d1d5db', padding: '8px 16px', borderRadius: 6,
                cursor: 'pointer' }}>Annuler</button>
              <button onClick={() => submit('draft')} disabled={!balanced} style={{
                background: '#6b7280', color: '#fff', border: 'none', padding: '8px 16px',
                borderRadius: 6, cursor: balanced ? 'pointer' : 'not-allowed',
                opacity: balanced ? 1 : 0.5 }}>Enregistrer brouillon</button>
              <button onClick={() => submit('posted')} disabled={!balanced} style={{
                background: '#00A08C', color: '#fff', border: 'none', padding: '8px 16px',
                borderRadius: 6, cursor: balanced ? 'pointer' : 'not-allowed',
                fontWeight: 600, opacity: balanced ? 1 : 0.5 }}>Poster</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```
Brancher : `{tab === 'journal' && <JournalTab />}`.

- [ ] **Step 2: Sanity parse**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
node -e "require('@babel/parser').parse(require('fs').readFileSync('src/pages/LedgerPage.js','utf8'), {sourceType:'module', plugins:['jsx']}); console.log('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add frontend/src/pages/LedgerPage.js
git commit -m "feat(ledger): Journal tab (list + entry editor with live balance counter)"
```

---

## Task 16 : Assistant bilan d'ouverture + bouton apport

**Files:**
- Modify: `frontend/src/pages/LedgerPage.js`

- [ ] **Step 1: Implémenter les onglets Ouverture + Apport**

Dans `frontend/src/pages/LedgerPage.js`, ajouter `OpeningTab` et `ContributionTab` :
```jsx
function OpeningTab() {
  const [accounts, setAccounts] = useState([]);
  const [openingDate, setOpeningDate] = useState('2026-01-01');
  const [balances, setBalances] = useState({}); // account_id -> {debit, credit}
  const [existing, setExisting] = useState(null);
  const [error, setError] = useState(null);
  const [ok, setOk] = useState(false);

  const load = () => {
    axios.get(`${BACKEND_URL}/api/ledger/accounts?active=true`)
      .then(r => setAccounts(r.data)).catch(() => {});
    axios.get(`${BACKEND_URL}/api/ledger/opening-balance`)
      .then(r => setExisting(r.data)).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  const set = (id, field, value) => {
    setBalances(prev => {
      const next = { ...prev, [id]: { ...(prev[id] || {}), [field]: value } };
      if (field === 'debit' && value) next[id].credit = '';
      if (field === 'credit' && value) next[id].debit = '';
      return next;
    });
  };

  const rows = Object.entries(balances)
    .map(([id, v]) => ({ account_id: id,
      debit: parseFloat(v.debit) || 0, credit: parseFloat(v.credit) || 0 }))
    .filter(r => r.debit > 0 || r.credit > 0);
  const totalDr = rows.reduce((s, r) => s + r.debit, 0);
  const totalCr = rows.reduce((s, r) => s + r.credit, 0);
  const balanced = Math.abs(totalDr - totalCr) < 0.005 && totalDr > 0;

  const submit = async () => {
    setError(null); setOk(false);
    const method = existing?.exists ? 'put' : 'post';
    try {
      await axios[method](`${BACKEND_URL}/api/ledger/opening-balance`,
        { opening_date: openingDate, balances: rows });
      setOk(true); load();
    } catch (err) { setError(err.response?.data?.detail || 'Erreur'); }
  };

  return (
    <div>
      <div style={{ background: '#eff6ff', padding: 12, borderRadius: 6, marginBottom: 16,
        fontSize: 13, color: '#1e3a8a' }}>
        Saisissez la balance de vérification d'ouverture fournie par votre comptable.
        Les débits doivent égaler les crédits.
      </div>
      {existing?.exists && (
        <div style={{ color: '#92400e', fontSize: 13, marginBottom: 12 }}>
          Un bilan d'ouverture existe déjà ({existing.opening_date}). L'enregistrement le remplacera.
        </div>
      )}
      <label style={{ fontSize: 13, fontWeight: 600 }}>Date d'ouverture{' '}
        <input type="date" value={openingDate} onChange={e => setOpeningDate(e.target.value)}
               style={{ padding: 6, border: '1px solid #d1d5db', borderRadius: 6 }} />
      </label>
      <table style={{ width: '100%', fontSize: 13, marginTop: 12 }}>
        <thead><tr style={{ textAlign: 'left', borderBottom: '2px solid #e5e7eb' }}>
          <th style={{ padding: 6 }}>Compte</th><th>Débit</th><th>Crédit</th></tr></thead>
        <tbody>
          {accounts.map(a => (
            <tr key={a.id} style={{ borderBottom: '1px solid #f3f4f6' }}>
              <td style={{ padding: 6 }}>{a.account_number} — {a.name}</td>
              <td><input type="number" step="0.01" value={balances[a.id]?.debit || ''}
                         onChange={e => set(a.id, 'debit', e.target.value)}
                         style={{ width: 100, padding: 4 }} /></td>
              <td><input type="number" step="0.01" value={balances[a.id]?.credit || ''}
                         onChange={e => set(a.id, 'credit', e.target.value)}
                         style={{ width: 100, padding: 4 }} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ display: 'flex', gap: 24, padding: 12, marginTop: 12,
        background: balanced ? '#ecfdf5' : '#fef2f2', borderRadius: 6 }}>
        <span>Total Dr : <strong>{totalDr.toFixed(2)} $</strong></span>
        <span>Total Cr : <strong>{totalCr.toFixed(2)} $</strong></span>
        <span style={{ color: balanced ? '#059669' : '#dc2626' }}>
          {balanced ? 'Équilibré' : 'Déséquilibré'}</span>
      </div>
      {error && <div style={{ color: '#991b1b', fontSize: 13, marginTop: 8 }}>{error}</div>}
      {ok && <div style={{ color: '#059669', fontSize: 13, marginTop: 8 }}>Bilan d'ouverture enregistré.</div>}
      <button onClick={submit} disabled={!balanced} style={{ marginTop: 12,
        background: '#00A08C', color: '#fff', border: 'none', padding: '10px 20px',
        borderRadius: 6, cursor: balanced ? 'pointer' : 'not-allowed', fontWeight: 600,
        opacity: balanced ? 1 : 0.5 }}>Enregistrer le bilan d'ouverture</button>
    </div>
  );
}

function ContributionTab() {
  const [amount, setAmount] = useState('');
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [error, setError] = useState(null);
  const [ok, setOk] = useState(false);

  const submit = async () => {
    setError(null); setOk(false);
    try {
      await axios.post(`${BACKEND_URL}/api/ledger/owner-contribution`,
        { amount: parseFloat(amount), date });
      setOk(true); setAmount('');
    } catch (err) { setError(err.response?.data?.detail || 'Erreur'); }
  };

  return (
    <div style={{ maxWidth: 480 }}>
      <div style={{ background: '#eff6ff', padding: 12, borderRadius: 6, marginBottom: 16,
        fontSize: 13, color: '#1e3a8a' }}>
        Enregistre un apport personnel dans l'entreprise.
      </div>
      <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Montant</label>
      <input type="number" step="0.01" value={amount} onChange={e => setAmount(e.target.value)}
             style={{ width: '100%', padding: 8, marginBottom: 12, border: '1px solid #d1d5db',
                      borderRadius: 6, boxSizing: 'border-box' }} />
      <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Date</label>
      <input type="date" value={date} onChange={e => setDate(e.target.value)}
             style={{ padding: 8, marginBottom: 12, border: '1px solid #d1d5db', borderRadius: 6 }} />
      {amount > 0 && (
        <div style={{ background: '#f3f4f6', padding: 12, borderRadius: 6, marginBottom: 12, fontSize: 13 }}>
          Cela enregistrera : <strong>Débit Encaisse {parseFloat(amount).toFixed(2)} $</strong> /{' '}
          <strong>Crédit Apport du propriétaire {parseFloat(amount).toFixed(2)} $</strong>
        </div>
      )}
      {error && <div style={{ color: '#991b1b', fontSize: 13, marginBottom: 8 }}>{error}</div>}
      {ok && <div style={{ color: '#059669', fontSize: 13, marginBottom: 8 }}>Apport enregistré.</div>}
      <button onClick={submit} disabled={!(amount > 0)} style={{
        background: '#00A08C', color: '#fff', border: 'none', padding: '10px 20px',
        borderRadius: 6, cursor: amount > 0 ? 'pointer' : 'not-allowed', fontWeight: 600,
        opacity: amount > 0 ? 1 : 0.5 }}>Enregistrer l'apport</button>
    </div>
  );
}
```
Brancher : `{tab === 'opening' && <OpeningTab />}` et `{tab === 'contribution' && <ContributionTab />}`.

- [ ] **Step 2: Sanity parse**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
node -e "require('@babel/parser').parse(require('fs').readFileSync('src/pages/LedgerPage.js','utf8'), {sourceType:'module', plugins:['jsx']}); console.log('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add frontend/src/pages/LedgerPage.js
git commit -m "feat(ledger): opening-balance wizard tab + owner-contribution tab"
```

---

## Task 17 : Pages Balance de vérification + Bilan (tableaux + export PDF)

**Files:**
- Modify: `frontend/src/pages/LedgerPage.js`

- [ ] **Step 1: Implémenter les onglets Trial balance + Bilan + Grand livre**

Dans `frontend/src/pages/LedgerPage.js`, ajouter le helper de téléchargement PDF authentifié + les 3 onglets restants :
```jsx
async function downloadPdf(url, filename) {
  const resp = await axios.get(url, { responseType: 'blob' });
  const blobUrl = window.URL.createObjectURL(new Blob([resp.data], { type: 'application/pdf' }));
  const a = document.createElement('a');
  a.href = blobUrl; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  window.URL.revokeObjectURL(blobUrl);
}

function TrialBalanceTab() {
  const [asOf, setAsOf] = useState(new Date().toISOString().slice(0, 10));
  const [data, setData] = useState(null);
  const load = () => axios.get(`${BACKEND_URL}/api/ledger/trial-balance?as_of=${asOf}`)
    .then(r => setData(r.data)).catch(() => {});
  useEffect(() => { load(); }, [asOf]);
  return (
    <div>
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center' }}>
        <input type="date" value={asOf} onChange={e => setAsOf(e.target.value)}
               style={{ padding: 6, border: '1px solid #d1d5db', borderRadius: 6 }} />
        <button onClick={() => downloadPdf(
          `${BACKEND_URL}/api/ledger/trial-balance/pdf?as_of=${asOf}`,
          `balance-verification-${asOf}.pdf`)} style={{
          background: '#00A08C', color: '#fff', border: 'none', padding: '6px 14px',
          borderRadius: 6, cursor: 'pointer' }}>Télécharger PDF</button>
        {data && (
          <span style={{ padding: '4px 12px', borderRadius: 999, fontSize: 13,
            background: data.balanced ? '#ecfdf5' : '#fef2f2',
            color: data.balanced ? '#059669' : '#dc2626' }}>
            {data.balanced ? 'Équilibrée' : 'Déséquilibrée'}</span>
        )}
      </div>
      {data && (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
          <thead><tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
            <th style={{ padding: 8 }}>Compte</th>
            <th style={{ padding: 8, textAlign: 'right' }}>Débit</th>
            <th style={{ padding: 8, textAlign: 'right' }}>Crédit</th></tr></thead>
          <tbody>
            {data.accounts.map(a => (
              <tr key={a.account_number} style={{ borderBottom: '1px solid #f3f4f6' }}>
                <td style={{ padding: 8 }}>{a.account_number} — {a.name}</td>
                <td style={{ padding: 8, textAlign: 'right' }}>
                  {a.debit_balance ? a.debit_balance.toFixed(2) + ' $' : ''}</td>
                <td style={{ padding: 8, textAlign: 'right' }}>
                  {a.credit_balance ? a.credit_balance.toFixed(2) + ' $' : ''}</td>
              </tr>
            ))}
            <tr style={{ fontWeight: 700, borderTop: '2px solid #1f2937' }}>
              <td style={{ padding: 8 }}>Total</td>
              <td style={{ padding: 8, textAlign: 'right' }}>{data.total_debit.toFixed(2)} $</td>
              <td style={{ padding: 8, textAlign: 'right' }}>{data.total_credit.toFixed(2)} $</td>
            </tr>
          </tbody>
        </table>
      )}
    </div>
  );
}

function BalanceSheetTab() {
  const [asOf, setAsOf] = useState(new Date().toISOString().slice(0, 10));
  const [data, setData] = useState(null);
  const load = () => axios.get(`${BACKEND_URL}/api/ledger/balance-sheet?as_of=${asOf}`)
    .then(r => setData(r.data)).catch(() => {});
  useEffect(() => { load(); }, [asOf]);
  const Section = ({ title, rows, total }) => (
    <div style={{ marginBottom: 16 }}>
      <h3 style={{ fontSize: 15, borderBottom: '1px solid #e5e7eb', paddingBottom: 4 }}>{title}</h3>
      {rows.map(r => (
        <div key={r.account_number} style={{ display: 'flex', justifyContent: 'space-between',
          padding: '4px 0', fontSize: 14 }}>
          <span>{r.account_number} — {r.name}</span><span>{r.balance.toFixed(2)} $</span>
        </div>
      ))}
      <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 700,
        borderTop: '1px solid #1f2937', paddingTop: 4, marginTop: 4 }}>
        <span>Total</span><span>{total.toFixed(2)} $</span></div>
    </div>
  );
  return (
    <div style={{ maxWidth: 640 }}>
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center' }}>
        <input type="date" value={asOf} onChange={e => setAsOf(e.target.value)}
               style={{ padding: 6, border: '1px solid #d1d5db', borderRadius: 6 }} />
        <button onClick={() => downloadPdf(
          `${BACKEND_URL}/api/ledger/balance-sheet/pdf?as_of=${asOf}`, `bilan-${asOf}.pdf`)}
          style={{ background: '#00A08C', color: '#fff', border: 'none', padding: '6px 14px',
            borderRadius: 6, cursor: 'pointer' }}>Télécharger PDF</button>
        {data && (
          <span style={{ padding: '4px 12px', borderRadius: 999, fontSize: 13,
            background: data.balanced ? '#ecfdf5' : '#fef2f2',
            color: data.balanced ? '#059669' : '#dc2626' }}>
            {data.balanced ? 'Équilibré' : 'Déséquilibré'}</span>
        )}
      </div>
      {data && (
        <>
          <Section title="Actif" rows={data.assets.accounts} total={data.assets.total} />
          <Section title="Passif" rows={data.liabilities.accounts} total={data.liabilities.total} />
          <div style={{ marginBottom: 16 }}>
            <h3 style={{ fontSize: 15, borderBottom: '1px solid #e5e7eb', paddingBottom: 4 }}>
              Capitaux propres</h3>
            {data.equity.accounts.map(r => (
              <div key={r.account_number} style={{ display: 'flex',
                justifyContent: 'space-between', padding: '4px 0', fontSize: 14 }}>
                <span>{r.account_number} — {r.name}</span><span>{r.balance.toFixed(2)} $</span>
              </div>
            ))}
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0',
              fontSize: 14, fontStyle: 'italic' }}>
              <span>Résultat net de l'exercice</span>
              <span>{data.equity.net_income_current_year.toFixed(2)} $</span></div>
            {/* ⚠️ Note Clôture annuelle (spec §7.2.1) */}
            <div style={{ background: '#FEF3C7', border: '1px solid #F59E0B',
              borderRadius: 6, padding: '8px 12px', marginTop: 8, fontSize: 12,
              color: '#92400E' }}>
              « Résultat net de l'exercice » est <strong>dérivé</strong> de l'exercice
              courant. La <strong>clôture annuelle</strong> (virement vers Bénéfices non
              répartis 3200) doit être passée manuellement <strong>à ou après la fin
              d'exercice</strong>, jamais en cours d'exercice. Sans elle, le bilan de
              l'exercice suivant sera <strong>déséquilibré</strong>.
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 700,
              borderTop: '1px solid #1f2937', paddingTop: 4, marginTop: 4 }}>
              <span>Total capitaux propres</span><span>{data.equity.total.toFixed(2)} $</span></div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 700,
            fontSize: 15, borderTop: '2px solid #1f2937', paddingTop: 8 }}>
            <span>Total passif + capitaux propres</span>
            <span>{data.total_liabilities_and_equity.toFixed(2)} $</span></div>
        </>
      )}
    </div>
  );
}

function LedgerDetailTab() {
  const [accounts, setAccounts] = useState([]);
  const [accountId, setAccountId] = useState('');
  const [data, setData] = useState(null);
  useEffect(() => {
    axios.get(`${BACKEND_URL}/api/ledger/accounts?active=true`)
      .then(r => setAccounts(r.data)).catch(() => {});
  }, []);
  useEffect(() => {
    if (!accountId) { setData(null); return; }
    axios.get(`${BACKEND_URL}/api/ledger/general-ledger?account_id=${accountId}`)
      .then(r => setData(r.data)).catch(() => {});
  }, [accountId]);
  return (
    <div>
      <select value={accountId} onChange={e => setAccountId(e.target.value)}
              style={{ padding: 8, marginBottom: 16, border: '1px solid #d1d5db', borderRadius: 6 }}>
        <option value="">— choisir un compte —</option>
        {accounts.map(a => (
          <option key={a.id} value={a.id}>{a.account_number} — {a.name}</option>
        ))}
      </select>
      {data && (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
          <thead><tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
            <th style={{ padding: 8 }}>Date</th><th style={{ padding: 8 }}>N°</th>
            <th style={{ padding: 8 }}>Description</th>
            <th style={{ padding: 8, textAlign: 'right' }}>Débit</th>
            <th style={{ padding: 8, textAlign: 'right' }}>Crédit</th>
            <th style={{ padding: 8, textAlign: 'right' }}>Solde</th></tr></thead>
          <tbody>
            <tr><td colSpan={5} style={{ padding: 8, fontStyle: 'italic' }}>Solde d'ouverture</td>
              <td style={{ padding: 8, textAlign: 'right' }}>{data.opening_balance.toFixed(2)} $</td></tr>
            {data.lines.map((ln, i) => (
              <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                <td style={{ padding: 8 }}>{ln.entry_date}</td>
                <td style={{ padding: 8, fontFamily: 'monospace' }}>{ln.entry_number}</td>
                <td style={{ padding: 8 }}>{ln.description}</td>
                <td style={{ padding: 8, textAlign: 'right' }}>{ln.debit ? ln.debit.toFixed(2) + ' $' : ''}</td>
                <td style={{ padding: 8, textAlign: 'right' }}>{ln.credit ? ln.credit.toFixed(2) + ' $' : ''}</td>
                <td style={{ padding: 8, textAlign: 'right' }}>{ln.running_balance.toFixed(2)} $</td>
              </tr>
            ))}
            <tr style={{ fontWeight: 700, borderTop: '2px solid #1f2937' }}>
              <td colSpan={5} style={{ padding: 8 }}>Solde de clôture</td>
              <td style={{ padding: 8, textAlign: 'right' }}>{data.closing_balance.toFixed(2)} $</td></tr>
          </tbody>
        </table>
      )}
    </div>
  );
}
```
Brancher les onglets restants :
```jsx
{tab === 'ledger' && <LedgerDetailTab />}
{tab === 'trial' && <TrialBalanceTab />}
{tab === 'balancesheet' && <BalanceSheetTab />}
```

- [ ] **Step 2: Sanity parse + build**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
node -e "require('@babel/parser').parse(require('fs').readFileSync('src/pages/LedgerPage.js','utf8'), {sourceType:'module', plugins:['jsx']}); console.log('OK')"
npm run build 2>&1 | tail -10
```
Expected : build success. Fixer toute erreur ESLint/parse.

- [ ] **Step 3: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add frontend/src/pages/LedgerPage.js
git commit -m "feat(ledger): trial-balance + balance-sheet + per-account ledger tabs (PDF export)"
```

---

## Task 18 : Tests intégration E2E + push + CLAUDE.md

**Files:**
- Modify: `backend/tests/test_general_ledger_integration.py`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Ajouter les tests RBAC + isolation cross-org**

Append à `backend/tests/test_general_ledger_integration.py` :
```python
class TestLedgerRBAC:
    def _make_viewer(self, client):
        """Crée un user viewer dans l'org du owner via invitation directe DB."""
        owner = server_module.db.users.find_one({"email": "gussdub@gmail.com"})
        org_id = owner["organization_id"]
        uid = f"gl-viewer-{uuid.uuid4().hex[:8]}"
        server_module.db.users.insert_one({
            "id": uid, "email": f"{uid}@viewer.test", "is_active": True,
            "organization_id": org_id, "role": "viewer",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        server_module.db.user_passwords.insert_one({
            "user_id": uid,
            "hashed_password": server_module.hash_password("viewerpass"),
        })
        r = client.post("/api/auth/login",
                        json={"email": f"{uid}@viewer.test", "password": "viewerpass"})
        return uid, {"Authorization": f"Bearer {r.json()['access_token']}"}

    def test_viewer_can_read_but_not_write(self, client):
        uid, vh = self._make_viewer(client)
        try:
            r = client.get("/api/ledger/entries", headers=vh)
            assert r.status_code == 200
            accounts = client.get("/api/ledger/accounts", headers=vh).json()
            by_num = {a["account_number"]: a for a in accounts}
            r2 = client.post("/api/ledger/entries", headers=vh, json={
                "entry_date": "2026-06-01", "description": "no", "status": "posted",
                "lines": [
                    {"account_id": by_num["1000"]["id"], "debit": 10, "credit": 0},
                    {"account_id": by_num["4000"]["id"], "debit": 0, "credit": 10},
                ],
            })
            assert r2.status_code == 403
        finally:
            server_module.db.users.delete_one({"id": uid})
            server_module.db.user_passwords.delete_one({"user_id": uid})


class TestLedgerCrossOrgIsolation:
    def _setup_org_b(self, client):
        uid = f"glb-{uuid.uuid4().hex[:8]}"
        org_id = str(uuid.uuid4())
        server_module.db.organizations.insert_one({
            "id": org_id, "name": "OrgB GL", "owner_id": uid,
            "subscription_status": "trial",
            "trial_ends_at": (datetime.now(timezone.utc) + timedelta(days=100)).isoformat(),
            "role_permissions": server_module.DEFAULT_ROLE_PERMISSIONS,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        server_module.db.company_settings.insert_one({
            "id": f"cs-{org_id}", "user_id": uid, "organization_id": org_id,
            "company_name": "OrgB GL",
        })
        server_module.db.users.insert_one({
            "id": uid, "email": f"{uid}@orgb.test", "is_active": True,
            "organization_id": org_id, "role": "owner",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        server_module.db.user_passwords.insert_one({
            "user_id": uid, "hashed_password": server_module.hash_password("orgbpass"),
        })
        r = client.post("/api/auth/login",
                        json={"email": f"{uid}@orgb.test", "password": "orgbpass"})
        return uid, org_id, {"Authorization": f"Bearer {r.json()['access_token']}"}

    def _cleanup(self, uid, org_id):
        server_module.db.users.delete_one({"id": uid})
        server_module.db.user_passwords.delete_one({"user_id": uid})
        server_module.db.organizations.delete_one({"id": org_id})
        server_module.db.company_settings.delete_many({"organization_id": org_id})
        server_module.db.chart_of_accounts.delete_many({"organization_id": org_id})
        server_module.db.journal_entries.delete_many({"organization_id": org_id})
        server_module.db.ledger_counters.delete_many({"organization_id": org_id})

    def test_org_b_cannot_read_org_a_entry(self, client, owner_headers):
        # org A (owner) crée une écriture
        accounts = client.get("/api/ledger/accounts", headers=owner_headers).json()
        by_num = {a["account_number"]: a for a in accounts}
        r = client.post("/api/ledger/entries", headers=owner_headers, json={
            "entry_date": "2026-06-02", "description": "OrgA privée", "status": "posted",
            "lines": [
                {"account_id": by_num["1000"]["id"], "debit": 77, "credit": 0},
                {"account_id": by_num["4000"]["id"], "debit": 0, "credit": 77},
            ],
        })
        entry_id_a = r.json()["id"]
        uid, org_id, hb = self._setup_org_b(client)
        try:
            # org B GET l'écriture de A → 404
            r2 = client.get(f"/api/ledger/entries/{entry_id_a}", headers=hb)
            assert r2.status_code == 404
            # la balance de B n'inclut pas les comptes de A (org B a son propre seed)
            tb = client.get("/api/ledger/trial-balance?as_of=2026-12-31", headers=hb).json()
            assert tb["total_debit"] == 0 or all(
                a["debit_balance"] != 77 for a in tb["accounts"])
        finally:
            client.post(f"/api/ledger/entries/{entry_id_a}/reverse",
                        headers=owner_headers, json={})
            self._cleanup(uid, org_id)

    def test_org_b_isolated_je_counter(self, client, owner_headers):
        # org B doit démarrer à JE-0001 indépendamment de A
        uid, org_id, hb = self._setup_org_b(client)
        try:
            accounts = client.get("/api/ledger/accounts", headers=hb).json()
            by_num = {a["account_number"]: a for a in accounts}
            r = client.post("/api/ledger/entries", headers=hb, json={
                "entry_date": "2026-06-03", "description": "OrgB first", "status": "posted",
                "lines": [
                    {"account_id": by_num["1000"]["id"], "debit": 5, "credit": 0},
                    {"account_id": by_num["4000"]["id"], "debit": 0, "credit": 5},
                ],
            })
            assert r.json()["entry_number"] == "JE-0001"
        finally:
            self._cleanup(uid, org_id)
```

- [ ] **Step 2: Run la suite GL complète**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_general_ledger.py tests/test_general_ledger_integration.py -v 2>&1 | tail -40
```
Expected : toute la suite GL passe.

- [ ] **Step 3: Full non-regression run**

```bash
pytest tests/ 2>&1 | tail -20
```
Expected : la suite complète passe, aucune régression.

- [ ] **Step 4: Update CLAUDE.md — ajouter la feature au changelog**

Ajouter en tête de la section « Features livrées » (avant la feature #11.1) :

```markdown
- **2026-07-03 — Grand livre en partie double, Phase 1 MVP (feature #12)**
  - 3 nouvelles collections : `chart_of_accounts` (plan comptable seedé par org, 29 comptes par défaut QC), `journal_entries` (lignes Dr/Cr embarquées, équilibre forcé backend), `ledger_counters` (numérotation atomique JE-XXXX/OB-0001 par org)
  - RBAC : `accounting:read` + `accounting:write` ajoutés à `PERMISSIONS_EDITABLE` (comptable = read+write, lecteur = read) ; backfill idempotent dans `migrate_general_ledger_v1`
  - Champs fiscaux sur `company_settings` : `fiscal_year_end_month/day` (défaut 12/31) + `ledger_start_date` ; éditables via `PUT /api/settings/company`
  - Partie double stricte : `_validate_entry_balance` (Dr=Cr forcé, tolérance 0,005 $, rejet 400) ; écritures postées immuables ; contre-passation par écriture miroir POSTED (l'origine RESTE `posted`, lien d'audit `reverses_entry_id`/`reversed_by_entry_id`, net zéro garanti, double contre-passation bloquée) ; statuts d'écriture = `draft`|`posted` seulement ; brouillons éditables
  - Assistant bilan d'ouverture (`OB-0001`, un seul par org, remplaçable) ; apport propriétaire guidé (Dr Encaisse / Cr Apport 3100)
  - États financiers : grand livre par compte (solde progressif), balance de vérification (invariant Dr=Cr), bilan (Actif = Passif + CP, résultat net dérivé sur l'exercice), 2 PDF FR-CA no-cache
  - ~15 endpoints `/api/ledger/*` org-scopés ; seed lazy du plan au 1er accès (idempotent)
  - Frontend : entrée sidebar « Grand livre » gatée `accounting:read` + RouteGuard, `LedgerPage` à 7 onglets (plan, journal avec compteur d'équilibre live, assistant ouverture, apport, grand livre, balance, bilan)
  - Limites v1 : auto-posting (Phase 2, plan séparé), écriture de clôture annuelle NON automatisée (résultat net dérivé — ⚠️ clôture manuelle à/après fin d'exercice obligatoire, sinon bilan N+1 déséquilibré ; avertissement UI onglets Journal + Bilan), CAD only, pas de verrou de période, export GIFI/T2 hors scope
  - Tests : ~25 unitaires + ~32 intégration = **~57 nouveaux tests** (dont net-zéro après contre-passation + balance équilibrée + double contre-passation bloquée), 0 régression
  - Spec : `docs/superpowers/specs/2026-07-03-general-ledger-design.md`
  - Plan : `docs/superpowers/plans/2026-07-03-general-ledger-phase1.md`
```

- [ ] **Step 5: Commit + push prod** *(le push reste sous contrôle humain — cf. convention feature #11 : aucun agent ne push sans revue finale)*

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add CLAUDE.md
git commit -m "docs: feature #12 general ledger phase 1 dans changelog"
# git push origin main   ← à exécuter manuellement après revue
```

Render redéploie backend (~3-5 min — `migrate_general_ledger_v1()` s'exécute au boot). Vercel redéploie frontend (~2 min).

- [ ] **Step 6: Monitoring post-deploy** *(après push manuel)*

Vérifier logs Render dans les 30 min :
- Aucune erreur 500 en cascade sur `/api/settings/company`, `/api/ledger/*`.
- `GET /api/ledger/accounts` sur `https://facturepro.ca` (compte owner prod) → plan à 29 comptes seedé.
- `GET /api/ledger/trial-balance` et `/balance-sheet` → `balanced: true` sur un jeu vide (0 = 0).
- Aucune régression sur factures/devis/dépenses/rapports/banque.

---

## Self-review

**1. Spec coverage** :
- ✅ §2 décision #1 (partie double stricte, équilibre forcé backend) : T5 `_validate_entry_balance` + T6 endpoints.
- ✅ §2 décision #3 (assistant ouverture, `entry_type="opening"`) : T7.
- ✅ §2 décision #4 (plages canoniques, type déduit du numéro) : T1 `_account_type_for_number`, T4 validation POST.
- ✅ §2 décision #5 (immuable + contre-passation) : T6 `reverse` + PUT/DELETE 400 sur posted.
- ✅ §2 décision #6 (apport guidé Dr 1000 / Cr 3100) : T8.
- ✅ §2 décision #7 (exercice sur `company_settings`) : T3 champs fiscaux + `PUT /api/settings/company`.
- ✅ §2 décision #8 (résultat net dérivé, non stocké) : T10 bilan `net_income_current_year`.
- ✅ §2 décision #9 (plan seedé par org, idempotent, mappé EXPENSE_CATEGORIES) : T1 `_build_default_accounts` + T4 `_ensure_chart_seeded`.
- ✅ §2 décision #10 (soft-delete si compte utilisé, hard si zéro ligne) : T4 DELETE.
- ✅ §2 décision #12 (RBAC accounting:read/write éditables) : T2.
- ✅ §2 décision #13 (séquence JE-XXXX / OB-0001 atomique) : T6 `_next_entry_number`.
- ✅ §3.1 (`chart_of_accounts` shape + normal_balance dérivé) : T1.
- ✅ §3.2 (`journal_entries` shape + invariants + lignes embarquées) : T6.
- ✅ §3.3 (`ledger_counters` atomique) : T6.
- ✅ §3.4 (champs `company_settings` fiscaux) : T3.
- ✅ §4 (plan par défaut 29 comptes) : T1 + tests `test_total_29_accounts`.
- ✅ §5.1 (validation équilibre — code exact repris) : T5.
- ✅ §5.2 (`_account_balance` orienté normal_balance, posted only, as_of) : T5.
- ✅ §5.3 (contre-passation : miroir posted Dr↔Cr inversés, origine RESTE posted, `reversed_by_entry_id` d'audit seulement, net zéro, double contre-passation bloquée en 400) : T6 (`reverse` + tests `test_reverse_nets_to_zero_and_stays_balanced`, `test_reverse_twice_forbidden`).
- ✅ §6.1 (accounts CRUD, codes retour 201/400/409/204) : T4.
- ✅ §6.2 (journal, post, reverse, delete) : T6.
- ✅ §6.3 (opening-balance GET/POST/PUT, 409 doublon) : T7.
- ✅ §6.4 (owner-contribution défauts 1000/3100, amount>0) : T8.
- ✅ §6.5 (general-ledger, trial-balance, balance-sheet + 2 PDF) : T9, T10, T11, T12.
- ✅ §7.1 (formule trial balance, colonne opposée si négatif, exclusion solde 0) : T9 `_trial_balance_rows`.
- ✅ §7.2 (bilan, `_current_fiscal_year` déc. + non-déc., net income sur [fy_start, as_of]) : T10.
- ✅ §7.3 (PDF FR-CA, `html.escape`, no-cache) : T12 réutilise `_t2125_format_money`.
- ✅ §8.1 (codes dans `PERMISSIONS_EDITABLE`) : T2.
- ✅ §8.2 (migration idempotente, indexes, backfill perms, flag pas de ré-écrasement) : T2 + T3.
- ✅ §8.3 (seed lazy `_ensure_chart_seeded`) : T4.
- ✅ §9 (frontend : sidebar gatée, 7 onglets, compteur équilibre live, export PDF) : T13-T17.
- ✅ §11 (sécurité : isolation cross-org, équilibre backend, immuabilité, un OB par org, compteur atomique) : couvert par les endpoints + tests T18.
- ✅ §12.1 (tests unitaires : validation, solde, plan par défaut, normal_balance, fiscal year, trial balance) : T1, T5, T9, T10.
- ✅ §12.2 (tests intégration : seed lazy, CRUD, journal équilibre forcé, ouverture, apport, grand livre, balance, bilan, RBAC, isolation, PDF, migration) : T3-T12, T18.
- ✅ §13 (limites v1 : auto-posting Phase 2, clôture manuelle, CAD only) : documentées dans CLAUDE.md (T18).
- ✅ §14 (rollback : module additif, migration idempotente, aucune donnée métier mutée) : la migration n'ajoute que des champs (`$exists` gating), 3 collections additives.

**2. Alignement avec le code réel** :
- `PERMISSIONS_EDITABLE` contient déjà `settings:read/write` (feature #11.1) ; T2 ajoute `accounting:*` à la suite — pas de conflit.
- `PERMISSIONS_OWNER_ONLY` = `["billing:manage", "team:manage"]` (pas `settings:manage`) : le plan n'y touche pas.
- `migrate_organizations_v1` fait déjà un backfill perms par boucle org : T2 s'y greffe, T3 duplique le motif dans `migrate_general_ledger_v1` (les deux idempotents et cohérents).
- PDF : réutilise `_t2125_format_money` (ligne 5352) + pattern `Response` no-cache (ligne 5548) vérifiés.
- `EXPENSE_CATEGORIES` a bien les clés `code` / `label_fr` / `arc_line` (ligne 150) : `_build_default_accounts` s'appuie sur `code` + `label_fr`, `other` exclu (17 comptes de dépenses → 29 total).
- Startup `seed_data()` (ligne 5555) appelle `migrate_organizations_v1()` (ligne 5582) : T3 insère `migrate_general_ledger_v1()` juste après.
- Compteur atomique : même motif `find_one_and_update` `$inc` upsert que l'existant (`server.py:939`).

**3. Placeholder scan** : aucun « TODO »/« TBD ». Les rares « adapter au code existant » concernent le nom exact de la variable d'accumulation du handler settings (T3 Step 5), la forme exacte des entrées de nav (T13) et la mécanique de routing `window.history` (T13) — inévitables car dépendants du code frontend/handler actuel, et documentés.

**4. Type consistency** :
- `account_type` ∈ 5 valeurs, `normal_balance` ∈ {debit, credit}, `status` ∈ {draft, posted} (PAS de `reversed` : une écriture contre-passée reste `posted`, §5.3), `entry_type` ∈ {manual, opening, reversal, auto} — uniformes backend/tests/frontend. Le lien de contre-passation vit dans les champs d'audit `reverses_entry_id`/`reversed_by_entry_id`, jamais dans `status`.
- `organization_id` partout (jamais `org_id` dans le métier), `entry_number` format `JE-XXXX`/`OB-0001`.
- Endpoints `/api/ledger/*` cohérents avec spec §6 exactement.
- Montants : `float` CAD arrondis 2 décimales côté backend, `.toFixed(2)` côté frontend.

**5. Rollback** : Phase 1 purement additive (3 collections neuves + champs `company_settings` via `$exists` gating). `migrate_general_ledger_v1` idempotente. Redeploy previous Render safe — aucun code legacy ne lit les nouvelles collections. Point de non-retour : aucun.

Plan prêt à l'exécution.
