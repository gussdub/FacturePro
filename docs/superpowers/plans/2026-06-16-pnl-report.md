# P&L Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Générer un état des résultats simplifié (P&L) : revenus, dépenses par catégorie ARC + sous-totaux par groupe, brut + déductible côte à côte, deux nets distincts (gestion / imposable), avec base accrual/cash, comparaison configurable, web + PDF.

**Architecture:** Aucun nouveau champ DB — tout exploite les données existantes des features #3 (catégories + `deductible_amount`) et #4 (filtres par status). Le backend ajoute 4 helpers (`_compute_compare_period`, `_pct_delta`, `_aggregate_pnl`, `_merge_expense_groups`) et 2 endpoints (JSON + PDF). Le frontend convertit ReportsPage en onglets et ajoute un composant `PnlReportSection`.

**Tech Stack:** FastAPI Python 3.11 + pymongo, React 18 CRA, pytest, ReportLab.

**Spec source:** [docs/superpowers/specs/2026-06-16-pnl-report-design.md](../specs/2026-06-16-pnl-report-design.md)

---

## File Structure

**Created:**
- `backend/tests/test_pnl_report.py` — tests unitaires des helpers (~140 lignes)
- `backend/tests/test_pnl_report_integration.py` — tests intégration HTTP (~200 lignes)

**Modified:**
- `backend/server.py` — 4 helpers (~120 lignes) + 2 endpoints (~50 lignes JSON + ~140 lignes PDF gen)
- `frontend/src/pages/ReportsPage.js` — conversion en onglets (sales_tax + pnl) + nouveau composant `PnlReportSection` (~250 lignes ajoutées)
- `CLAUDE.md` — changelog feature (~10 lignes)

---

## Task 1 — Helpers `_compute_compare_period` et `_pct_delta`

**Files:**
- Create: `backend/tests/test_pnl_report.py`
- Modify: `backend/server.py` (ajouter après les helpers de feature #4 `_compute_taxes_paid` et `_quarter_to_dates`)

- [ ] **Step 1: Écrire les tests**

Créer `backend/tests/test_pnl_report.py` :

```python
"""Tests unitaires pour le rapport P&L (feature #5)."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "facturepro_test_unit")
os.environ.setdefault("JWT_SECRET", "test")

from server import _compute_compare_period, _pct_delta


class TestComputeComparePeriod:
    def test_none_returns_none(self):
        assert _compute_compare_period("2026-04-01", "2026-06-30", "none") is None

    def test_invalid_mode_returns_none(self):
        assert _compute_compare_period("2026-04-01", "2026-06-30", "garbage") is None

    def test_previous_q2_to_q1(self):
        # Q2 2026 = 91 jours (avr-jun). Précédent = 91 jours avant 1er avril.
        result = _compute_compare_period("2026-04-01", "2026-06-30", "previous")
        # 2026-04-01 minus 1 day = 2026-03-31. Minus 90 more = 2026-01-01.
        assert result == ("2026-01-01", "2026-03-31")

    def test_previous_single_day(self):
        result = _compute_compare_period("2026-06-15", "2026-06-15", "previous")
        assert result == ("2026-06-14", "2026-06-14")

    def test_prior_year(self):
        assert _compute_compare_period("2026-04-01", "2026-06-30", "prior_year") == \
            ("2025-04-01", "2025-06-30")

    def test_prior_year_leap_day(self):
        # 2024-02-29 → 2023-02-28 (clamp)
        result = _compute_compare_period("2024-02-29", "2024-02-29", "prior_year")
        assert result == ("2023-02-28", "2023-02-28")

    def test_invalid_date_returns_none(self):
        assert _compute_compare_period("not-a-date", "2026-06-30", "previous") is None
        assert _compute_compare_period("2026-06-30", "also-bad", "prior_year") is None


class TestPctDelta:
    def test_positive_growth(self):
        assert _pct_delta(100, 120) == 20.0

    def test_negative_growth(self):
        assert _pct_delta(100, 80) == -20.0

    def test_no_change(self):
        assert _pct_delta(100, 100) == 0.0

    def test_zero_previous_nonzero_current(self):
        # On considère 100 % (cap raisonnable, pas inf)
        assert _pct_delta(0, 50) == 100.0

    def test_zero_previous_zero_current(self):
        assert _pct_delta(0, 0) == 0.0

    def test_negative_previous(self):
        # Cas pathologique mais ne doit pas crasher
        assert isinstance(_pct_delta(-50, 100), float)
```

- [ ] **Step 2: Vérifier l'échec**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
pytest tests/test_pnl_report.py -v 2>&1 | tail -10
```

Expected: `ImportError`.

- [ ] **Step 3: Implémenter dans `server.py`**

Dans `backend/server.py`, repérer où sont les helpers de feature #4 (`_compute_taxes_paid`, `_quarter_to_dates`, autour de la ligne ~228). Ajouter immédiatement après :

```python
# ─── P&L report helpers (feature #5 du spec pnl-report) ───

from datetime import date, timedelta


def _parse_date(s):
    """YYYY-MM-DD → date. Retourne None si invalide."""
    try:
        y, m, d = map(int, s.split("-"))
        return date(y, m, d)
    except Exception:
        return None


def _compute_compare_period(start, end, mode):
    """Retourne (start, end) de la période de comparaison, ou None si mode == 'none'
    ou si les dates sont invalides.

    - mode='previous'   : fenêtre de même durée juste avant start.
    - mode='prior_year' : même fenêtre, année précédente (clamp 29 février).
    """
    if mode == "none":
        return None
    s = _parse_date(start)
    e = _parse_date(end)
    if not s or not e:
        return None
    if mode == "previous":
        delta = (e - s).days
        new_e = s - timedelta(days=1)
        new_s = new_e - timedelta(days=delta)
        return (new_s.isoformat(), new_e.isoformat())
    if mode == "prior_year":
        def _shift_year(d):
            try:
                return d.replace(year=d.year - 1)
            except ValueError:
                # 29 février → 28 février année non-bissextile
                return d.replace(year=d.year - 1, day=28)
        return (_shift_year(s).isoformat(), _shift_year(e).isoformat())
    return None


def _pct_delta(previous, current):
    """Pourcentage de variation. Convention : si previous == 0 et current != 0 → 100 %.
    Si les deux sont 0, retourne 0. Arrondi à 1 décimale."""
    if previous == 0:
        return 0.0 if current == 0 else 100.0
    return round((current - previous) / previous * 100, 1)
```

Vérifier que `date`, `timedelta` ne sont pas déjà importés ailleurs ; sinon utiliser l'import local comme ci-dessus.

- [ ] **Step 4: Vérifier le succès**

```bash
pytest tests/test_pnl_report.py -v 2>&1 | tail -15
```

Expected: **13 passed** (7 compare + 6 pct).

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_pnl_report.py
git commit -m "feat(pnl): helpers _compute_compare_period + _pct_delta + _parse_date"
```

---

## Task 2 — Helper `_aggregate_pnl`

**Files:**
- Modify: `backend/server.py`
- Modify: `backend/tests/test_pnl_report.py` (ajouter classe `TestAggregatePnl`)

- [ ] **Step 1: Préparer un test d'intégration avec la vraie DB**

Vu que `_aggregate_pnl` lit `db.invoices` et `db.expenses`, on le teste mieux en intégration. Ajouter à `backend/tests/test_pnl_report.py` :

```python
import pytest
from pymongo import MongoClient
import uuid


@pytest.fixture
def isolated_db():
    """DB isolée pour tester _aggregate_pnl avec données contrôlées."""
    client = MongoClient("mongodb://localhost:27017")
    db_name = f"facturepro_test_pnl_{uuid.uuid4().hex[:8]}"
    yield client[db_name]
    client.drop_database(db_name)


def _seed_for_aggregate(test_db, user_id):
    """Seed : 2 invoices paid, 1 invoice sent, 1 invoice draft + 3 expenses dans 3 catégories."""
    test_db.invoices.insert_many([
        {"id": "i1", "user_id": user_id, "subtotal": 1000, "currency": "CAD",
         "exchange_rate_to_cad": 1.0, "status": "paid", "issue_date": "2099-04-15"},
        {"id": "i2", "user_id": user_id, "subtotal": 2000, "currency": "CAD",
         "exchange_rate_to_cad": 1.0, "status": "paid", "issue_date": "2099-05-10"},
        {"id": "i3", "user_id": user_id, "subtotal": 500, "currency": "CAD",
         "exchange_rate_to_cad": 1.0, "status": "sent", "issue_date": "2099-06-01"},
        {"id": "i4", "user_id": user_id, "subtotal": 5000, "currency": "CAD",
         "exchange_rate_to_cad": 1.0, "status": "draft", "issue_date": "2099-04-20"},
    ])
    test_db.expenses.insert_many([
        {"id": "e1", "user_id": user_id, "amount_cad": 200,
         "category_code": "office_expenses", "deductible_amount": 200,
         "expense_date": "2099-04-10"},
        {"id": "e2", "user_id": user_id, "amount_cad": 300,
         "category_code": "meals_entertainment", "deductible_amount": 150,
         "expense_date": "2099-05-15"},
        {"id": "e3", "user_id": user_id, "amount_cad": 150,
         "category_code": "rent", "deductible_amount": 150,
         "expense_date": "2099-06-20"},
    ])


class TestAggregatePnl:
    """Tests qui hit la DB locale (via monkey-patch de la global `db`)."""

    def test_accrual_includes_sent_paid_overdue(self, isolated_db, monkeypatch):
        import server
        monkeypatch.setattr(server, "db", isolated_db)
        _seed_for_aggregate(isolated_db, "u1")
        result = server._aggregate_pnl("u1", "2099-04-01", "2099-06-30", "accrual")
        # 2 paid + 1 sent = 3500 (draft exclu)
        assert result["revenue"] == 3500.00
        assert result["invoice_count"] == 3
        assert result["expense_count"] == 3

    def test_cash_only_paid(self, isolated_db, monkeypatch):
        import server
        monkeypatch.setattr(server, "db", isolated_db)
        _seed_for_aggregate(isolated_db, "u1")
        result = server._aggregate_pnl("u1", "2099-04-01", "2099-06-30", "cash")
        # 2 paid uniquement
        assert result["revenue"] == 3000.00
        assert result["invoice_count"] == 2

    def test_expense_groups_structure(self, isolated_db, monkeypatch):
        import server
        monkeypatch.setattr(server, "db", isolated_db)
        _seed_for_aggregate(isolated_db, "u1")
        result = server._aggregate_pnl("u1", "2099-04-01", "2099-06-30", "accrual")
        groups = {g["group"]: g for g in result["expense_groups"]}
        # office_expenses → group office
        assert "office" in groups
        office_cats = [c["code"] for c in groups["office"]["categories"]]
        assert "office_expenses" in office_cats
        # meals_entertainment → group marketing
        assert "marketing" in groups
        meals = next(c for c in groups["marketing"]["categories"] if c["code"] == "meals_entertainment")
        assert meals["gross"] == 300.00
        assert meals["deductible"] == 150.00
        # rent → group premises
        assert "premises" in groups

    def test_totals(self, isolated_db, monkeypatch):
        import server
        monkeypatch.setattr(server, "db", isolated_db)
        _seed_for_aggregate(isolated_db, "u1")
        result = server._aggregate_pnl("u1", "2099-04-01", "2099-06-30", "accrual")
        # Total gross = 200 + 300 + 150 = 650
        assert result["total_expenses"]["gross"] == 650.00
        # Total deductible = 200 + 150 + 150 = 500
        assert result["total_expenses"]["deductible"] == 500.00
        # Net management = 3500 - 650 = 2850
        assert result["net_income"]["management"] == 2850.00
        # Net taxable = 3500 - 500 = 3000
        assert result["net_income"]["taxable"] == 3000.00

    def test_empty_period(self, isolated_db, monkeypatch):
        import server
        monkeypatch.setattr(server, "db", isolated_db)
        result = server._aggregate_pnl("u1", "2020-01-01", "2020-01-31", "accrual")
        assert result["revenue"] == 0
        assert result["total_expenses"] == {"gross": 0, "deductible": 0}
        assert result["net_income"] == {"management": 0, "taxable": 0}
        assert result["expense_groups"] == []
        assert result["invoice_count"] == 0
        assert result["expense_count"] == 0
```

- [ ] **Step 2: Vérifier l'échec**

```bash
pytest tests/test_pnl_report.py::TestAggregatePnl -v 2>&1 | tail -10
```

Expected: `ImportError: cannot import name '_aggregate_pnl'`.

- [ ] **Step 3: Implémenter `_aggregate_pnl` dans `server.py`**

Localiser une bonne place après `_pct_delta` (créé en Task 1). Ajouter :

```python
def _aggregate_pnl(user_id, start, end, basis):
    """Calcule la portion 'current' (sans comparaison) du P&L pour la période [start, end].

    basis = 'accrual' : status ∈ {sent, paid, overdue}
    basis = 'cash'    : status == paid
    """
    # Revenue
    if basis == "cash":
        status_filter = "paid"
    else:
        status_filter = {"$in": ["sent", "paid", "overdue"]}
    invoice_filter = {
        "user_id": user_id,
        "issue_date": {"$gte": start, "$lte": end},
        "status": status_filter,
    }
    invoices = list(db.invoices.find(invoice_filter, {"_id": 0}))
    revenue = 0.0
    for inv in invoices:
        rate = inv.get("exchange_rate_to_cad", 1.0) or 1.0
        cur = inv.get("currency", "CAD")
        subtotal = float(inv.get("subtotal", 0) or 0)
        if cur != "CAD" and float(rate) > 0:
            subtotal = subtotal / float(rate)
        revenue += subtotal

    # Expenses
    expenses = list(db.expenses.find({
        "user_id": user_id,
        "expense_date": {"$gte": start, "$lte": end},
    }, {"_id": 0}))

    by_code = {}
    for e in expenses:
        code = e.get("category_code") or "other"
        if code not in by_code:
            by_code[code] = {"gross": 0.0, "deductible": 0.0}
        by_code[code]["gross"] += float(e.get("amount_cad", 0) or 0)
        by_code[code]["deductible"] += float(e.get("deductible_amount", 0) or 0)

    groups_order = ["office", "marketing", "premises", "travel", "personnel", "other"]
    expense_groups = []
    for g in groups_order:
        cats = [c for c in EXPENSE_CATEGORIES if c["group"] == g]
        rows = []
        sub_gross = 0.0
        sub_ded = 0.0
        for cat in cats:
            stats = by_code.get(cat["code"], {"gross": 0.0, "deductible": 0.0})
            if stats["gross"] == 0 and stats["deductible"] == 0:
                continue
            rows.append({
                "code": cat["code"],
                "label": cat["label_fr"],
                "arc_line": cat["arc_line"],
                "gross": round(stats["gross"], 2),
                "deductible": round(stats["deductible"], 2),
            })
            sub_gross += stats["gross"]
            sub_ded += stats["deductible"]
        if rows:
            expense_groups.append({
                "group": g,
                "label": EXPENSE_CATEGORY_GROUPS[g],
                "categories": rows,
                "subtotal": {"gross": round(sub_gross, 2), "deductible": round(sub_ded, 2)},
            })

    total_gross = sum(g["subtotal"]["gross"] for g in expense_groups)
    total_ded = sum(g["subtotal"]["deductible"] for g in expense_groups)

    return {
        "revenue": round(revenue, 2),
        "expense_groups": expense_groups,
        "total_expenses": {"gross": round(total_gross, 2), "deductible": round(total_ded, 2)},
        "net_income": {
            "management": round(revenue - total_gross, 2),
            "taxable": round(revenue - total_ded, 2),
        },
        "invoice_count": len(invoices),
        "expense_count": len(expenses),
    }
```

- [ ] **Step 4: Vérifier le succès**

```bash
pytest tests/test_pnl_report.py -v 2>&1 | tail -15
```

Expected: **18 passed** (13 prior + 5 aggregate).

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_pnl_report.py
git commit -m "feat(pnl): helper _aggregate_pnl (revenue + expenses par groupe + nets)"
```

---

## Task 3 — Helper `_merge_expense_groups`

**Files:**
- Modify: `backend/server.py`
- Modify: `backend/tests/test_pnl_report.py`

- [ ] **Step 1: Écrire les tests**

Append à `test_pnl_report.py` :

```python
class TestMergeExpenseGroups:
    def test_merge_disjoint_groups(self):
        from server import _merge_expense_groups
        current = [
            {"group": "office", "label": "Bureau et administration",
             "categories": [
                 {"code": "office_expenses", "label": "Frais de bureau", "arc_line": "8810",
                  "gross": 500, "deductible": 500},
             ],
             "subtotal": {"gross": 500, "deductible": 500}},
        ]
        previous = [
            {"group": "marketing", "label": "Marketing",
             "categories": [
                 {"code": "advertising", "label": "Publicité et promotion", "arc_line": "8520",
                  "gross": 200, "deductible": 200},
             ],
             "subtotal": {"gross": 200, "deductible": 200}},
        ]
        result = _merge_expense_groups(current, previous)
        # Devrait contenir 2 groupes
        groups = {g["group"]: g for g in result}
        assert "office" in groups
        assert "marketing" in groups
        # office présent uniquement dans current
        office = groups["office"]
        assert office["subtotal"]["current"] == {"gross": 500, "deductible": 500}
        assert office["subtotal"]["previous"] == {"gross": 0, "deductible": 0}
        # office_expenses category : current rempli, previous zéro
        oe = next(c for c in office["categories"] if c["code"] == "office_expenses")
        assert oe["current"] == {"gross": 500, "deductible": 500}
        assert oe["previous"] == {"gross": 0, "deductible": 0}

    def test_merge_overlap(self):
        from server import _merge_expense_groups
        current = [
            {"group": "office", "label": "Bureau et administration",
             "categories": [
                 {"code": "office_expenses", "label": "Frais de bureau", "arc_line": "8810",
                  "gross": 500, "deductible": 500},
             ],
             "subtotal": {"gross": 500, "deductible": 500}},
        ]
        previous = [
            {"group": "office", "label": "Bureau et administration",
             "categories": [
                 {"code": "office_expenses", "label": "Frais de bureau", "arc_line": "8810",
                  "gross": 450, "deductible": 450},
             ],
             "subtotal": {"gross": 450, "deductible": 450}},
        ]
        result = _merge_expense_groups(current, previous)
        assert len(result) == 1
        office = result[0]
        assert office["subtotal"]["current"]["gross"] == 500
        assert office["subtotal"]["previous"]["gross"] == 450
        oe = office["categories"][0]
        assert oe["current"]["gross"] == 500
        assert oe["previous"]["gross"] == 450

    def test_merge_preserves_groups_order(self):
        from server import _merge_expense_groups
        # Mettre les groupes dans un ordre désordonné en entrée
        current = [
            {"group": "marketing", "label": "Marketing", "categories": [], "subtotal": {"gross": 0, "deductible": 0}},
            {"group": "office", "label": "Bureau et administration", "categories": [], "subtotal": {"gross": 0, "deductible": 0}},
        ]
        # Ajouter de vraies catégories pour qu'ils soient inclus
        current[0]["categories"] = [{"code": "advertising", "label": "Publicité et promotion",
                                     "arc_line": "8520", "gross": 100, "deductible": 100}]
        current[0]["subtotal"] = {"gross": 100, "deductible": 100}
        current[1]["categories"] = [{"code": "office_expenses", "label": "Frais de bureau",
                                     "arc_line": "8810", "gross": 200, "deductible": 200}]
        current[1]["subtotal"] = {"gross": 200, "deductible": 200}
        result = _merge_expense_groups(current, [])
        order = [g["group"] for g in result]
        # office doit venir avant marketing dans l'ordre canonique
        assert order.index("office") < order.index("marketing")
```

- [ ] **Step 2: Vérifier l'échec**

```bash
pytest tests/test_pnl_report.py::TestMergeExpenseGroups -v 2>&1 | tail -10
```

Expected: `ImportError`.

- [ ] **Step 3: Implémenter dans `server.py`**

Ajouter immédiatement après `_aggregate_pnl` :

```python
def _merge_expense_groups(current_groups, previous_groups):
    """Aligne les groupes/catégories des deux périodes en un seul tableau,
    avec valeurs 'current' et 'previous' par catégorie + sous-total."""
    # Index previous par code de catégorie et par groupe
    p_by_code = {}
    p_subtotals = {}
    for pg in previous_groups:
        p_subtotals[pg["group"]] = pg["subtotal"]
        for cat in pg["categories"]:
            p_by_code[cat["code"]] = {"gross": cat["gross"], "deductible": cat["deductible"]}

    # Index current par groupe
    c_by_group = {g["group"]: g for g in current_groups}

    # Tous les groupes apparaissant dans l'un ou l'autre
    groups_order = ["office", "marketing", "premises", "travel", "personnel", "other"]
    merged = []
    for g_key in groups_order:
        c_group = c_by_group.get(g_key)
        p_subtotal = p_subtotals.get(g_key)
        if not c_group and not p_subtotal:
            continue
        c_subtotal = c_group["subtotal"] if c_group else {"gross": 0, "deductible": 0}
        p_subtotal = p_subtotal or {"gross": 0, "deductible": 0}

        rows = []
        for cat_def in [c for c in EXPENSE_CATEGORIES if c["group"] == g_key]:
            code = cat_def["code"]
            c_cat = None
            if c_group:
                c_cat = next((cc for cc in c_group["categories"] if cc["code"] == code), None)
            p_cat = p_by_code.get(code)
            if not c_cat and not p_cat:
                continue
            rows.append({
                "code": code,
                "label": cat_def["label_fr"],
                "arc_line": cat_def["arc_line"],
                "current": {
                    "gross": c_cat["gross"] if c_cat else 0,
                    "deductible": c_cat["deductible"] if c_cat else 0,
                },
                "previous": {
                    "gross": p_cat["gross"] if p_cat else 0,
                    "deductible": p_cat["deductible"] if p_cat else 0,
                },
            })
        merged.append({
            "group": g_key,
            "label": EXPENSE_CATEGORY_GROUPS[g_key],
            "categories": rows,
            "subtotal": {"current": c_subtotal, "previous": p_subtotal},
        })
    return merged
```

- [ ] **Step 4: Vérifier le succès**

```bash
pytest tests/test_pnl_report.py -v 2>&1 | tail -15
```

Expected: **21 passed** (18 prior + 3 merge).

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_pnl_report.py
git commit -m "feat(pnl): helper _merge_expense_groups pour structure current/previous"
```

---

## Task 4 — Endpoint `GET /api/reports/pnl`

**Files:**
- Modify: `backend/server.py`
- Create: `backend/tests/test_pnl_report_integration.py`

- [ ] **Step 1: Écrire les tests d'intégration**

Créer `backend/tests/test_pnl_report_integration.py` :

```python
"""Tests d'intégration HTTP pour le rapport P&L (feature #5)."""
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


class TestPnlReport:
    _cleanup = {"clients": [], "invoices": [], "expenses": []}
    _auth_headers = None
    _setup_done = False

    def _setup_data(self, auth):
        """Pour rester isolé du jeu de données locales, on utilise l'année 2099.
        2 invoices QC paid + 1 invoice sent + 1 invoice draft + 2 expenses + 1 expense meals."""
        if TestPnlReport._setup_done:
            return
        TestPnlReport._auth_headers = auth
        TestPnlReport._setup_done = True
        c = requests.post(f"{BASE_URL}/api/clients", headers=auth,
                          json={"name": "P&L Test"}).json()
        TestPnlReport._cleanup["clients"].append(c["id"])
        # 2 paid invoices (1000 chacune)
        for i in range(2):
            inv = requests.post(f"{BASE_URL}/api/invoices", headers=auth, json={
                "client_id": c["id"],
                "items": [{"description": "S", "quantity": 1, "unit_price": 1000}],
                "province": "QC", "issue_date": "2099-04-15",
            }).json()
            TestPnlReport._cleanup["invoices"].append(inv["id"])
            requests.put(f"{BASE_URL}/api/invoices/{inv['id']}/status",
                         headers=auth, json={"status": "paid"})
        # 1 invoice sent (1000)
        s = requests.post(f"{BASE_URL}/api/invoices", headers=auth, json={
            "client_id": c["id"],
            "items": [{"description": "Sent", "quantity": 1, "unit_price": 1000}],
            "province": "QC", "issue_date": "2099-05-10",
        }).json()
        TestPnlReport._cleanup["invoices"].append(s["id"])
        requests.put(f"{BASE_URL}/api/invoices/{s['id']}/status",
                     headers=auth, json={"status": "sent"})
        # 1 draft (à exclure)
        d = requests.post(f"{BASE_URL}/api/invoices", headers=auth, json={
            "client_id": c["id"],
            "items": [{"description": "Drft", "quantity": 1, "unit_price": 9999}],
            "province": "QC", "issue_date": "2099-04-20",
        }).json()
        TestPnlReport._cleanup["invoices"].append(d["id"])
        # 3 expenses
        for desc, amount, code in [("Bureau", 200, "office_expenses"),
                                    ("Repas", 300, "meals_entertainment"),
                                    ("Loyer", 150, "rent")]:
            e = requests.post(f"{BASE_URL}/api/expenses", headers=auth, json={
                "description": desc,
                "amount": amount,
                "currency": "CAD",
                "expense_date": "2099-04-20",
                "category_code": code,
            }).json()
            TestPnlReport._cleanup["expenses"].append(e["id"])

    def test_accrual_no_compare(self, auth):
        self._setup_data(auth)
        resp = requests.get(f"{BASE_URL}/api/reports/pnl",
                            headers=auth,
                            params={"start": "2099-04-01", "end": "2099-06-30",
                                    "basis": "accrual", "compare": "none"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["basis"] == "accrual"
        assert body["compare"] == "none"
        assert body["period"] == {"start": "2099-04-01", "end": "2099-06-30"}
        # 2 paid + 1 sent = 3000 (draft exclu)
        assert body["revenue"]["current"] == 3000.00
        # Total dépenses brut = 200 + 300 + 150 = 650
        assert body["total_expenses"]["current"]["gross"] == 650.00
        # Total dépenses déductibles = 200 + 150 (50% repas) + 150 = 500
        assert body["total_expenses"]["current"]["deductible"] == 500.00
        # Net management = 3000 - 650 = 2350
        assert body["net_income"]["current"]["management"] == 2350.00
        # Net taxable = 3000 - 500 = 2500
        assert body["net_income"]["current"]["taxable"] == 2500.00
        # 3 invoices (sans draft), 3 expenses
        assert body["invoice_count"] == 3
        assert body["expense_count"] == 3
        # Pas de compare_period
        assert "compare_period" not in body

    def test_cash_basis(self, auth):
        self._setup_data(auth)
        resp = requests.get(f"{BASE_URL}/api/reports/pnl",
                            headers=auth,
                            params={"start": "2099-04-01", "end": "2099-06-30",
                                    "basis": "cash", "compare": "none"})
        body = resp.json()
        # cash = uniquement paid : 2 invoices = 2000
        assert body["revenue"]["current"] == 2000.00
        assert body["invoice_count"] == 2

    def test_compare_previous(self, auth):
        self._setup_data(auth)
        resp = requests.get(f"{BASE_URL}/api/reports/pnl",
                            headers=auth,
                            params={"start": "2099-04-01", "end": "2099-06-30",
                                    "basis": "accrual", "compare": "previous"})
        body = resp.json()
        assert "compare_period" in body
        # Période précédente de même durée (Q2 = 91 jours) = Q1 2099
        assert body["compare_period"]["end"] == "2099-03-31"
        # previous est vide → 0
        assert body["revenue"]["previous"] == 0.0
        # delta_pct présent
        assert "delta_pct" in body["revenue"]

    def test_compare_prior_year(self, auth):
        self._setup_data(auth)
        resp = requests.get(f"{BASE_URL}/api/reports/pnl",
                            headers=auth,
                            params={"start": "2099-04-01", "end": "2099-06-30",
                                    "basis": "accrual", "compare": "prior_year"})
        body = resp.json()
        assert body["compare_period"] == {"start": "2098-04-01", "end": "2098-06-30"}

    def test_empty_period(self, auth):
        resp = requests.get(f"{BASE_URL}/api/reports/pnl",
                            headers=auth,
                            params={"start": "2020-01-01", "end": "2020-01-31",
                                    "basis": "accrual", "compare": "none"})
        body = resp.json()
        assert body["revenue"]["current"] == 0
        assert body["total_expenses"]["current"] == {"gross": 0, "deductible": 0}
        assert body["expense_groups"] == []
        assert body["invoice_count"] == 0
        assert body["expense_count"] == 0

    def test_invalid_basis_falls_back_to_accrual(self, auth):
        self._setup_data(auth)
        resp = requests.get(f"{BASE_URL}/api/reports/pnl",
                            headers=auth,
                            params={"start": "2099-04-01", "end": "2099-06-30",
                                    "basis": "garbage", "compare": "none"})
        body = resp.json()
        assert body["basis"] == "accrual"
        assert body["revenue"]["current"] == 3000.00

    def test_invalid_compare_falls_back_to_none(self, auth):
        self._setup_data(auth)
        resp = requests.get(f"{BASE_URL}/api/reports/pnl",
                            headers=auth,
                            params={"start": "2099-04-01", "end": "2099-06-30",
                                    "basis": "accrual", "compare": "weird"})
        body = resp.json()
        assert body["compare"] == "none"
        assert "compare_period" not in body

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
        cls._setup_done = False
```

- [ ] **Step 2: Démarrer uvicorn et vérifier l'échec**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
lsof -ti:8000 | xargs kill 2>/dev/null
source .venv/bin/activate
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_pnl_report_integration.py::TestPnlReport -v 2>&1 | tail -15
```

Expected: 404 sur les endpoints.

- [ ] **Step 3: Ajouter l'endpoint dans `server.py`**

Localiser après le endpoint `/api/reports/sales-tax/pdf` (autour de la ligne 2100+ après feature #4). Ajouter :

```python
@app.get("/api/reports/pnl")
def get_pnl_report(
    start: str = Query(...),
    end: str = Query(...),
    basis: str = Query("accrual"),
    compare: str = Query("none"),
    current_user: User = Depends(get_current_user_with_access),
):
    """État des résultats simplifié (P&L)."""
    if basis not in ("accrual", "cash"):
        basis = "accrual"
    if compare not in ("none", "previous", "prior_year"):
        compare = "none"

    current = _aggregate_pnl(current_user.id, start, end, basis)
    out = {
        "period": {"start": start, "end": end},
        "basis": basis,
        "compare": compare,
        "revenue": {"current": current["revenue"]},
        "expense_groups": [],
        "total_expenses": {"current": current["total_expenses"]},
        "net_income": {"current": current["net_income"]},
        "invoice_count": current["invoice_count"],
        "expense_count": current["expense_count"],
    }

    compare_period = _compute_compare_period(start, end, compare)
    if compare_period:
        cs, ce = compare_period
        previous = _aggregate_pnl(current_user.id, cs, ce, basis)
        out["compare_period"] = {"start": cs, "end": ce}
        out["revenue"]["previous"] = previous["revenue"]
        out["revenue"]["delta_pct"] = _pct_delta(previous["revenue"], current["revenue"])
        out["total_expenses"]["previous"] = previous["total_expenses"]
        out["net_income"]["previous"] = previous["net_income"]
        out["net_income"]["delta_pct"] = {
            "management": _pct_delta(previous["net_income"]["management"], current["net_income"]["management"]),
            "taxable": _pct_delta(previous["net_income"]["taxable"], current["net_income"]["taxable"]),
        }
        out["expense_groups"] = _merge_expense_groups(current["expense_groups"], previous["expense_groups"])
    else:
        # Sans comparaison : restructurer en {current: {...}} pour cohérence frontend
        for g in current["expense_groups"]:
            out["expense_groups"].append({
                "group": g["group"],
                "label": g["label"],
                "categories": [
                    {
                        "code": cat["code"],
                        "label": cat["label"],
                        "arc_line": cat["arc_line"],
                        "current": {"gross": cat["gross"], "deductible": cat["deductible"]},
                    } for cat in g["categories"]
                ],
                "subtotal": {"current": g["subtotal"]},
            })
    return out
```

- [ ] **Step 4: Redémarrer et relancer**

```bash
lsof -ti:8000 | xargs kill 2>/dev/null
source .venv/bin/activate
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_pnl_report.py tests/test_pnl_report_integration.py -v 2>&1 | tail -15
```

Expected: 28 passed (21 unit + 7 integration).

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_pnl_report_integration.py
git commit -m "feat(pnl): GET /api/reports/pnl avec basis et compare configurables"
```

---

## Task 5 — Endpoint `GET /api/reports/pnl/pdf`

**Files:**
- Modify: `backend/server.py`
- Modify: `backend/tests/test_pnl_report_integration.py`

- [ ] **Step 1: Ajouter le test PDF**

Append à `TestPnlReport` (avant `teardown_class`) :

```python
    def test_pdf_endpoint(self, auth):
        self._setup_data(auth)
        resp = requests.get(f"{BASE_URL}/api/reports/pnl/pdf",
                            headers=auth,
                            params={"start": "2099-04-01", "end": "2099-06-30",
                                    "basis": "accrual", "compare": "none"})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/pdf")
        assert resp.content[:4] == b"%PDF"
        assert len(resp.content) > 1000

    def test_pdf_with_compare(self, auth):
        self._setup_data(auth)
        resp = requests.get(f"{BASE_URL}/api/reports/pnl/pdf",
                            headers=auth,
                            params={"start": "2099-04-01", "end": "2099-06-30",
                                    "basis": "accrual", "compare": "previous"})
        assert resp.status_code == 200
        assert resp.content[:4] == b"%PDF"
```

- [ ] **Step 2: Vérifier l'échec**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
pytest tests/test_pnl_report_integration.py::TestPnlReport::test_pdf_endpoint tests/test_pnl_report_integration.py::TestPnlReport::test_pdf_with_compare -v 2>&1 | tail -10
```

Expected: 404.

- [ ] **Step 3: Ajouter le générateur PDF + endpoint dans `server.py`**

Localiser juste après le endpoint `GET /api/reports/pnl` ajouté en Task 4. Ajouter :

```python
def generate_pnl_report_pdf(user_id, data):
    """Génère un PDF du rapport P&L. `data` est la sortie de get_pnl_report."""
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
    comp_name = company_settings.get('company_name', 'Mon Entreprise')
    elements.append(Paragraph(comp_name, ParagraphStyle('C', parent=styles['Normal'],
                                                          fontSize=13, textColor=dark,
                                                          fontName='Helvetica-Bold')))
    elements.append(Paragraph("État des résultats", title_style))
    p = data['period']
    basis_label = "Comptabilité d'exercice" if data['basis'] == 'accrual' else "Comptabilité de caisse"
    elements.append(Paragraph(f"Période : {p['start']} au {p['end']}  ·  {basis_label}", sub_style))
    if data.get('compare_period'):
        cp = data['compare_period']
        elements.append(Paragraph(f"Comparaison : {cp['start']} au {cp['end']}", sub_style))
    elements.append(Spacer(1, 0.2*inch))

    # Numéros d'enregistrement (réutilise feature #2)
    regs = _take_regs(company_settings)
    parts = _reg_label_parts(regs)
    if parts:
        elements.append(Paragraph("Numéros d'enregistrement", bold))
        elements.append(Paragraph(' &nbsp;·&nbsp; '.join(parts), small))
        elements.append(Spacer(1, 0.2*inch))

    def fmt(v):
        return f"{(v or 0):,.2f} $".replace(",", " ")

    # Sommaire
    elements.append(Paragraph("Sommaire", bold))
    summary_rows = [['', fmt(data['revenue']['current']) if False else 'Montant']]
    has_compare = data.get('compare_period') is not None
    summary_rows = [
        ["", "Période", "Comparaison" if has_compare else "", "Δ %" if has_compare else ""],
        ["Revenus", fmt(data['revenue']['current']),
         fmt(data['revenue'].get('previous')) if has_compare else "",
         f"{data['revenue'].get('delta_pct', 0):+.1f} %" if has_compare else ""],
        ["Total dépenses (brut)", fmt(data['total_expenses']['current']['gross']),
         fmt(data['total_expenses'].get('previous', {}).get('gross')) if has_compare else "",
         ""],
        ["Bénéfice de gestion", fmt(data['net_income']['current']['management']),
         fmt(data['net_income'].get('previous', {}).get('management')) if has_compare else "",
         f"{data['net_income'].get('delta_pct', {}).get('management', 0):+.1f} %" if has_compare else ""],
        ["Bénéfice imposable", fmt(data['net_income']['current']['taxable']),
         fmt(data['net_income'].get('previous', {}).get('taxable')) if has_compare else "",
         f"{data['net_income'].get('delta_pct', {}).get('taxable', 0):+.1f} %" if has_compare else ""],
    ]
    summary_t = Table(summary_rows, colWidths=[2.2*inch, 1.5*inch, 1.5*inch, 1*inch])
    summary_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#f8fafb')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#e5e7eb')),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(summary_t)
    elements.append(Spacer(1, 0.3*inch))

    # Détail des dépenses
    elements.append(Paragraph("Détail des dépenses", bold))
    headers = ["Catégorie", "Brut", "Déductible"]
    if has_compare:
        headers += ["Brut (cmp)", "Déduct. (cmp)"]
    detail_rows = [headers]
    for g in data['expense_groups']:
        # Ligne de groupe
        group_subtotal = g['subtotal']
        c_st = group_subtotal['current']
        p_st = group_subtotal.get('previous', {"gross": 0, "deductible": 0})
        row = [g['label'], fmt(c_st['gross']), fmt(c_st['deductible'])]
        if has_compare:
            row += [fmt(p_st['gross']), fmt(p_st['deductible'])]
        detail_rows.append(row)
        # Catégories
        for cat in g['categories']:
            cc = cat['current']
            pc = cat.get('previous', {"gross": 0, "deductible": 0})
            label = f"  · {cat['label']}" + (f" ({cat['arc_line']})" if cat['arc_line'] else "")
            row = [label, fmt(cc['gross']), fmt(cc['deductible'])]
            if has_compare:
                row += [fmt(pc['gross']), fmt(pc['deductible'])]
            detail_rows.append(row)

    col_widths = [2.3*inch, 1*inch, 1*inch]
    if has_compare:
        col_widths += [1.1*inch, 1.1*inch]
    detail_t = Table(detail_rows, colWidths=col_widths)
    detail_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#f8fafb')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#e5e7eb')),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(detail_t)
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


@app.get("/api/reports/pnl/pdf")
def get_pnl_report_pdf(
    start: str = Query(...),
    end: str = Query(...),
    basis: str = Query("accrual"),
    compare: str = Query("none"),
    current_user: User = Depends(get_current_user_with_access),
):
    data = get_pnl_report(start, end, basis, compare, current_user)
    pdf_buffer = generate_pnl_report_pdf(current_user.id, data)
    filename = f"etat-des-resultats-{start}-au-{end}.pdf"
    return StreamingResponse(pdf_buffer, media_type="application/pdf",
                              headers={"Content-Disposition": f'attachment; filename="{filename}"'})
```

- [ ] **Step 4: Redémarrer et relancer**

```bash
lsof -ti:8000 | xargs kill 2>/dev/null
source .venv/bin/activate
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_pnl_report.py tests/test_pnl_report_integration.py -v 2>&1 | tail -10
```

Expected: 30 passed (28 + 2 PDF).

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_pnl_report_integration.py
git commit -m "feat(pnl): GET /api/reports/pnl/pdf — PDF avec sommaire et détail dépenses"
```

---

## Task 6 — Frontend : conversion ReportsPage en onglets

**Files:**
- Modify: `frontend/src/pages/ReportsPage.js`

Le contenu existant (rapport TPS/TVQ) doit être extrait en composant et un onglet doit permettre de switcher vers le nouveau composant P&L (qui sera créé au Task 7).

- [ ] **Step 1: Lire la structure actuelle**

```bash
head -50 frontend/src/pages/ReportsPage.js
```

- [ ] **Step 2: Refactorer ReportsPage en wrapper d'onglets**

Au sommet de `ReportsPage.js`, conserver les imports et helpers existants (`QUARTERS`, `YEARS`, `fmt`, etc.).

Convertir le composant `ReportsPage` en :

```javascript
function ReportsPage() {
  const [activeTab, setActiveTab] = useState('sales_tax');

  const tabStyle = (isActive) => ({
    padding: '10px 18px',
    background: isActive ? 'white' : '#f3f4f6',
    color: isActive ? '#00A08C' : '#6b7280',
    border: 0,
    borderBottom: isActive ? '2px solid #00A08C' : '2px solid transparent',
    fontSize: 14,
    fontWeight: isActive ? 600 : 500,
    cursor: 'pointer',
    marginRight: 4,
  });

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: 20 }}>
      <h2 style={{ marginTop: 0 }}>Rapports</h2>
      <div style={{ display: 'flex', borderBottom: '1px solid #e5e7eb', marginBottom: 20 }}>
        <button style={tabStyle(activeTab === 'sales_tax')}
          onClick={() => setActiveTab('sales_tax')}>
          Rapport TPS / TVQ
        </button>
        <button style={tabStyle(activeTab === 'pnl')}
          onClick={() => setActiveTab('pnl')}>
          État des résultats (P&L)
        </button>
      </div>
      {activeTab === 'sales_tax' && <SalesTaxReportSection />}
      {activeTab === 'pnl' && <PnlReportSection />}
    </div>
  );
}
```

Extraire le code existant du rapport TPS/TVQ en un composant `SalesTaxReportSection` (le code qui gère le picker trimestre + custom + génération + affichage du rapport sales-tax existant). Toute la logique du composant ReportsPage actuel devient le corps de `SalesTaxReportSection`.

Au bas du fichier, ajouter un stub :

```javascript
function PnlReportSection() {
  return <div>État des résultats — à venir (Task 7)</div>;
}
```

- [ ] **Step 3: Build**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
npx --no-install react-scripts build 2>&1 | tail -10
```

Expected: Compiled successfully.

- [ ] **Step 4: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add frontend/src/pages/ReportsPage.js
git commit -m "refactor(reports): conversion ReportsPage en onglets (SalesTax + stub P&L)"
```

---

## Task 7 — Frontend : composant `PnlReportSection`

**Files:**
- Modify: `frontend/src/pages/ReportsPage.js`

Remplacer le stub `PnlReportSection` ajouté en Task 6 par le vrai composant.

- [ ] **Step 1: Implémenter PnlReportSection**

Remplacer le stub par :

```javascript
const PNL_QUARTERS = QUARTERS;  // réutilise constants déjà définies
const PNL_YEARS = YEARS;
const MONTHS = [
  { value: '01', label: 'Janvier' }, { value: '02', label: 'Février' },
  { value: '03', label: 'Mars' },    { value: '04', label: 'Avril' },
  { value: '05', label: 'Mai' },     { value: '06', label: 'Juin' },
  { value: '07', label: 'Juillet' }, { value: '08', label: 'Août' },
  { value: '09', label: 'Septembre' },{ value: '10', label: 'Octobre' },
  { value: '11', label: 'Novembre' },{ value: '12', label: 'Décembre' },
];

function PnlReportSection() {
  const [periodMode, setPeriodMode] = useState('quarter');
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [quarter, setQuarter] = useState('Q1');
  const [month, setMonth] = useState('01');
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');
  const [basis, setBasis] = useState('accrual');
  const [compare, setCompare] = useState('none');
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);

  const getDates = () => {
    if (periodMode === 'quarter') {
      const q = PNL_QUARTERS.find(x => x.value === quarter);
      return { start: `${year}-${q.start}`, end: `${year}-${q.end}` };
    }
    if (periodMode === 'month') {
      // Dernier jour du mois (calcul JS naïf)
      const lastDay = new Date(parseInt(year), parseInt(month), 0).getDate();
      return { start: `${year}-${month}-01`, end: `${year}-${month}-${String(lastDay).padStart(2, '0')}` };
    }
    if (periodMode === 'year') {
      return { start: `${year}-01-01`, end: `${year}-12-31` };
    }
    return { start: customStart, end: customEnd };
  };

  const generate = async () => {
    const { start, end } = getDates();
    if (!start || !end) return;
    setLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const resp = await axios.get(`${BACKEND_URL}/api/reports/pnl`, {
        headers: { Authorization: `Bearer ${token}` },
        params: { start, end, basis, compare },
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
      `${BACKEND_URL}/api/reports/pnl/pdf?start=${start}&end=${end}&basis=${basis}&compare=${compare}`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    const blob = await resp.blob();
    const url = window.URL.createObjectURL(blob);
    window.open(url, '_blank');
  };

  const fmt2 = v => (v || 0).toLocaleString('fr-CA', { style: 'currency', currency: 'CAD' });
  const deltaColor = d => d > 0 ? '#059669' : d < 0 ? '#dc2626' : '#6b7280';
  const deltaArrow = d => d > 0 ? '↑' : d < 0 ? '↓' : '';
  const hasCompare = report && report.compare !== 'none' && report.compare_period;

  return (
    <div style={{ background: 'white', padding: 20, borderRadius: 8, boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
      <h3 style={{ marginTop: 0 }}>État des résultats (P&L)</h3>

      <div style={{ marginBottom: 12 }}>
        <label style={{ marginRight: 12 }}>
          <input type="radio" checked={periodMode === 'month'} onChange={() => setPeriodMode('month')} /> Mois
        </label>
        <label style={{ marginRight: 12 }}>
          <input type="radio" checked={periodMode === 'quarter'} onChange={() => setPeriodMode('quarter')} /> Trimestre
        </label>
        <label style={{ marginRight: 12 }}>
          <input type="radio" checked={periodMode === 'year'} onChange={() => setPeriodMode('year')} /> Année
        </label>
        <label>
          <input type="radio" checked={periodMode === 'custom'} onChange={() => setPeriodMode('custom')} /> Personnalisée
        </label>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
        {(periodMode === 'quarter' || periodMode === 'year' || periodMode === 'month') && (
          <select value={year} onChange={e => setYear(e.target.value)}
            style={{ padding: 8, borderRadius: 6, border: '1px solid #d1d5db' }}>
            {PNL_YEARS.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        )}
        {periodMode === 'quarter' && (
          <select value={quarter} onChange={e => setQuarter(e.target.value)}
            style={{ padding: 8, borderRadius: 6, border: '1px solid #d1d5db' }}>
            {PNL_QUARTERS.map(q => <option key={q.value} value={q.value}>{q.label}</option>)}
          </select>
        )}
        {periodMode === 'month' && (
          <select value={month} onChange={e => setMonth(e.target.value)}
            style={{ padding: 8, borderRadius: 6, border: '1px solid #d1d5db' }}>
            {MONTHS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        )}
        {periodMode === 'custom' && (
          <>
            <input type="date" value={customStart} onChange={e => setCustomStart(e.target.value)}
              style={{ padding: 8, borderRadius: 6, border: '1px solid #d1d5db' }} />
            <input type="date" value={customEnd} onChange={e => setCustomEnd(e.target.value)}
              style={{ padding: 8, borderRadius: 6, border: '1px solid #d1d5db' }} />
          </>
        )}
      </div>

      <div style={{ marginBottom: 12 }}>
        <span style={{ fontSize: 13, fontWeight: 500, marginRight: 12 }}>Base :</span>
        <label style={{ marginRight: 12 }}>
          <input type="radio" checked={basis === 'accrual'} onChange={() => setBasis('accrual')} /> Comptabilité d'exercice
        </label>
        <label>
          <input type="radio" checked={basis === 'cash'} onChange={() => setBasis('cash')} /> Comptabilité de caisse
        </label>
      </div>

      <div style={{ marginBottom: 12 }}>
        <span style={{ fontSize: 13, fontWeight: 500, marginRight: 12 }}>Comparer :</span>
        <label style={{ marginRight: 12 }}>
          <input type="radio" checked={compare === 'none'} onChange={() => setCompare('none')} /> Aucune
        </label>
        <label style={{ marginRight: 12 }}>
          <input type="radio" checked={compare === 'previous'} onChange={() => setCompare('previous')} /> Période précédente
        </label>
        <label>
          <input type="radio" checked={compare === 'prior_year'} onChange={() => setCompare('prior_year')} /> Année précédente
        </label>
      </div>

      <button onClick={generate} disabled={loading}
        style={{ padding: '10px 18px', background: '#00A08C', color: 'white', border: 0, borderRadius: 6, cursor: 'pointer' }}>
        {loading ? 'Génération…' : 'Générer le rapport'}
      </button>

      {report && (
        <div style={{ marginTop: 24 }}>
          {/* Sommaire */}
          <h4 style={{ marginBottom: 8 }}>Sommaire</h4>
          <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 16 }}>
            <thead>
              <tr style={{ background: '#f8fafb' }}>
                <th style={{ padding: 8, textAlign: 'left' }}></th>
                <th style={{ padding: 8, textAlign: 'right' }}>Période</th>
                {hasCompare && <th style={{ padding: 8, textAlign: 'right' }}>Compare</th>}
                {hasCompare && <th style={{ padding: 8, textAlign: 'right' }}>Δ %</th>}
              </tr>
            </thead>
            <tbody>
              <tr style={{ borderBottom: '1px solid #e5e7eb' }}>
                <td style={{ padding: 8 }}>Revenus</td>
                <td style={{ padding: 8, textAlign: 'right' }}>{fmt2(report.revenue.current)}</td>
                {hasCompare && <td style={{ padding: 8, textAlign: 'right' }}>{fmt2(report.revenue.previous)}</td>}
                {hasCompare && (
                  <td style={{ padding: 8, textAlign: 'right', color: deltaColor(report.revenue.delta_pct) }}>
                    {report.revenue.delta_pct.toFixed(1)} % {deltaArrow(report.revenue.delta_pct)}
                  </td>
                )}
              </tr>
              <tr style={{ borderBottom: '1px solid #e5e7eb' }}>
                <td style={{ padding: 8 }}>Total dépenses (brut)</td>
                <td style={{ padding: 8, textAlign: 'right' }}>{fmt2(report.total_expenses.current.gross)}</td>
                {hasCompare && <td style={{ padding: 8, textAlign: 'right' }}>{fmt2(report.total_expenses.previous.gross)}</td>}
                {hasCompare && <td></td>}
              </tr>
              <tr style={{ borderTop: '2px solid #00A08C', fontWeight: 700 }}>
                <td style={{ padding: 8 }}>Bénéfice de gestion</td>
                <td style={{ padding: 8, textAlign: 'right' }}>{fmt2(report.net_income.current.management)}</td>
                {hasCompare && <td style={{ padding: 8, textAlign: 'right' }}>{fmt2(report.net_income.previous.management)}</td>}
                {hasCompare && (
                  <td style={{ padding: 8, textAlign: 'right', color: deltaColor(report.net_income.delta_pct.management) }}>
                    {report.net_income.delta_pct.management.toFixed(1)} % {deltaArrow(report.net_income.delta_pct.management)}
                  </td>
                )}
              </tr>
              <tr style={{ fontWeight: 700 }}>
                <td style={{ padding: 8 }}>Bénéfice imposable</td>
                <td style={{ padding: 8, textAlign: 'right' }}>{fmt2(report.net_income.current.taxable)}</td>
                {hasCompare && <td style={{ padding: 8, textAlign: 'right' }}>{fmt2(report.net_income.previous.taxable)}</td>}
                {hasCompare && (
                  <td style={{ padding: 8, textAlign: 'right', color: deltaColor(report.net_income.delta_pct.taxable) }}>
                    {report.net_income.delta_pct.taxable.toFixed(1)} % {deltaArrow(report.net_income.delta_pct.taxable)}
                  </td>
                )}
              </tr>
            </tbody>
          </table>

          {/* Détail dépenses */}
          <h4 style={{ marginBottom: 8 }}>Détail des dépenses</h4>
          {report.expense_groups.map(g => (
            <details key={g.group} open style={{ marginBottom: 8 }}>
              <summary style={{ cursor: 'pointer', fontWeight: 600, padding: '6px 8px', background: '#f9fafb', borderRadius: 4 }}>
                {g.label} — Brut {fmt2(g.subtotal.current.gross)} · Déduct. {fmt2(g.subtotal.current.deductible)}
                {hasCompare && ` (cmp ${fmt2(g.subtotal.previous.gross)} / ${fmt2(g.subtotal.previous.deductible)})`}
              </summary>
              <table style={{ width: '100%', marginTop: 4, borderCollapse: 'collapse' }}>
                <tbody>
                  {g.categories.map(cat => (
                    <tr key={cat.code} style={{ borderBottom: '1px solid #f3f4f6' }}>
                      <td style={{ padding: '4px 16px', fontSize: 13 }}>
                        · {cat.label}
                        {cat.arc_line && <span style={{ color: '#9ca3af', fontSize: 11, marginLeft: 4 }}>({cat.arc_line})</span>}
                        {cat.code === 'meals_entertainment' && cat.current.gross > cat.current.deductible && (
                          <span style={{ marginLeft: 6, fontSize: 11, color: '#92400e' }}>⚠ 50%</span>
                        )}
                      </td>
                      <td style={{ padding: '4px 8px', textAlign: 'right', fontSize: 13 }}>{fmt2(cat.current.gross)}</td>
                      <td style={{ padding: '4px 8px', textAlign: 'right', fontSize: 13 }}>{fmt2(cat.current.deductible)}</td>
                      {hasCompare && <td style={{ padding: '4px 8px', textAlign: 'right', fontSize: 13, color: '#6b7280' }}>{fmt2(cat.previous.gross)}</td>}
                      {hasCompare && <td style={{ padding: '4px 8px', textAlign: 'right', fontSize: 13, color: '#6b7280' }}>{fmt2(cat.previous.deductible)}</td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          ))}

          <div style={{ marginTop: 12, color: '#6b7280', fontSize: 12 }}>
            {report.invoice_count} factures · {report.expense_count} dépenses incluses
          </div>

          <button onClick={downloadPdf}
            style={{ marginTop: 12, padding: '10px 18px', background: '#1f2937', color: 'white', border: 0, borderRadius: 6, cursor: 'pointer' }}>
            Télécharger le PDF
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Build**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
npx --no-install react-scripts build 2>&1 | tail -10
```

Expected: Compiled successfully.

- [ ] **Step 3: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add frontend/src/pages/ReportsPage.js
git commit -m "feat(pnl): PnlReportSection (period multi-mode, basis, compare, table)"
```

---

## Task 8 — E2E + push prod + CLAUDE.md

- [ ] **Step 1: Full test battery**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
lsof -ti:8000 | xargs kill 2>/dev/null
source .venv/bin/activate
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_tax_numbers.py tests/test_tax_registrations_integration.py tests/test_expense_categories.py tests/test_expense_categories_integration.py tests/test_tax_report.py tests/test_tax_report_integration.py tests/test_pnl_report.py tests/test_pnl_report_integration.py -v 2>&1 | tail -10
```

Expected: ~135 tests (108 prior + 21 unit + 8 integration).

- [ ] **Step 2: E2E HTTP**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
   -H "Content-Type: application/json" \
   -d '{"email":"gussdub@gmail.com","password":"testpass123"}' \
   | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

echo "=== P&L JSON (empty period, no compare) ==="
curl -s "http://localhost:8000/api/reports/pnl?start=2020-01-01&end=2020-01-31&basis=accrual&compare=none" \
   -H "Authorization: Bearer $TOKEN" | python -m json.tool | head -30

echo "=== P&L PDF ==="
curl -s "http://localhost:8000/api/reports/pnl/pdf?start=2020-01-01&end=2020-01-31&basis=accrual&compare=none" \
   -H "Authorization: Bearer $TOKEN" -o /tmp/pnl.pdf
file /tmp/pnl.pdf
```

Expected: PDF + valid JSON.

- [ ] **Step 3: Stop local backend**

```bash
lsof -ti:8000 | xargs kill 2>/dev/null
```

- [ ] **Step 4: Update CLAUDE.md**

Append à la section "Features livrées" :

```markdown

- **2026-06-16 — État des résultats simplifié P&L (feature #5)**
  - `GET /api/reports/pnl?start&end&basis&compare` retourne revenus, dépenses groupées par catégorie ARC + sous-totaux par groupe, 2 nets (gestion + imposable)
  - `GET /api/reports/pnl/pdf?...` génère un PDF avec sommaire et détail
  - Frontend : ReportsPage en onglets (Rapport TPS/TVQ + État des résultats)
  - Sélecteurs multi-période (mois / trimestre / année / personnalisée), basis (exercice/caisse), comparaison (aucune/précédente/année précédente)
  - Tableau collapsible par groupe avec brut + déductible côte à côte
  - Limitation v1 : cash basis = filtre `status=paid` sur `issue_date` (approximation)
  - Spec : `docs/superpowers/specs/2026-06-16-pnl-report-design.md`
  - Plan : `docs/superpowers/plans/2026-06-16-pnl-report.md`
```

- [ ] **Step 5: Push prod**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git log origin/main..HEAD --oneline
git add CLAUDE.md
git commit -m "docs: changelog feature #5 (P&L)"
git push origin main 2>&1 | tail -5
```

- [ ] **Step 6: Verify prod after ~3 min**

```bash
sleep 180
echo "=== Backend prod ==="
curl -s -m 90 https://facturepro-backend-dkvn.onrender.com/api/health
echo
echo "=== Frontend prod ==="
curl -sI -m 30 https://facturepro.ca | head -3
```

Expected: backend healthy, frontend 308.

---

## Récap fichiers touchés

| Fichier | Tasks | Nature |
|---|---|---|
| `backend/server.py` | 1, 2, 3, 4, 5 | Modif (4 helpers + 2 endpoints + PDF gen) |
| `backend/tests/test_pnl_report.py` | 1, 2, 3 | Nouveau (unit) |
| `backend/tests/test_pnl_report_integration.py` | 4, 5 | Nouveau (intégration) |
| `frontend/src/pages/ReportsPage.js` | 6, 7 | Modif (onglets + PnlReportSection) |
| `CLAUDE.md` | 8 | Modif (changelog) |

Commits attendus : **8** (un par task).
