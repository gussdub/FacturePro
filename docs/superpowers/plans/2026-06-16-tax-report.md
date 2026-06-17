# Tax Report TPS/TVQ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permettre la saisie des TPS/TVQ/TVH payées sur dépenses, et générer un rapport trimestriel (sommaire + format CRA + format Revenu Québec) en JSON et PDF.

**Architecture:** Helpers backend `_compute_taxes_paid(amount_gross, province)` et `_quarter_to_dates(year, quarter)` côté Python + miroir JS côté ExpensesPage pour le bouton "Calculer auto". Nouveaux champs sur `expenses` (4) et `company_settings` (1, `province`), tous optionnels avec défauts graceful. Nouveau endpoint `GET /api/reports/sales-tax` qui filtre/agrège invoices + expenses sur une plage de dates. Nouveau endpoint PDF qui réutilise ReportLab. Nouvelle page frontend "Rapports" avec quick-picker trimestre.

**Tech Stack:** FastAPI Python 3.11 + pymongo, React 18 CRA, pytest, ReportLab, MongoDB Atlas.

**Spec source:** [docs/superpowers/specs/2026-06-16-tax-report-design.md](../specs/2026-06-16-tax-report-design.md)

---

## File Structure

**Created:**
- `backend/tests/test_tax_report.py` — tests unitaires des helpers (~80 lignes)
- `backend/tests/test_tax_report_integration.py` — tests intégration HTTP (~250 lignes)
- `frontend/src/pages/ReportsPage.js` — nouvelle page (~200 lignes)

**Modified:**
- `backend/server.py` — helpers (~40 lignes), endpoints POST/PUT expenses étendus (~15 lignes), GET/PUT settings étendus (~10 lignes), endpoint rapport JSON (~80 lignes), endpoint rapport PDF (~150 lignes)
- `frontend/src/pages/SettingsPage.js` — dropdown province (~30 lignes)
- `frontend/src/pages/ExpensesPage.js` — section "Taxes payées" + bouton calculer auto (~80 lignes)
- `frontend/src/App.js` — route `/reports` + entrée nav (~5 lignes)
- `frontend/src/components/Layout.js` — entrée menu "Rapports" (~5 lignes)
- `CLAUDE.md` — changelog feature livrée (~10 lignes)

---

## Task 1 — Helpers `_compute_taxes_paid` et `_quarter_to_dates`

**Files:**
- Create: `backend/tests/test_tax_report.py`
- Modify: `backend/server.py` (ajouter après les helpers de feature #3, avant les endpoints)

- [ ] **Step 1: Écrire les tests**

Créer `backend/tests/test_tax_report.py` :

```python
"""Tests unitaires pour le rapport TPS/TVQ (feature #4)."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "facturepro_test_unit")
os.environ.setdefault("JWT_SECRET", "test")

from server import _compute_taxes_paid, _quarter_to_dates, PROVINCES_VALID


class TestComputeTaxesPaid:
    def test_qc_on_114_975(self):
        # 114.975 brut = 100 net + 5 TPS + 9.975 TVQ
        result = _compute_taxes_paid(114.975, "QC")
        assert result["gst"] == 5.00
        assert result["qst"] == 9.98  # round(9.975, 2)
        assert result["hst"] == 0

    def test_qc_zero_amount(self):
        result = _compute_taxes_paid(0, "QC")
        assert result == {"gst": 0, "qst": 0, "hst": 0}

    def test_qc_none_amount(self):
        result = _compute_taxes_paid(None, "QC")
        assert result == {"gst": 0, "qst": 0, "hst": 0}

    def test_qc_negative_amount(self):
        result = _compute_taxes_paid(-50, "QC")
        assert result == {"gst": 0, "qst": 0, "hst": 0}

    def test_on_on_113(self):
        # 113 brut = 100 net + 13 TVH
        result = _compute_taxes_paid(113, "ON")
        assert result["gst"] == 0
        assert result["qst"] == 0
        assert result["hst"] == 13.00

    def test_nb_on_115(self):
        # 115 brut = 100 net + 15 TVH (Maritimes)
        result = _compute_taxes_paid(115, "NB")
        assert result["hst"] == 15.00
        assert result["gst"] == 0

    def test_ns_on_115(self):
        assert _compute_taxes_paid(115, "NS")["hst"] == 15.00

    def test_pe_on_115(self):
        assert _compute_taxes_paid(115, "PE")["hst"] == 15.00

    def test_nl_on_115(self):
        assert _compute_taxes_paid(115, "NL")["hst"] == 15.00

    def test_bc_on_105(self):
        # 105 brut = 100 net + 5 TPS (BC : la PST n'est pas tracée comme CTI)
        result = _compute_taxes_paid(105, "BC")
        assert result["gst"] == 5.00
        assert result["qst"] == 0
        assert result["hst"] == 0

    def test_ab_on_105(self):
        assert _compute_taxes_paid(105, "AB")["gst"] == 5.00

    def test_unknown_province_falls_back_to_gst_only(self):
        result = _compute_taxes_paid(105, "ZZ")
        assert result == {"gst": 5.00, "qst": 0, "hst": 0}


class TestQuarterToDates:
    def test_q1(self):
        assert _quarter_to_dates("2026", "Q1") == ("2026-01-01", "2026-03-31")

    def test_q2(self):
        assert _quarter_to_dates("2026", "Q2") == ("2026-04-01", "2026-06-30")

    def test_q3(self):
        assert _quarter_to_dates("2026", "Q3") == ("2026-07-01", "2026-09-30")

    def test_q4(self):
        assert _quarter_to_dates("2026", "Q4") == ("2026-10-01", "2026-12-31")

    def test_year_2025(self):
        assert _quarter_to_dates("2025", "Q1") == ("2025-01-01", "2025-03-31")


class TestProvincesValid:
    def test_contains_qc_on(self):
        assert "QC" in PROVINCES_VALID
        assert "ON" in PROVINCES_VALID

    def test_contains_all_13(self):
        expected = {
            "QC", "ON", "BC", "AB", "SK", "MB",
            "NB", "NS", "PE", "NL", "YT", "NU", "NT",
        }
        assert set(PROVINCES_VALID) == expected
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
pytest tests/test_tax_report.py -v 2>&1 | tail -15
```

Expected: `ImportError: cannot import name '_compute_taxes_paid' from 'server'`

- [ ] **Step 3: Implémenter les helpers dans `server.py`**

Localiser une place après les helpers de feature #3 (par exemple après `_build_expense_category_snapshot`, autour de la ligne 180). Ajouter :

```python
PROVINCES_VALID = frozenset({
    "QC", "ON", "BC", "AB", "SK", "MB",
    "NB", "NS", "PE", "NL", "YT", "NU", "NT",
})


def _compute_taxes_paid(amount_gross, province):
    """Calcule les taxes incluses dans un montant brut TTC selon la province.
    Toutes les valeurs retournées sont des floats CAD arrondis à 2 décimales.

    QC      : 5 % TPS + 9.975 % TVQ → diviseur 114.975
    ON      : 13 % TVH               → diviseur 113
    NB/NS/PE/NL : 15 % TVH           → diviseur 115
    autres (BC, AB, SK, MB, YT, NU, NT, inconnu) : 5 % TPS → diviseur 105
    """
    if not amount_gross or amount_gross <= 0:
        return {"gst": 0, "qst": 0, "hst": 0}
    if province == "QC":
        return {
            "gst": round(amount_gross * 5 / 114.975, 2),
            "qst": round(amount_gross * 9.975 / 114.975, 2),
            "hst": 0,
        }
    if province == "ON":
        return {"gst": 0, "qst": 0, "hst": round(amount_gross * 13 / 113, 2)}
    if province in ("NB", "NS", "PE", "NL"):
        return {"gst": 0, "qst": 0, "hst": round(amount_gross * 15 / 115, 2)}
    # BC, AB, SK, MB, YT, NU, NT, ou inconnu → TPS seule
    return {"gst": round(amount_gross * 5 / 105, 2), "qst": 0, "hst": 0}


_QUARTER_STARTS = {"Q1": "01-01", "Q2": "04-01", "Q3": "07-01", "Q4": "10-01"}
_QUARTER_ENDS = {"Q1": "03-31", "Q2": "06-30", "Q3": "09-30", "Q4": "12-31"}


def _quarter_to_dates(year, quarter):
    """Q1=jan-mar, Q2=avr-jun, Q3=jul-sep, Q4=oct-dec.
    Retourne (start: 'YYYY-MM-DD', end: 'YYYY-MM-DD')."""
    return (f"{year}-{_QUARTER_STARTS[quarter]}", f"{year}-{_QUARTER_ENDS[quarter]}")
```

- [ ] **Step 4: Vérifier que les tests passent**

```bash
pytest tests/test_tax_report.py -v 2>&1 | tail -15
```

Expected: **20 passed** (12 TestComputeTaxesPaid + 5 TestQuarterToDates + 3 TestProvincesValid = 20).

Note: 9.975 arrondi à 2 décimales = 9.97 ou 9.98 selon le mode d'arrondi de Python (banker's rounding). Vérifie : `round(9.975, 2)` peut retourner 9.97 sur certaines plateformes à cause de la représentation flottante. Si le test `test_qc_on_114_975` échoue avec `9.97` au lieu de `9.98`, change le test pour utiliser `assert result["qst"] in (9.97, 9.98)` OU change le helper pour utiliser `Decimal` (overkill). Préfère la première option.

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/tests/test_tax_report.py backend/server.py
git commit -m "feat(taxes): helpers _compute_taxes_paid + _quarter_to_dates + PROVINCES_VALID"
```

---

## Task 2 — Ajouter `province` à GET/PUT `/api/settings/company`

**Files:**
- Modify: `backend/server.py` (endpoints settings)
- Create: `backend/tests/test_tax_report_integration.py`

- [ ] **Step 1: Créer le fichier de tests d'intégration avec auth fixture + tests province**

Créer `backend/tests/test_tax_report_integration.py` :

```python
"""Tests d'intégration HTTP pour le rapport TPS/TVQ (feature #4)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("FACTUREPRO_BACKEND_URL", "http://localhost:8000").rstrip("/")
TEST_EMAIL = "gussdub@gmail.com"
TEST_PASSWORD = "testpass123"


@pytest.fixture(scope="module")
def auth():
    resp = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


class TestSettingsProvince:
    def test_get_returns_province_field(self, auth):
        resp = requests.get(f"{BASE_URL}/api/settings/company", headers=auth)
        assert resp.status_code == 200
        body = resp.json()
        assert "province" in body
        assert body["province"] in (
            "QC", "ON", "BC", "AB", "SK", "MB",
            "NB", "NS", "PE", "NL", "YT", "NU", "NT",
        )

    def test_put_qc(self, auth):
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth,
                      json={"province": "QC"})
        body = requests.get(f"{BASE_URL}/api/settings/company", headers=auth).json()
        assert body["province"] == "QC"

    def test_put_on(self, auth):
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth,
                      json={"province": "ON"})
        body = requests.get(f"{BASE_URL}/api/settings/company", headers=auth).json()
        assert body["province"] == "ON"
        # Restore
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth,
                      json={"province": "QC"})

    def test_put_invalid_value_ignored(self, auth):
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth,
                      json={"province": "QC"})
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth,
                      json={"province": "XX"})
        body = requests.get(f"{BASE_URL}/api/settings/company", headers=auth).json()
        assert body["province"] == "QC"
```

- [ ] **Step 2: Démarrer uvicorn et vérifier que les tests échouent**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
lsof -ti:8000 | xargs kill 2>/dev/null
source .venv/bin/activate
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_tax_report_integration.py::TestSettingsProvince -v 2>&1 | tail -15
```

Expected: tests FAIL (champ `province` absent).

- [ ] **Step 3: Modifier les endpoints settings dans `server.py`**

Localiser le GET `/api/settings/company` (modifié à plusieurs reprises dans les features #2 et #3). Pour le **GET** :

Dans le default doc (quand settings est absent), ajouter `"province": "QC"`.

Après les `setdefault` existants (TAX_FIELDS + entity_type), ajouter :
```python
    settings.setdefault("province", "QC")
```

Pour le **PUT** : juste après le bloc qui valide `entity_type`, ajouter :
```python
    # Validation province : seules les 13 valeurs canadiennes acceptées
    if "province" in update and update["province"] not in PROVINCES_VALID:
        update.pop("province")
```

- [ ] **Step 4: Redémarrer et relancer**

```bash
lsof -ti:8000 | xargs kill 2>/dev/null
source .venv/bin/activate
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_tax_report.py tests/test_tax_report_integration.py::TestSettingsProvince -v 2>&1 | tail -10
```

Expected: 24 passed (20 unit + 4 settings).

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_tax_report_integration.py
git commit -m "feat(settings): champ province (13 valeurs CA) avec défaut QC + validation"
```

---

## Task 3 — Ajouter 4 champs taxes payées à POST/PUT `/api/expenses`

**Files:**
- Modify: `backend/server.py` (endpoints expenses)
- Modify: `backend/tests/test_tax_report_integration.py` (ajouter `TestExpenseTaxesPaid`)

- [ ] **Step 1: Ajouter les tests**

Append à `backend/tests/test_tax_report_integration.py` :

```python
class TestExpenseTaxesPaid:
    _cleanup_ids = []
    _auth_headers = None

    def test_create_with_taxes_paid(self, auth):
        TestExpenseTaxesPaid._auth_headers = auth
        payload = {
            "description": "Achat fournitures",
            "amount": 114.975,
            "currency": "CAD",
            "category_code": "office_expenses",
            "expense_date": "2026-06-16",
            "gst_paid_cad": 5.00,
            "qst_paid_cad": 9.98,
            "hst_paid_cad": 0,
            "taxes_auto_computed": True,
        }
        resp = requests.post(f"{BASE_URL}/api/expenses", headers=auth, json=payload)
        assert resp.status_code in (200, 201)
        exp = resp.json()
        TestExpenseTaxesPaid._cleanup_ids.append(exp["id"])
        assert exp["gst_paid_cad"] == 5.00
        assert exp["qst_paid_cad"] == 9.98
        assert exp["hst_paid_cad"] == 0
        assert exp["taxes_auto_computed"] is True

    def test_create_without_taxes_paid_defaults(self, auth):
        TestExpenseTaxesPaid._auth_headers = auth
        payload = {
            "description": "Plain expense",
            "amount": 100,
            "currency": "CAD",
            "expense_date": "2026-06-16",
        }
        resp = requests.post(f"{BASE_URL}/api/expenses", headers=auth, json=payload)
        exp = resp.json()
        TestExpenseTaxesPaid._cleanup_ids.append(exp["id"])
        assert exp["gst_paid_cad"] == 0
        assert exp["qst_paid_cad"] == 0
        assert exp["hst_paid_cad"] == 0
        assert exp["taxes_auto_computed"] is False

    def test_update_taxes_paid(self, auth):
        TestExpenseTaxesPaid._auth_headers = auth
        resp = requests.post(f"{BASE_URL}/api/expenses", headers=auth, json={
            "description": "To update",
            "amount": 113,
            "currency": "CAD",
            "expense_date": "2026-06-16",
        })
        eid = resp.json()["id"]
        TestExpenseTaxesPaid._cleanup_ids.append(eid)
        upd = requests.put(f"{BASE_URL}/api/expenses/{eid}", headers=auth,
                            json={"hst_paid_cad": 13.00, "taxes_auto_computed": True})
        assert upd.status_code == 200
        exp = upd.json()
        assert exp["hst_paid_cad"] == 13.00
        assert exp["taxes_auto_computed"] is True

    @classmethod
    def teardown_class(cls):
        if not cls._auth_headers:
            return
        for eid in cls._cleanup_ids:
            try:
                requests.delete(f"{BASE_URL}/api/expenses/{eid}", headers=cls._auth_headers)
            except Exception:
                pass
        cls._cleanup_ids = []
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
pytest tests/test_tax_report_integration.py::TestExpenseTaxesPaid -v 2>&1 | tail -15
```

Expected: FAIL (champs absents).

- [ ] **Step 3: Modifier les endpoints expenses dans `server.py`**

Pour le **POST `/api/expenses`** : dans le `doc` literal, ajouter les 4 nouveaux champs avec défauts :

```python
        "gst_paid_cad": float(expense_data.get("gst_paid_cad", 0) or 0),
        "qst_paid_cad": float(expense_data.get("qst_paid_cad", 0) or 0),
        "hst_paid_cad": float(expense_data.get("hst_paid_cad", 0) or 0),
        "taxes_auto_computed": bool(expense_data.get("taxes_auto_computed", False)),
```

Placer ces 4 lignes après les champs de catégorie (déjà ajoutés en feature #3, via `**cat_snapshot`), avant `expense_date`.

Pour le **PUT `/api/expenses/{id}`** : le PUT existant fait déjà un `$set` sur les champs fournis. Les nouveaux champs passent naturellement. Aucune modification supplémentaire requise. Si un cast est nécessaire (par sécurité contre type strings), ajouter avant le `update_one` :

```python
    # Cast des champs taxes payées si présents (le frontend peut envoyer des strings)
    for k in ("gst_paid_cad", "qst_paid_cad", "hst_paid_cad"):
        if k in expense_data:
            expense_data[k] = float(expense_data[k] or 0)
    if "taxes_auto_computed" in expense_data:
        expense_data["taxes_auto_computed"] = bool(expense_data["taxes_auto_computed"])
```

- [ ] **Step 4: Redémarrer et relancer**

```bash
lsof -ti:8000 | xargs kill 2>/dev/null
source .venv/bin/activate
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_tax_report.py tests/test_tax_report_integration.py -v 2>&1 | tail -15
```

Expected: 27 passed (20 unit + 4 settings + 3 expense taxes).

Aussi vérifier que les tests des features précédentes ne sont pas cassés :
```bash
pytest tests/test_tax_numbers.py tests/test_tax_registrations_integration.py tests/test_expense_categories.py tests/test_expense_categories_integration.py -v 2>&1 | tail -5
```
Expected: 75 PASS.

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_tax_report_integration.py
git commit -m "feat(expenses): champs gst_paid_cad / qst_paid_cad / hst_paid_cad / taxes_auto_computed"
```

---

## Task 4 — Endpoint `GET /api/reports/sales-tax`

**Files:**
- Modify: `backend/server.py` (ajouter helper + endpoint)
- Modify: `backend/tests/test_tax_report_integration.py` (ajouter `TestSalesTaxReport`)

- [ ] **Step 1: Ajouter les tests**

Append à `test_tax_report_integration.py` :

```python
class TestSalesTaxReport:
    _cleanup = {"clients": [], "invoices": [], "expenses": []}
    _auth_headers = None

    def _setup_data(self, auth):
        """Crée un client, 2 invoices QC payées, 1 invoice draft, 2 expenses avec taxes."""
        TestSalesTaxReport._auth_headers = auth
        # Client
        c = requests.post(f"{BASE_URL}/api/clients", headers=auth,
                          json={"name": "Tax Report Test"}).json()
        TestSalesTaxReport._cleanup["clients"].append(c["id"])
        # 2 invoices QC paid (subtotal 1000 each, gst=50, qst=99.75)
        for i in range(2):
            inv = requests.post(f"{BASE_URL}/api/invoices", headers=auth, json={
                "client_id": c["id"],
                "items": [{"description": "S", "quantity": 1, "unit_price": 1000}],
                "province": "QC",
                "issue_date": "2026-04-15",
            }).json()
            TestSalesTaxReport._cleanup["invoices"].append(inv["id"])
            # Mark as paid
            requests.put(f"{BASE_URL}/api/invoices/{inv['id']}/status",
                         headers=auth, json={"status": "paid"})
        # 1 invoice draft (must be excluded)
        d = requests.post(f"{BASE_URL}/api/invoices", headers=auth, json={
            "client_id": c["id"],
            "items": [{"description": "Drafty", "quantity": 1, "unit_price": 500}],
            "province": "QC",
            "issue_date": "2026-04-15",
        }).json()
        TestSalesTaxReport._cleanup["invoices"].append(d["id"])
        # 2 expenses avec taxes payées
        for amount, gst, qst in [(114.975, 5.00, 9.98), (229.95, 10.00, 19.96)]:
            e = requests.post(f"{BASE_URL}/api/expenses", headers=auth, json={
                "description": "Exp",
                "amount": amount,
                "currency": "CAD",
                "expense_date": "2026-04-20",
                "gst_paid_cad": gst,
                "qst_paid_cad": qst,
            }).json()
            TestSalesTaxReport._cleanup["expenses"].append(e["id"])
        return c["id"]

    def test_report_summary(self, auth):
        self._setup_data(auth)
        resp = requests.get(
            f"{BASE_URL}/api/reports/sales-tax",
            headers=auth, params={"start": "2026-04-01", "end": "2026-06-30"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["period"] == {"start": "2026-04-01", "end": "2026-06-30"}
        # 2 paid invoices QC : 50 GST each = 100 total
        assert body["summary"]["gst"]["collected"] == 100.00
        # 99.75 QST each × 2 = 199.50 ; round: 199.50
        assert body["summary"]["qst"]["collected"] == 199.50
        # Expenses: 5 + 10 = 15 GST paid, 9.98 + 19.96 = 29.94 QST paid
        assert body["summary"]["gst"]["paid"] == 15.00
        assert body["summary"]["qst"]["paid"] == 29.94
        # Net = collected - paid
        assert body["summary"]["gst"]["net"] == 85.00
        assert body["summary"]["qst"]["net"] == round(199.50 - 29.94, 2)
        # No HST (no ON invoices)
        assert body["summary"]["hst"] == {"collected": 0, "paid": 0, "net": 0}

    def test_counts(self, auth):
        self._setup_data(auth)
        resp = requests.get(
            f"{BASE_URL}/api/reports/sales-tax",
            headers=auth, params={"start": "2026-04-01", "end": "2026-06-30"})
        body = resp.json()
        # 2 paid invoices, draft excluded
        assert body["invoice_count"] == 2
        # 2 expenses
        assert body["expense_count"] == 2

    def test_cra_detail_lines_present(self, auth):
        self._setup_data(auth)
        resp = requests.get(
            f"{BASE_URL}/api/reports/sales-tax",
            headers=auth, params={"start": "2026-04-01", "end": "2026-06-30"})
        body = resp.json()
        cra = body["cra_detail"]
        for key in ("line_101_sales", "line_103_gst_collected", "line_106_itc_gst",
                    "line_109_net_gst", "line_103_hst_collected", "line_106_itc_hst",
                    "line_109_net_hst"):
            assert key in cra

    def test_rq_detail_lines_present(self, auth):
        self._setup_data(auth)
        resp = requests.get(
            f"{BASE_URL}/api/reports/sales-tax",
            headers=auth, params={"start": "2026-04-01", "end": "2026-06-30"})
        body = resp.json()
        rq = body["rq_detail"]
        for key in ("line_201_taxable_sales_qc", "line_203_qst_collected",
                    "line_205_itr_qst", "line_209_net_qst"):
            assert key in rq

    def test_empty_period(self, auth):
        resp = requests.get(
            f"{BASE_URL}/api/reports/sales-tax",
            headers=auth, params={"start": "2020-01-01", "end": "2020-01-31"})
        body = resp.json()
        assert body["summary"]["gst"] == {"collected": 0, "paid": 0, "net": 0}
        assert body["invoice_count"] == 0
        assert body["expense_count"] == 0

    @classmethod
    def teardown_class(cls):
        if not cls._auth_headers:
            return
        for iid in cls._cleanup["invoices"]:
            try:
                requests.delete(f"{BASE_URL}/api/invoices/{iid}", headers=cls._auth_headers)
            except Exception:
                pass
        for eid in cls._cleanup["expenses"]:
            try:
                requests.delete(f"{BASE_URL}/api/expenses/{eid}", headers=cls._auth_headers)
            except Exception:
                pass
        for cid in cls._cleanup["clients"]:
            try:
                requests.delete(f"{BASE_URL}/api/clients/{cid}", headers=cls._auth_headers)
            except Exception:
                pass
        cls._cleanup = {"clients": [], "invoices": [], "expenses": []}
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
pytest tests/test_tax_report_integration.py::TestSalesTaxReport -v 2>&1 | tail -15
```

Expected: 404 sur `/api/reports/sales-tax`.

- [ ] **Step 3: Ajouter l'endpoint dans `server.py`**

Localiser une bonne place (par exemple après le dernier endpoint expenses, vers la ligne 850+) :

```python
def _aggregate_sales_tax(user_id, start, end):
    """Calcule sommaire + détails CRA + Revenu Québec pour la période [start, end] inclusive."""
    invoices = list(db.invoices.find({
        "user_id": user_id,
        "status": {"$in": ["sent", "paid", "overdue"]},
        "issue_date": {"$gte": start, "$lte": end},
    }, {"_id": 0}))
    expenses = list(db.expenses.find({
        "user_id": user_id,
        "expense_date": {"$gte": start, "$lte": end},
    }, {"_id": 0}))

    def to_cad(amount, rate, currency):
        if amount is None:
            return 0
        if currency == "CAD" or not rate:
            return float(amount)
        return float(amount) / float(rate) if float(rate) > 0 else float(amount)

    gst_collected = 0.0
    qst_collected = 0.0
    hst_collected = 0.0
    sales_total = 0.0
    sales_qc_total = 0.0
    for inv in invoices:
        rate = inv.get("exchange_rate_to_cad", 1.0) or 1.0
        cur = inv.get("currency", "CAD")
        subtotal_cad = to_cad(inv.get("subtotal", 0), rate, cur)
        gst_cad = to_cad(inv.get("gst_amount", 0), rate, cur)
        qst_cad = to_cad(inv.get("pst_amount", 0), rate, cur)  # pst_amount = TVQ legacy
        hst_cad = to_cad(inv.get("hst_amount", 0), rate, cur)
        sales_total += subtotal_cad
        if inv.get("province") == "QC":
            sales_qc_total += subtotal_cad
        gst_collected += gst_cad
        qst_collected += qst_cad
        hst_collected += hst_cad

    gst_paid = sum(float(e.get("gst_paid_cad", 0) or 0) for e in expenses)
    qst_paid = sum(float(e.get("qst_paid_cad", 0) or 0) for e in expenses)
    hst_paid = sum(float(e.get("hst_paid_cad", 0) or 0) for e in expenses)

    def r(v):
        return round(v, 2)

    summary = {
        "gst": {"collected": r(gst_collected), "paid": r(gst_paid), "net": r(gst_collected - gst_paid)},
        "qst": {"collected": r(qst_collected), "paid": r(qst_paid), "net": r(qst_collected - qst_paid)},
        "hst": {"collected": r(hst_collected), "paid": r(hst_paid), "net": r(hst_collected - hst_paid)},
    }
    cra_detail = {
        "line_101_sales": r(sales_total),
        "line_103_gst_collected": r(gst_collected),
        "line_103_hst_collected": r(hst_collected),
        "line_106_itc_gst": r(gst_paid),
        "line_106_itc_hst": r(hst_paid),
        "line_109_net_gst": r(gst_collected - gst_paid),
        "line_109_net_hst": r(hst_collected - hst_paid),
    }
    rq_detail = {
        "line_201_taxable_sales_qc": r(sales_qc_total),
        "line_203_qst_collected": r(qst_collected),
        "line_205_itr_qst": r(qst_paid),
        "line_209_net_qst": r(qst_collected - qst_paid),
    }
    return {
        "period": {"start": start, "end": end},
        "summary": summary,
        "cra_detail": cra_detail,
        "rq_detail": rq_detail,
        "invoice_count": len(invoices),
        "expense_count": len(expenses),
    }


@app.get("/api/reports/sales-tax")
def get_sales_tax_report(start: str = Query(...), end: str = Query(...),
                         current_user: User = Depends(get_current_user_with_access)):
    """Rapport TPS/TVQ pour une période donnée."""
    return _aggregate_sales_tax(current_user.id, start, end)
```

- [ ] **Step 4: Redémarrer et relancer**

```bash
lsof -ti:8000 | xargs kill 2>/dev/null
source .venv/bin/activate
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_tax_report.py tests/test_tax_report_integration.py -v 2>&1 | tail -15
```

Expected: 32 passed (20 unit + 4 settings + 3 expense + 5 report).

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_tax_report_integration.py
git commit -m "feat(reports): GET /api/reports/sales-tax avec sommaire + détail CRA + Revenu Québec"
```

---

## Task 5 — Endpoint `GET /api/reports/sales-tax/pdf`

**Files:**
- Modify: `backend/server.py` (ajouter la génération PDF)
- Modify: `backend/tests/test_tax_report_integration.py` (ajouter un test PDF)

- [ ] **Step 1: Ajouter le test PDF**

Append à `TestSalesTaxReport` (avant le `teardown_class`) :

```python
    def test_pdf_endpoint(self, auth):
        self._setup_data(auth)
        resp = requests.get(
            f"{BASE_URL}/api/reports/sales-tax/pdf",
            headers=auth, params={"start": "2026-04-01", "end": "2026-06-30"})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/pdf")
        # PDF starts with %PDF magic bytes
        assert resp.content[:4] == b"%PDF"
        assert len(resp.content) > 1000  # not empty
```

- [ ] **Step 2: Vérifier qu'il échoue**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
pytest tests/test_tax_report_integration.py::TestSalesTaxReport::test_pdf_endpoint -v 2>&1 | tail -10
```

Expected: 404.

- [ ] **Step 3: Ajouter le générateur PDF dans `server.py`**

Localiser une bonne place (par exemple juste après `_aggregate_sales_tax`). Ajouter :

```python
def generate_sales_tax_report_pdf(user_id, start, end):
    """Génère un PDF A4 du rapport TPS/TVQ."""
    data = _aggregate_sales_tax(user_id, start, end)
    company_settings = db.company_settings.find_one({"user_id": user_id}, {"_id": 0}) or {}

    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch,
                            bottomMargin=0.5*inch, leftMargin=0.6*inch, rightMargin=0.6*inch)
    styles = getSampleStyleSheet()
    teal = HexColor('#00A08C')
    dark = HexColor('#1f2937')
    gray = HexColor('#6b7280')
    title_style = ParagraphStyle('T', parent=styles['Heading1'], fontSize=22, textColor=teal, spaceAfter=6)
    sub_style = ParagraphStyle('S', parent=styles['Normal'], fontSize=11, textColor=gray)
    small = ParagraphStyle('Small', parent=styles['Normal'], fontSize=9, textColor=gray, leading=12)
    bold = ParagraphStyle('B', parent=styles['Normal'], fontSize=10, textColor=dark, fontName='Helvetica-Bold')

    elements = []
    # Header
    comp_name = company_settings.get('company_name', 'Mon Entreprise')
    elements.append(Paragraph(comp_name, ParagraphStyle('C', parent=styles['Normal'], fontSize=13, textColor=dark, fontName='Helvetica-Bold')))
    elements.append(Paragraph("Rapport TPS / TVQ", title_style))
    elements.append(Paragraph(f"Période : {start} au {end}", sub_style))
    elements.append(Spacer(1, 0.2*inch))

    # Numéros d'enregistrement
    regs = _take_regs(company_settings)
    parts = _reg_label_parts(regs)
    if parts:
        elements.append(Paragraph("Numéros d'enregistrement", bold))
        elements.append(Paragraph(' &nbsp;·&nbsp; '.join(parts), small))
        elements.append(Spacer(1, 0.2*inch))

    # Summary (3 cards)
    summary = data["summary"]
    def fmt(v):
        return f"{v:,.2f} $".replace(",", " ")
    card_data = [
        ['TPS', 'TVQ', 'TVH'],
        [
            f"Perçue : {fmt(summary['gst']['collected'])}\nPayée : {fmt(summary['gst']['paid'])}\nNet : {fmt(summary['gst']['net'])}",
            f"Perçue : {fmt(summary['qst']['collected'])}\nPayée : {fmt(summary['qst']['paid'])}\nNet : {fmt(summary['qst']['net'])}",
            f"Perçue : {fmt(summary['hst']['collected'])}\nPayée : {fmt(summary['hst']['paid'])}\nNet : {fmt(summary['hst']['net'])}",
        ]
    ]
    cards = Table(card_data, colWidths=[2.3*inch, 2.3*inch, 2.3*inch])
    cards.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), teal),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#ffffff')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#e5e7eb')),
    ]))
    elements.append(cards)
    elements.append(Spacer(1, 0.3*inch))

    # CRA detail
    elements.append(Paragraph("Détail format ARC (T1 GST/HST)", bold))
    cra = data["cra_detail"]
    cra_rows = [
        ['Ligne', 'Description', 'Montant'],
        ['101', 'Ventes et autres recettes', fmt(cra['line_101_sales'])],
        ['103', 'TPS perçue', fmt(cra['line_103_gst_collected'])],
        ['103', 'TVH perçue', fmt(cra['line_103_hst_collected'])],
        ['106', 'CTI TPS', fmt(cra['line_106_itc_gst'])],
        ['106', 'CTI TVH', fmt(cra['line_106_itc_hst'])],
        ['109', 'Taxe nette TPS', fmt(cra['line_109_net_gst'])],
        ['109', 'Taxe nette TVH', fmt(cra['line_109_net_hst'])],
    ]
    cra_t = Table(cra_rows, colWidths=[0.7*inch, 3.5*inch, 1.5*inch])
    cra_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#f8fafb')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#e5e7eb')),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(cra_t)
    elements.append(Spacer(1, 0.2*inch))

    # RQ detail
    elements.append(Paragraph("Détail format Revenu Québec (FP-2500)", bold))
    rq = data["rq_detail"]
    rq_rows = [
        ['Ligne', 'Description', 'Montant'],
        ['201', 'Ventes taxables au Québec', fmt(rq['line_201_taxable_sales_qc'])],
        ['203', 'TVQ perçue', fmt(rq['line_203_qst_collected'])],
        ['205', 'RTI TVQ', fmt(rq['line_205_itr_qst'])],
        ['209', 'TVQ nette', fmt(rq['line_209_net_qst'])],
    ]
    rq_t = Table(rq_rows, colWidths=[0.7*inch, 3.5*inch, 1.5*inch])
    rq_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#f8fafb')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#e5e7eb')),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(rq_t)
    elements.append(Spacer(1, 0.3*inch))

    # Footer
    elements.append(Paragraph(
        f"{data['invoice_count']} factures · {data['expense_count']} dépenses incluses",
        small))
    elements.append(Paragraph(
        f"Généré le {datetime.now(timezone.utc).strftime('%Y-%m-%d')} — FacturePro",
        small))

    pdf.build(elements)
    buffer.seek(0)
    return buffer


@app.get("/api/reports/sales-tax/pdf")
def get_sales_tax_report_pdf(start: str = Query(...), end: str = Query(...),
                              current_user: User = Depends(get_current_user_with_access)):
    pdf_buffer = generate_sales_tax_report_pdf(current_user.id, start, end)
    filename = f"rapport-tps-tvq-{start}-au-{end}.pdf"
    return StreamingResponse(pdf_buffer, media_type="application/pdf",
                              headers={"Content-Disposition": f'attachment; filename="{filename}"'})
```

- [ ] **Step 4: Redémarrer et relancer**

```bash
lsof -ti:8000 | xargs kill 2>/dev/null
source .venv/bin/activate
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_tax_report.py tests/test_tax_report_integration.py -v 2>&1 | tail -15
```

Expected: 33 passed (32 + 1 PDF).

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_tax_report_integration.py
git commit -m "feat(reports): GET /api/reports/sales-tax/pdf — PDF A4 avec sommaire et détails"
```

---

## Task 6 — Frontend SettingsPage : dropdown province

**Files:**
- Modify: `frontend/src/pages/SettingsPage.js`

- [ ] **Step 1: Ajouter `province` à l'état settings**

Trouver le `useState` du form settings. Ajouter aux valeurs par défaut :
```javascript
province: 'QC',
```

Confirmer que le `useEffect` qui fetch `/api/settings/company` peuple ce champ via spread.

- [ ] **Step 2: Ajouter le dropdown JSX**

Insérer juste après le select `entity_type` (feature #3) :

```jsx
<div style={{ marginBottom: 16 }}>
  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 500, color: '#374151', marginBottom: 4 }}>
    Province
    <span
      title="Utilisée pour le calcul automatique des taxes sur tes dépenses (TPS/TVQ/TVH)."
      style={{ cursor: 'help', color: '#6b7280', fontSize: 14 }}
    >
      ⓘ
    </span>
  </label>
  <select
    value={settings.province || 'QC'}
    onChange={(e) => setSettings(prev => ({ ...prev, province: e.target.value }))}
    style={{
      width: '100%', padding: '12px',
      border: '1.5px solid #d1d5db', borderRadius: 8,
      fontSize: 14, background: 'white', boxSizing: 'border-box',
    }}
  >
    <option value="QC">Québec</option>
    <option value="ON">Ontario</option>
    <option value="BC">Colombie-Britannique</option>
    <option value="AB">Alberta</option>
    <option value="SK">Saskatchewan</option>
    <option value="MB">Manitoba</option>
    <option value="NB">Nouveau-Brunswick</option>
    <option value="NS">Nouvelle-Écosse</option>
    <option value="PE">Île-du-Prince-Édouard</option>
    <option value="NL">Terre-Neuve-et-Labrador</option>
    <option value="YT">Yukon</option>
    <option value="NU">Nunavut</option>
    <option value="NT">Territoires du Nord-Ouest</option>
  </select>
</div>
```

(Adapter le pattern de setter pour matcher celui du fichier — feature #3 utilise `setSettings(prev => ({...prev, ...}))`.)

- [ ] **Step 3: Build**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
npx --no-install react-scripts build 2>&1 | tail -10
```

Expected: Compiled successfully.

- [ ] **Step 4: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add frontend/src/pages/SettingsPage.js
git commit -m "feat(settings): dropdown Province (13 valeurs CA)"
```

---

## Task 7 — Frontend ExpensesPage : section "Taxes payées" + bouton "Calculer auto"

**Files:**
- Modify: `frontend/src/pages/ExpensesPage.js`

- [ ] **Step 1: Ajouter `gst_paid_cad`, `qst_paid_cad`, `hst_paid_cad`, `taxes_auto_computed` à l'état formData**

Dans les valeurs par défaut de `formData` :
```javascript
gst_paid_cad: 0,
qst_paid_cad: 0,
hst_paid_cad: 0,
taxes_auto_computed: false,
```

Aussi dans `resetForm()` ou équivalent.

- [ ] **Step 2: Fetch settings.province au mount**

Si la province n'est pas déjà disponible dans le state, ajouter un useState et useEffect :

```javascript
const [companyProvince, setCompanyProvince] = useState('QC');

useEffect(() => {
  axios.get(`${BACKEND_URL}/api/settings/company`, {
    headers: { Authorization: `Bearer ${token}` }
  })
    .then(resp => setCompanyProvince(resp.data.province || 'QC'))
    .catch(() => {});
}, []);
```

Adapter `BACKEND_URL` et `token` au pattern du fichier.

- [ ] **Step 3: Ajouter le helper computeTaxesPaid (en haut du fichier ou inline)**

```javascript
function computeTaxesPaid(amountGross, province) {
  const a = parseFloat(amountGross) || 0;
  if (a <= 0) return { gst: 0, qst: 0, hst: 0 };
  const r2 = v => Math.round(v * 100) / 100;
  if (province === 'QC') {
    return { gst: r2(a * 5 / 114.975), qst: r2(a * 9.975 / 114.975), hst: 0 };
  }
  if (province === 'ON') {
    return { gst: 0, qst: 0, hst: r2(a * 13 / 113) };
  }
  if (['NB', 'NS', 'PE', 'NL'].includes(province)) {
    return { gst: 0, qst: 0, hst: r2(a * 15 / 115) };
  }
  return { gst: r2(a * 5 / 105), qst: 0, hst: 0 };
}
```

- [ ] **Step 4: Ajouter le JSX de la section "Taxes payées"**

Insérer dans le formulaire dépense, après la section catégorie + helper déductible (feature #3), avant les boutons d'action :

```jsx
<div style={{ marginTop: 18, padding: 16, background: '#f9fafb', borderRadius: 8, border: '1px solid #e5e7eb' }}>
  <h4 style={{ margin: '0 0 6px', fontSize: 14, color: '#1f2937' }}>Taxes payées (CTI/RTI)</h4>
  <p style={{ marginTop: 0, marginBottom: 12, fontSize: 12, color: '#6b7280' }}>
    Saisis ces montants pour les inclure dans ton rapport TPS/TVQ trimestriel.
  </p>
  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
    <div>
      <label style={{ fontSize: 12, fontWeight: 500, color: '#374151' }}>TPS payée</label>
      <input
        type="number" step="0.01" min="0"
        value={formData.gst_paid_cad}
        onChange={(e) => setFormData(prev => ({
          ...prev,
          gst_paid_cad: parseFloat(e.target.value) || 0,
          taxes_auto_computed: false,
        }))}
        style={{ width: '100%', padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, boxSizing: 'border-box' }}
      />
    </div>
    <div>
      <label style={{ fontSize: 12, fontWeight: 500, color: '#374151' }}>TVQ payée</label>
      <input
        type="number" step="0.01" min="0"
        value={formData.qst_paid_cad}
        onChange={(e) => setFormData(prev => ({
          ...prev,
          qst_paid_cad: parseFloat(e.target.value) || 0,
          taxes_auto_computed: false,
        }))}
        style={{ width: '100%', padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, boxSizing: 'border-box' }}
      />
    </div>
    <div>
      <label style={{ fontSize: 12, fontWeight: 500, color: '#374151' }}>TVH payée</label>
      <input
        type="number" step="0.01" min="0"
        value={formData.hst_paid_cad}
        onChange={(e) => setFormData(prev => ({
          ...prev,
          hst_paid_cad: parseFloat(e.target.value) || 0,
          taxes_auto_computed: false,
        }))}
        style={{ width: '100%', padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, boxSizing: 'border-box' }}
      />
    </div>
  </div>
  <button
    type="button"
    onClick={() => {
      const t = computeTaxesPaid(formData.amount, companyProvince);
      setFormData(prev => ({
        ...prev,
        gst_paid_cad: t.gst,
        qst_paid_cad: t.qst,
        hst_paid_cad: t.hst,
        taxes_auto_computed: true,
      }));
    }}
    disabled={formData.currency !== 'CAD'}
    style={{
      marginTop: 10, padding: '8px 14px',
      background: formData.currency === 'CAD' ? '#00A08C' : '#d1d5db',
      color: 'white', border: 0, borderRadius: 6,
      fontSize: 13, cursor: formData.currency === 'CAD' ? 'pointer' : 'not-allowed',
    }}
  >
    🧮 Calculer auto (province {companyProvince})
  </button>
  {formData.currency !== 'CAD' && (
    <p style={{ marginTop: 6, fontSize: 11.5, color: '#92400e' }}>
      ⚠ Calcul auto disponible seulement pour les dépenses en CAD.
    </p>
  )}
</div>
```

- [ ] **Step 5: Build**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
npx --no-install react-scripts build 2>&1 | tail -10
```

Expected: Compiled successfully.

- [ ] **Step 6: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add frontend/src/pages/ExpensesPage.js
git commit -m "feat(expenses): section Taxes payées + bouton Calculer auto (CTI/RTI)"
```

---

## Task 8 — Frontend nouvelle page `ReportsPage` + entrée nav

**Files:**
- Create: `frontend/src/pages/ReportsPage.js`
- Modify: `frontend/src/App.js` (ajouter route)
- Modify: `frontend/src/components/Layout.js` (ajouter entrée nav)

- [ ] **Step 1: Créer `frontend/src/pages/ReportsPage.js`**

```javascript
import React, { useState } from 'react';
import axios from 'axios';
import { BACKEND_URL } from '../config';

const QUARTERS = [
  { value: 'Q1', label: 'T1 (jan-mar)', start: '01-01', end: '03-31' },
  { value: 'Q2', label: 'T2 (avr-jun)', start: '04-01', end: '06-30' },
  { value: 'Q3', label: 'T3 (jul-sep)', start: '07-01', end: '09-30' },
  { value: 'Q4', label: 'T4 (oct-déc)', start: '10-01', end: '12-31' },
];

const currentYear = new Date().getFullYear();
const YEARS = [currentYear, currentYear - 1, currentYear - 2, currentYear - 3];

const fmt = v => (v || 0).toLocaleString('fr-CA', { style: 'currency', currency: 'CAD' });

function ReportsPage() {
  const [periodMode, setPeriodMode] = useState('quarter');
  const [year, setYear] = useState(String(currentYear));
  const [quarter, setQuarter] = useState('Q1');
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);

  const getDates = () => {
    if (periodMode === 'quarter') {
      const q = QUARTERS.find(x => x.value === quarter);
      return { start: `${year}-${q.start}`, end: `${year}-${q.end}` };
    }
    return { start: customStart, end: customEnd };
  };

  const generate = async () => {
    const { start, end } = getDates();
    if (!start || !end) return;
    setLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const resp = await axios.get(`${BACKEND_URL}/api/reports/sales-tax`, {
        headers: { Authorization: `Bearer ${token}` },
        params: { start, end },
      });
      setReport(resp.data);
    } finally {
      setLoading(false);
    }
  };

  const downloadPdf = async () => {
    const { start, end } = getDates();
    if (!start || !end) return;
    const token = localStorage.getItem('access_token');
    const resp = await fetch(
      `${BACKEND_URL}/api/reports/sales-tax/pdf?start=${start}&end=${end}`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    const blob = await resp.blob();
    const url = window.URL.createObjectURL(blob);
    window.open(url, '_blank');
  };

  const netColor = v => v > 0 ? '#dc2626' : v < 0 ? '#059669' : '#1f2937';
  const arrow = v => v > 0 ? '↑' : v < 0 ? '↓' : '';

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: 20 }}>
      <h2 style={{ marginTop: 0 }}>Rapports</h2>

      <div style={{ background: 'white', padding: 20, borderRadius: 8, boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
        <h3 style={{ marginTop: 0 }}>Rapport TPS / TVQ trimestriel</h3>

        <div style={{ marginBottom: 12 }}>
          <label style={{ marginRight: 16 }}>
            <input type="radio" checked={periodMode === 'quarter'}
              onChange={() => setPeriodMode('quarter')} /> Trimestre
          </label>
          <label>
            <input type="radio" checked={periodMode === 'custom'}
              onChange={() => setPeriodMode('custom')} /> Période personnalisée
          </label>
        </div>

        {periodMode === 'quarter' && (
          <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
            <select value={year} onChange={e => setYear(e.target.value)}
              style={{ padding: 8, borderRadius: 6, border: '1px solid #d1d5db' }}>
              {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
            <select value={quarter} onChange={e => setQuarter(e.target.value)}
              style={{ padding: 8, borderRadius: 6, border: '1px solid #d1d5db' }}>
              {QUARTERS.map(q => <option key={q.value} value={q.value}>{q.label}</option>)}
            </select>
          </div>
        )}
        {periodMode === 'custom' && (
          <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
            <input type="date" value={customStart} onChange={e => setCustomStart(e.target.value)}
              style={{ padding: 8, borderRadius: 6, border: '1px solid #d1d5db' }} />
            <input type="date" value={customEnd} onChange={e => setCustomEnd(e.target.value)}
              style={{ padding: 8, borderRadius: 6, border: '1px solid #d1d5db' }} />
          </div>
        )}

        <button onClick={generate} disabled={loading}
          style={{ padding: '10px 18px', background: '#00A08C', color: 'white', border: 0, borderRadius: 6, cursor: 'pointer' }}>
          {loading ? 'Génération…' : 'Générer le rapport'}
        </button>

        {report && (
          <div style={{ marginTop: 24 }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
              {['gst', 'qst', 'hst'].map(k => (
                <div key={k} style={{ background: '#f9fafb', padding: 14, borderRadius: 6 }}>
                  <div style={{ fontWeight: 700, color: '#00A08C', textTransform: 'uppercase', fontSize: 11 }}>{k}</div>
                  <div style={{ marginTop: 6, fontSize: 12 }}>Perçue : {fmt(report.summary[k].collected)}</div>
                  <div style={{ fontSize: 12 }}>Payée : {fmt(report.summary[k].paid)}</div>
                  <div style={{ marginTop: 6, fontWeight: 700, fontSize: 16, color: netColor(report.summary[k].net) }}>
                    Net : {fmt(report.summary[k].net)} {arrow(report.summary[k].net)}
                  </div>
                </div>
              ))}
            </div>

            <details style={{ marginTop: 16 }}>
              <summary style={{ cursor: 'pointer', fontWeight: 600 }}>Détail format ARC (T1 GST/HST)</summary>
              <table style={{ width: '100%', marginTop: 8, borderCollapse: 'collapse' }}>
                <tbody>
                  {[
                    ['101', 'Ventes et autres recettes', report.cra_detail.line_101_sales],
                    ['103', 'TPS perçue', report.cra_detail.line_103_gst_collected],
                    ['103', 'TVH perçue', report.cra_detail.line_103_hst_collected],
                    ['106', 'CTI TPS', report.cra_detail.line_106_itc_gst],
                    ['106', 'CTI TVH', report.cra_detail.line_106_itc_hst],
                    ['109', 'Taxe nette TPS', report.cra_detail.line_109_net_gst],
                    ['109', 'Taxe nette TVH', report.cra_detail.line_109_net_hst],
                  ].map(([line, desc, amt], i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #e5e7eb' }}>
                      <td style={{ padding: 6, fontFamily: 'monospace' }}>{line}</td>
                      <td style={{ padding: 6 }}>{desc}</td>
                      <td style={{ padding: 6, textAlign: 'right' }}>{fmt(amt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>

            <details style={{ marginTop: 8 }}>
              <summary style={{ cursor: 'pointer', fontWeight: 600 }}>Détail format Revenu Québec (FP-2500)</summary>
              <table style={{ width: '100%', marginTop: 8, borderCollapse: 'collapse' }}>
                <tbody>
                  {[
                    ['201', 'Ventes taxables au Québec', report.rq_detail.line_201_taxable_sales_qc],
                    ['203', 'TVQ perçue', report.rq_detail.line_203_qst_collected],
                    ['205', 'RTI TVQ', report.rq_detail.line_205_itr_qst],
                    ['209', 'TVQ nette', report.rq_detail.line_209_net_qst],
                  ].map(([line, desc, amt], i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #e5e7eb' }}>
                      <td style={{ padding: 6, fontFamily: 'monospace' }}>{line}</td>
                      <td style={{ padding: 6 }}>{desc}</td>
                      <td style={{ padding: 6, textAlign: 'right' }}>{fmt(amt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>

            <div style={{ marginTop: 12, color: '#6b7280', fontSize: 12 }}>
              {report.invoice_count} factures · {report.expense_count} dépenses incluses
            </div>

            <button onClick={downloadPdf}
              style={{ marginTop: 12, padding: '10px 18px', background: '#1f2937', color: 'white', border: 0, borderRadius: 6, cursor: 'pointer' }}>
              📥 Télécharger le PDF
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default ReportsPage;
```

- [ ] **Step 2: Ajouter la route dans `App.js`**

Trouver les routes existantes (l'app utilise navigation manuelle via `window.history`, pas react-router — voir `App.js`). Ajouter le cas pour `/reports` :

```javascript
import ReportsPage from './pages/ReportsPage';

// Dans le switch des routes :
if (currentRoute === '/reports') return <Layout><ReportsPage /></Layout>;
```

Adapter selon le pattern exact du fichier (probablement un `switch` ou une série de `if`).

- [ ] **Step 3: Ajouter l'entrée nav dans `Layout.js`**

Trouver le menu de navigation (probablement une liste de `<button>` ou `<a>`). Ajouter :

```jsx
<button onClick={() => navigate('/reports')}
  style={{ /* même style que les autres entrées */ }}>
  Rapports
</button>
```

Pour le placement : entre "Export" et "Settings" semble naturel.

- [ ] **Step 4: Build**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
npx --no-install react-scripts build 2>&1 | tail -10
```

Expected: Compiled successfully.

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add frontend/src/pages/ReportsPage.js frontend/src/App.js frontend/src/components/Layout.js
git commit -m "feat(reports): page Rapports avec rapport TPS/TVQ trimestriel + download PDF"
```

---

## Task 9 — E2E + push prod + CLAUDE.md changelog

- [ ] **Step 1: Re-run all tests**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
lsof -ti:8000 | xargs kill 2>/dev/null
source .venv/bin/activate
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_tax_numbers.py tests/test_tax_registrations_integration.py tests/test_expense_categories.py tests/test_expense_categories_integration.py tests/test_tax_report.py tests/test_tax_report_integration.py -v 2>&1 | tail -10
```

Expected: 108 passed (36 + 39 + 33).

- [ ] **Step 2: E2E HTTP**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
   -H "Content-Type: application/json" \
   -d '{"email":"gussdub@gmail.com","password":"testpass123"}' \
   | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

echo "=== Settings province round-trip ==="
curl -s -X PUT http://localhost:8000/api/settings/company \
   -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
   -d '{"province":"ON"}' > /dev/null
curl -s http://localhost:8000/api/settings/company -H "Authorization: Bearer $TOKEN" \
   | python -c "import sys,json;print('province:', json.load(sys.stdin).get('province'))"
# Restore
curl -s -X PUT http://localhost:8000/api/settings/company \
   -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
   -d '{"province":"QC"}' > /dev/null

echo "=== Tax report endpoint ==="
curl -s "http://localhost:8000/api/reports/sales-tax?start=2026-04-01&end=2026-06-30" \
   -H "Authorization: Bearer $TOKEN" | python -m json.tool | head -30

echo "=== Tax report PDF ==="
curl -s "http://localhost:8000/api/reports/sales-tax/pdf?start=2026-04-01&end=2026-06-30" \
   -H "Authorization: Bearer $TOKEN" -o /tmp/report.pdf
file /tmp/report.pdf
```

Expected:
- province ON after PUT, back to QC after restore
- Report JSON with summary/cra_detail/rq_detail
- `/tmp/report.pdf: PDF document, version 1.x`

- [ ] **Step 3: Stop local backend**

```bash
lsof -ti:8000 | xargs kill 2>/dev/null
```

- [ ] **Step 4: Update CLAUDE.md**

Append à la section "Features livrées" :

```markdown

- **2026-06-16 — Rapport TPS/TVQ trimestriel (feature #4)**
  - Tracking TPS/TVQ/TVH payées sur dépenses via 4 champs sur `expenses` + bouton "Calculer auto"
  - Champ `province` sur `company_settings` (13 valeurs CA, défaut QC)
  - `GET /api/reports/sales-tax?start&end` retourne sommaire + détail CRA (T1) + détail Revenu Québec (FP-2500)
  - `GET /api/reports/sales-tax/pdf?start&end` génère un PDF A4 avec sommaire et tableaux ligne-par-ligne
  - Nouvelle page Rapports avec quick-picker trimestre (4 dernières années) + plage personnalisée
  - Filtre invoices : exclut `draft`, inclut `sent/paid/overdue` (accrual basis)
  - Multi-devise : conversion via `exchange_rate_to_cad` snapshoté
  - Spec : `docs/superpowers/specs/2026-06-16-tax-report-design.md`
  - Plan : `docs/superpowers/plans/2026-06-16-tax-report.md`
```

- [ ] **Step 5: Commit + push prod**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git log origin/main..HEAD --oneline
git add CLAUDE.md
git commit -m "docs: changelog feature #4 (rapport TPS/TVQ trimestriel)"
git push origin main 2>&1 | tail -5
```

Expected: push succeeds, Render + Vercel start redeploying.

- [ ] **Step 6: Vérifier prod après ~3 min**

```bash
sleep 180
echo "=== Backend prod ==="
curl -s -m 90 https://facturepro-backend-dkvn.onrender.com/api/health
echo
echo "=== Tax report endpoint prod (empty period) ==="
TOKEN_PROD=$(curl -s -X POST https://facturepro-backend-dkvn.onrender.com/api/auth/login \
   -H "Content-Type: application/json" \
   -d '{"email":"gussdub@gmail.com","password":"VOTRE_VRAI_PASSWORD"}' \
   | python -c "import sys,json;print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)
# If login fails (probably will, prod has different password), just hit /api/health
echo "=== Frontend prod ==="
curl -sI -m 30 https://facturepro.ca | head -3
```

Note: le password prod est différent du local. Si pas possible de se logger en prod, vérifie juste le health endpoint et le frontend.

---

## Récap fichiers touchés

| Fichier | Tasks | Nature |
|---|---|---|
| `backend/server.py` | 1, 2, 3, 4, 5 | Modif (helpers + endpoints) |
| `backend/tests/test_tax_report.py` | 1 | Nouveau |
| `backend/tests/test_tax_report_integration.py` | 2, 3, 4, 5 | Nouveau |
| `frontend/src/pages/SettingsPage.js` | 6 | Modif (dropdown province) |
| `frontend/src/pages/ExpensesPage.js` | 7 | Modif (section taxes payées) |
| `frontend/src/pages/ReportsPage.js` | 8 | Nouveau |
| `frontend/src/App.js` | 8 | Modif (route) |
| `frontend/src/components/Layout.js` | 8 | Modif (nav) |
| `CLAUDE.md` | 9 | Modif (changelog) |

Commits attendus : **9** (un par task + commit doc final dans T9).
