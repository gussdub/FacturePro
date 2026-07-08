# Dépenses nettes des taxes récupérables (feature #7.7) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faire comptabiliser au P&L / T2125 / GIFI / rapport TPS-TVQ la charge NETTE des taxes récupérables (CTI/RTI) — 50 % pour les repas, prorata avec seuils 10/90 pour le télécom — via un helper unifié partagé avec le grand livre, pour qu'ils ne divergent jamais.

**Architecture:** Un helper `_expense_recovery_frac(exp)` (source unique de la fraction de taxe récupérable) et `_expense_net_business_cad(exp)` (la charge nette qui va au compte 5xxx). Le grand livre (`_build_expense_charge_lines`), le P&L (`_aggregate_pnl`) et le rapport de taxes (`_aggregate_sales_tax`) en dérivent tous. Migration idempotente au startup pour re-snapshoter le déductible et re-poster les écritures de repas.

**Tech Stack:** FastAPI + pymongo (sync), `backend/server.py` monolithique ; tests pytest in-process (`TestClient`) sur MongoDB local ; venv `.venv-test/` ; frontend React CRA (build CI obligatoire avant push).

Spec de référence : [`docs/superpowers/specs/2026-07-08-expenses-net-of-recoverable-tax-design.md`](../specs/2026-07-08-expenses-net-of-recoverable-tax-design.md).

---

## Contexte technique

- **Commande de test** : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest <path> -q`
- **Compte de test** : `email=gussdub@gmail.com` / `password=testpass123` (voir `test_bank_expense_automatch.py`).
- **Champs de taxe sur une dépense** : `gst_paid_cad`, `qst_paid_cad`, `hst_paid_cad` (saisis dans la devise de la dépense, reconvertis CAD via `exchange_rate_to_cad` pour une devise étrangère). `personal_use_amount_cad` = portion perso (télécom uniquement). `amount_cad` = décaissement TTC.
- **Helpers existants à connaître** : `_repost_expense_gl(org_id, user_id, expense_id, updated_expense)` (contre-passe + re-poste, idempotent, gaté sur `autopost_enabled`) ; `_autopost_debit`/`_autopost_credit`/`_resolve_expense_account`/`_resolve_ledger_account`/`_account_type_for_number`.
- **Build frontend AVANT push** : `CI=true GENERATE_SOURCEMAP=false npx --no-install react-scripts build` depuis `frontend/`.
- **Push** : `git push origin main` déclenche Render (backend + migration startup) + Vercel. Confirmer avec l'utilisateur (Task 8).

---

## Structure des fichiers

Tout le backend est dans `backend/server.py`. Nouveaux helpers regroupés juste avant `_build_expense_charge_lines` (section GL, ~ligne 3060). Tests dans `backend/tests/test_expense_net_tax.py`.

---

## Task 0 : Fichier de tests

**Files:** Create `backend/tests/test_expense_net_tax.py`

- [ ] **Step 1: Créer le fichier**

```python
"""Tests — dépenses nettes des taxes récupérables (feature #7.7).

Vérifie le helper unifié de fraction récupérable (50% repas, seuils 10/90 télécom),
la charge nette (P&L/5xxx), le rapport TPS/TVQ, l'équilibre partie double, et la
migration idempotente.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")
os.environ.setdefault("DB_NAME", "facturepro")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from backend.server import app, db  # noqa: E402

client = TestClient(app)


@pytest.fixture
def auth_headers():
    r = client.post("/api/auth/login", json={"email": "gussdub@gmail.com", "password": "testpass123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
```

- [ ] **Step 2: Vérifier le collect**

Run: `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_net_tax.py --collect-only -q`
Expected: `no tests collected`.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_expense_net_tax.py
git commit -m "test(F7.7-T0): stub tests dépenses nettes de taxes"
```

---

## Task 1 : Helpers unifiés de taxe récupérable

**Files:** Modify `backend/server.py` (nouveaux helpers avant `_build_expense_charge_lines`) ; Test `backend/tests/test_expense_net_tax.py`

- [ ] **Step 1: Tests qui échouent**

Append à `backend/tests/test_expense_net_tax.py` :

```python
def _exp(**kw):
    """Fabrique un dict dépense minimal pour les tests unitaires des helpers."""
    base = {"amount_cad": 0.0, "currency": "CAD", "exchange_rate_to_cad": 1.0,
            "gst_paid_cad": 0.0, "qst_paid_cad": 0.0, "hst_paid_cad": 0.0,
            "category_code": "office_supplies"}
    base.update(kw)
    return base


def test_recovery_frac_normal_meals_telecom():
    from backend.server import _expense_recovery_frac
    # normal → 1.0
    assert _expense_recovery_frac(_exp(category_code="office_supplies")) == 1.0
    # repas → 0.5
    assert _expense_recovery_frac(_exp(category_code="meals_entertainment")) == 0.5
    # télécom 60% (perso 40% de 100) → 0.6
    assert abs(_expense_recovery_frac(_exp(category_code="telecom_cell",
               amount_cad=100.0, personal_use_amount_cad=40.0)) - 0.6) < 1e-9
    # télécom 8% affaires (perso 92) → seuil ≤10% → 0.0
    assert _expense_recovery_frac(_exp(category_code="telecom_cell",
               amount_cad=100.0, personal_use_amount_cad=92.0)) == 0.0
    # télécom 95% affaires (perso 5) → seuil ≥90% → 1.0
    assert _expense_recovery_frac(_exp(category_code="telecom_cell",
               amount_cad=100.0, personal_use_amount_cad=5.0)) == 1.0


def test_net_business_and_balance():
    from backend.server import _expense_net_business_cad, _expense_recoverable_tax_cad
    # Office 114.98 TTC (100 + 14.98 taxes QC) → net 100.00
    e = _exp(category_code="office_supplies", amount_cad=114.98, gst_paid_cad=5.0, qst_paid_cad=9.98)
    assert _expense_net_business_cad(e) == 100.00
    # Repas 114.98 → récupérable 50% (7.49) → net 107.49
    m = _exp(category_code="meals_entertainment", amount_cad=114.98, gst_paid_cad=5.0, qst_paid_cad=9.98)
    assert _expense_net_business_cad(m) == 107.49
    # Télécom 60% 114.98 (perso 45.99) → récupérable 0.6×14.98=8.99 → net 60.00
    t = _exp(category_code="telecom_cell", amount_cad=114.98, personal_use_amount_cad=45.99,
             gst_paid_cad=5.0, qst_paid_cad=9.98)
    assert _expense_net_business_cad(t) == 60.00
    # INVARIANT équilibre : net + Σrecoverable + personal == amount_cad (au cent près)
    for exp in (e, m, t):
        gst, qst, hst = _expense_recoverable_tax_cad(exp)
        personal = float(exp.get("personal_use_amount_cad", 0) or 0)
        net = _expense_net_business_cad(exp)
        assert abs(net + gst + qst + hst + personal - exp["amount_cad"]) < 0.011


def test_recoverable_capped_at_business_amount():
    from backend.server import _expense_recoverable_tax_cad
    # Taxes aberrantes > montant : capées à amount - personal (jamais > la portion affaires payée).
    e = _exp(category_code="office_supplies", amount_cad=10.0, gst_paid_cad=8.0, qst_paid_cad=8.0)
    gst, qst, hst = _expense_recoverable_tax_cad(e)
    assert abs((gst + qst + hst) - 10.0) < 0.011
```

- [ ] **Step 2: Vérifier l'échec**

Run: `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_net_tax.py -q`
Expected: FAIL (`ImportError: _expense_recovery_frac`).

- [ ] **Step 3: Ajouter les helpers**

Dans `backend/server.py`, JUSTE AVANT `def _build_expense_charge_lines`, insérer :

```python
_MEALS_RECOVERY_RATE = 0.5  # limite ITC repas : seulement 50% de la TPS/TVQ récupérable


def _recoverable_usage_frac(exp):
    """Fraction d'usage AFFAIRES ouvrant droit au CTI/RTI, avec les seuils ARC (Mémorandum
    TPS/TVH 8-1, par. 24/27) : ≤10 % → 0 ; ≥90 % → 1 ; sinon la fraction réelle. Retourne 1.0
    pour une dépense non télécom (pas de personal_use_amount_cad). Les seuils ne visent QUE le
    crédit de taxe — la déductibilité du revenu reste sur la fraction réelle (personal_use)."""
    amt = float(exp.get("amount_cad", 0) or 0)
    personal = exp.get("personal_use_amount_cad")
    if personal is None or amt <= 0:
        return 1.0
    biz = max(0.0, (amt - float(personal or 0)) / amt)
    if biz <= 0.10:
        return 0.0
    if biz >= 0.90:
        return 1.0
    return biz


def _expense_recovery_frac(exp):
    """SOURCE UNIQUE (feature #7.7) de la fraction de la taxe SAISIE réellement récupérable :
    taux catégorie (50 % repas, 100 % sinon) × fraction d'usage affaires (avec seuils télécom).
    Partagée par le grand livre (_build_expense_charge_lines), le P&L (_aggregate_pnl) et le
    rapport TPS/TVQ (_aggregate_sales_tax) → aucune divergence possible."""
    cat_rate = _MEALS_RECOVERY_RATE if (exp.get("category_code") == "meals_entertainment") else 1.0
    return cat_rate * _recoverable_usage_frac(exp)


def _expense_recoverable_tax_cad(exp):
    """(gst, qst, hst) récupérables en CAD. Chaque taxe saisie est reconvertie en CAD pour une
    dépense en devise (÷ taux, comme les taxes de facture), puis × recovery_frac. Le TOTAL est
    plafonné à (amount_cad − personal) : on ne récupère jamais plus que la portion affaires
    TTC payée (garde-fou équilibre partie double)."""
    rate = exp.get("exchange_rate_to_cad") or 1.0
    is_foreign = exp.get("currency") not in (None, "", "CAD") and rate > 0

    def _cad(x):
        x = float(x or 0)
        return round((x / rate), 2) if is_foreign else round(x, 2)

    frac = _expense_recovery_frac(exp)
    gst = round(_cad(exp.get("gst_paid_cad")) * frac, 2)
    qst = round(_cad(exp.get("qst_paid_cad")) * frac, 2)
    hst = round(_cad(exp.get("hst_paid_cad")) * frac, 2)
    amt = round(float(exp.get("amount_cad", 0) or 0), 2)
    personal = min(max(round(float(exp.get("personal_use_amount_cad", 0) or 0), 2), 0.0), amt)
    cap = round(amt - personal, 2)
    total = round(gst + qst + hst, 2)
    if total > cap and total > 0:
        ratio = cap / total
        gst = round(gst * ratio, 2)
        qst = round(qst * ratio, 2)
        hst = round(hst * ratio, 2)
        drift = round(cap - (gst + qst + hst), 2)
        if drift != 0:
            if gst > 0:
                gst = round(gst + drift, 2)
            elif qst > 0:
                qst = round(qst + drift, 2)
            elif hst > 0:
                hst = round(hst + drift, 2)
    return gst, qst, hst


def _expense_net_business_cad(exp):
    """Charge nette d'affaires (feature #7.7) : ce qui va au compte de charge 5xxx et au P&L.
    = amount_cad − portion personnelle − taxes récupérables. Clamp ≥ 0. Le plafonnement des
    taxes garantit que amount − personal − taxes ≥ 0 (donc pas de clamp destructeur d'équilibre)."""
    amt = round(float(exp.get("amount_cad", 0) or 0), 2)
    personal = min(max(round(float(exp.get("personal_use_amount_cad", 0) or 0), 2), 0.0), amt)
    gst, qst, hst = _expense_recoverable_tax_cad(exp)
    return max(0.0, round(amt - personal - gst - qst - hst, 2))
```

- [ ] **Step 4: Vérifier le succès**

Run: `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_net_tax.py -q`
Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/server.py backend/tests/test_expense_net_tax.py
git commit -m "feat(F7.7-T1): helpers unifiés de taxe récupérable (50% repas, seuils 10/90)"
```

---

## Task 2 : Refactor du grand livre sur les helpers

**Files:** Modify `backend/server.py` — `_build_expense_charge_lines` (actuellement ~ligne 3063-3212) ; Test `backend/tests/test_expense_net_tax.py`

- [ ] **Step 1: Test qui échoue (équilibre + répartition repas)**

Append :

```python
def test_gl_charge_lines_meals_50pct(auth_headers):
    """Une écriture de repas récupère 50% de la taxe (12xx) et pose le reste en charge (5xxx)."""
    from backend import server
    # Org de test : on force autopost + on crée une dépense repas via l'API, puis on lit l'écriture.
    org = server.db.users.find_one({"email": "gussdub@gmail.com"})
    org_id = org.get("organization_id")
    if not org_id:
        pytest.skip("org_id indisponible")
    prev = server.db.company_settings.find_one({"organization_id": org_id}, {"_id": 0}) or {}
    server.db.company_settings.update_one({"organization_id": org_id},
        {"$set": {"autopost_enabled": True}}, upsert=True)
    exp_id = None
    try:
        r = client.post("/api/expenses", headers=auth_headers, json={
            "amount": 114.98, "currency": "CAD", "category_code": "meals_entertainment",
            "description": "Diner client", "expense_date": "2099-04-10",
            "gst_paid_cad": 5.0, "qst_paid_cad": 9.98})
        assert r.status_code in (200, 201), r.text
        exp_id = r.json()["id"]
        exp = server.db.expenses.find_one({"id": exp_id}, {"_id": 0})
        lines = server._build_expense_charge_lines(org_id, org["id"], exp)
        debits = round(sum(l.get("debit", 0) for l in lines), 2)
        credits = round(sum(l.get("credit", 0) for l in lines), 2)
        assert debits == credits == 114.98, f"équilibre: Dr {debits} Cr {credits}"
        # Charge nette 5xxx = 107.49 (net de 50% de taxe)
        # Taxes récupérables 12xx = 7.49 (50% de 14.98)
        tax_debit = round(sum(l.get("debit", 0) for l in lines
                              if _line_account_number(server, l) in ("1200", "1210", "1220")), 2)
        assert tax_debit == 7.49, f"taxes récupérables attendues 7.49, obtenu {tax_debit}"
    finally:
        if exp_id:
            client.delete(f"/api/expenses/{exp_id}", headers=auth_headers)
        server.db.company_settings.update_one({"organization_id": org_id},
            {"$set": {"autopost_enabled": prev.get("autopost_enabled", False)}})


def _line_account_number(server, line):
    acc = server.db.chart_of_accounts.find_one({"id": line.get("account_id")}, {"_id": 0, "account_number": 1})
    return acc.get("account_number") if acc else None
```

- [ ] **Step 2: Vérifier l'échec**

Run: `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_net_tax.py::test_gl_charge_lines_meals_50pct -q`
Expected: FAIL (`tax_debit == 14.98` avant refactor, attendu 7.49).

- [ ] **Step 3: Réécrire `_build_expense_charge_lines`**

Remplacer TOUT le corps de la fonction (garder la signature + le docstring, mais réécrire la logique) par la version unifiée dérivée des helpers :

```python
def _build_expense_charge_lines(org_id: str, user_id: str, expense: dict) -> list:
    """Lignes de l'écriture de charge d'une dépense (feature #7.7 — dérivé des helpers unifiés).

    Dr 5xxx (charge NETTE = amount − personal − taxes récupérables, compte résolu par catégorie,
    fallback 5900) / Dr 1200/1210/1220 (taxes récupérables : 50 % repas, prorata télécom avec
    seuils via _expense_recoverable_tax_cad) / Dr offset actionnaire (portion perso télécom, compte
    de BILAN 1300 par défaut) / Cr 1000 (Encaisse) ou 2000 (Fournisseurs) selon le flag org.

    Équilibre partie double GARANTI par construction : le total des taxes est plafonné à
    (amount − personal) par _expense_recoverable_tax_cad, donc net ≥ 0 et
    Σ débits (net + taxes + personal) == Cr amount_cad au cent exact."""
    amount_cad = round(float(expense.get("amount_cad", 0) or 0), 2)
    gst_cad, qst_cad, hst_cad = _expense_recoverable_tax_cad(expense)
    personal_cad = min(max(round(float(expense.get("personal_use_amount_cad", 0) or 0), 2), 0.0), amount_cad)
    net_cad = round(amount_cad - personal_cad - gst_cad - qst_cad - hst_cad, 2)
    if net_cad < 0:
        net_cad = 0.0  # défensif : le plafonnement des taxes garantit déjà net ≥ 0

    settings = db.company_settings.find_one({"organization_id": org_id}, {"_id": 0}) or {}
    credit_number = settings.get("expense_default_credit_account", "1000")
    if credit_number not in ("1000", "2000"):
        credit_number = "1000"

    expense_acc = _resolve_expense_account(org_id, user_id, expense.get("category_code"))
    if expense_acc is None:
        raise ValueError("Compte de charge introuvable (5900 attendu)")

    lines = []
    if net_cad > 0:
        lines.append({"account_id": expense_acc["id"], "debit": net_cad, "credit": 0.0})
    if gst_cad > 0:
        lines.append(_autopost_debit(org_id, user_id, "1200", gst_cad))
    if qst_cad > 0:
        lines.append(_autopost_debit(org_id, user_id, "1210", qst_cad))
    if hst_cad > 0:
        lines.append(_autopost_debit(
            org_id, user_id, "1220", hst_cad,
            create_if_missing=True, kind="asset", name="TVH à recouvrer"))
    if personal_cad > 0:
        # Compte offset de la portion perso : compte de BILAN (actif/passif), JAMAIS 5xxx ni taxe
        # récupérable (sinon la portion perso redeviendrait une charge / un faux CTI). Fallback 1300.
        offset_num = str(settings.get("telecom_personal_offset_account") or "1300").strip() or "1300"
        offset_kind = _account_type_for_number(offset_num) or "asset"
        offset_acc = _resolve_ledger_account(
            org_id, user_id, offset_num, create_if_missing=True,
            kind=offset_kind, name="Dû par un actionnaire")
        if (offset_acc is None or offset_acc.get("account_type") not in ("asset", "liability")
                or offset_acc.get("sub_type") == "tax_recoverable"):
            offset_acc = _resolve_ledger_account(
                org_id, user_id, "1300", create_if_missing=True,
                kind="asset", name="Dû par un actionnaire")
        lines.append({"account_id": offset_acc["id"], "debit": personal_cad, "credit": 0.0})
    lines.append(_autopost_credit(org_id, user_id, credit_number, amount_cad))
    return lines
```

- [ ] **Step 4: Vérifier le succès + non-régression GL**

Run: `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_net_tax.py -q 2>&1 | tail -3`
Expected: PASSED.

Run non-régression GL : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/ -q -k "ledger or autopost or gl or expense" --ignore=backend/tests/test_bank_reconciliation_integration.py --ignore=backend/tests/test_csv_import.py 2>&1 | tail -5`
Expected: les tests in-process PASSENT (les intégration live-serveur :8000 échouent en baseline — ignorer). **ATTENTION** : si un test existant assert l'ancien comportement repas (taxe 100 %) ou l'ancien net télécom, le mettre à jour vers le nouveau (net de 50 %/prorata) — c'est le comportement voulu par la feature. Documenter chaque test modifié dans le rapport.

- [ ] **Step 5: Commit**

```bash
git add backend/server.py backend/tests/test_expense_net_tax.py
git commit -m "feat(F7.7-T2): grand livre dérive des helpers (repas 50%, seuils télécom)"
```

---

## Task 3 : P&L net (corrige P&L + T2125 + GIFI)

**Files:** Modify `backend/server.py` — `_aggregate_pnl` (boucle expenses, ~ligne 703-717) ; Test `backend/tests/test_expense_net_tax.py`

- [ ] **Step 1: Test qui échoue (P&L net via l'API)**

Append :

```python
def test_pnl_net_of_tax(auth_headers):
    """Le P&L compte la charge NETTE : office 114.98 → gross 100.00 ; repas → 107.49 / déd. 53.75."""
    ids = []
    try:
        ids.append(client.post("/api/expenses", headers=auth_headers, json={
            "amount": 114.98, "currency": "CAD", "category_code": "office_supplies",
            "description": "Fournitures", "expense_date": "2099-07-05",
            "gst_paid_cad": 5.0, "qst_paid_cad": 9.98}).json()["id"])
        ids.append(client.post("/api/expenses", headers=auth_headers, json={
            "amount": 114.98, "currency": "CAD", "category_code": "meals_entertainment",
            "description": "Diner", "expense_date": "2099-07-06",
            "gst_paid_cad": 5.0, "qst_paid_cad": 9.98}).json()["id"])
        r = client.get("/api/reports/pnl?year=2099&basis=accrual", headers=auth_headers)
        assert r.status_code == 200, r.text
        flat = {}
        for g in r.json()["expense_groups"]:
            for c in g["categories"]:
                flat[c["code"]] = c
        assert flat["office_supplies"]["gross"] == 100.00
        assert flat["office_supplies"]["deductible"] == 100.00
        assert flat["meals_entertainment"]["gross"] == 107.49
        assert flat["meals_entertainment"]["deductible"] == 53.75  # 107.49 × 50%
    finally:
        from backend import server
        for i in ids:
            server.db.expenses.delete_one({"id": i})
```

Note : vérifier la signature réelle de `/api/reports/pnl` (paramètres `year`/`basis` ou `start`/`end`). Adapter l'URL si nécessaire (grep `@app.get("/api/reports/pnl")`). Si l'endpoint prend `start`/`end`, utiliser `?start=2099-01-01&end=2099-12-31&basis=accrual`.

- [ ] **Step 2: Vérifier l'échec**

Run: `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_net_tax.py::test_pnl_net_of_tax -q`
Expected: FAIL (gross = 114.98 avant fix).

- [ ] **Step 3: Modifier la boucle de `_aggregate_pnl`**

Localiser dans `_aggregate_pnl` le bloc (actuel) :

```python
        gross_val = float(e.get("amount_cad", 0) or 0)
        personal = e.get("personal_use_amount_cad")
        if personal is not None:
            gross_val -= float(personal or 0)
        by_code[code]["gross"] += gross_val
        by_code[code]["deductible"] += float(e.get("deductible_amount", 0) or 0)
```

Le remplacer par :

```python
        # [COMPTA] Feature #7.7 — la charge est NETTE des taxes récupérables (CTI/RTI),
        # alignée EXACTEMENT sur le grand livre (_expense_net_business_cad). La déductibilité
        # (50 % repas, etc.) s'applique AU NET. Pour le télécom, la portion affaires est déjà
        # isolée dans net_business et est 100 % déductible.
        gross_val = _expense_net_business_cad(e)
        if e.get("personal_use_amount_cad") is not None:
            ded_val = gross_val  # télécom : portion affaires nette, 100 % déductible
        else:
            pct = float(e.get("deductible_percentage", 100) or 100)
            ded_val = round(gross_val * pct / 100, 2)
        by_code[code]["gross"] += gross_val
        by_code[code]["deductible"] += ded_val
```

- [ ] **Step 4: Vérifier le succès**

Run: `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_net_tax.py::test_pnl_net_of_tax -q`
Expected: PASSED.

Run non-régression P&L/T2125/GIFI : `... -m pytest backend/tests/ -q -k "pnl or t2125 or gifi" --ignore=backend/tests/test_bank_reconciliation_integration.py --ignore=backend/tests/test_csv_import.py 2>&1 | tail -5`
Expected: PASSED (mettre à jour tout test in-process qui assert l'ancien montant TTC — c'est le comportement voulu ; documenter).

- [ ] **Step 5: Commit**

```bash
git add backend/server.py backend/tests/test_expense_net_tax.py
git commit -m "feat(F7.7-T3): P&L/T2125/GIFI comptent la charge nette de taxes"
```

---

## Task 4 : Rapport TPS/TVQ sur le helper partagé

**Files:** Modify `backend/server.py` — `_aggregate_sales_tax` (le `_itc_frac` local, ~ligne 10284-10292) ; Test `backend/tests/test_expense_net_tax.py`

- [ ] **Step 1: Test qui échoue**

Append :

```python
def test_sales_tax_meals_50_and_telecom_threshold(auth_headers):
    """CTI = 50% de la taxe repas ; télécom 8% affaires → CTI 0 (seuil ≤10%)."""
    ids = []
    try:
        ids.append(client.post("/api/expenses", headers=auth_headers, json={
            "amount": 114.98, "currency": "CAD", "category_code": "meals_entertainment",
            "description": "Diner", "expense_date": "2099-08-01",
            "gst_paid_cad": 5.0, "qst_paid_cad": 9.98}).json()["id"])
        # Télécom 8% affaires : perso 92% de 114.98 = 105.78
        ids.append(client.post("/api/expenses", headers=auth_headers, json={
            "amount": 114.98, "currency": "CAD", "category_code": "telecom_cell",
            "description": "Cell", "expense_date": "2099-08-02",
            "gst_paid_cad": 5.0, "qst_paid_cad": 9.98}).json()["id"])
        from backend import server
        server.db.expenses.update_one({"id": ids[1]}, {"$set": {"personal_use_amount_cad": 105.78}})
        r = client.get("/api/reports/sales-tax?year=2099&quarter=Q3", headers=auth_headers)
        assert r.status_code == 200, r.text
        summary = r.json()["summary"]
        # Repas seul contribue au CTI : 50% de 5.00 = 2.50 (GST) ; télécom 8% → 0.
        assert abs(summary["gst"]["paid"] - 2.50) < 0.02, summary["gst"]
        assert abs(summary["qst"]["paid"] - 4.99) < 0.02, summary["qst"]  # 50% de 9.98
    finally:
        from backend import server
        for i in ids:
            server.db.expenses.delete_one({"id": i})
```

Note : vérifier la signature réelle de `/api/reports/sales-tax` (grep) et adapter (`year`/`quarter` ou `start`/`end`). Q3 = juillet-septembre couvre les dates 2099-08.

- [ ] **Step 2: Vérifier l'échec**

Run: `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_net_tax.py::test_sales_tax_meals_50_and_telecom_threshold -q`
Expected: FAIL (CTI repas = 5.00 avant fix, attendu 2.50).

- [ ] **Step 3: Remplacer `_itc_frac` par le helper partagé**

Dans `_aggregate_sales_tax`, remplacer le bloc :

```python
    def _itc_frac(e):
        amt = float(e.get("amount_cad", 0) or 0)
        personal = e.get("personal_use_amount_cad")
        if personal is None or amt <= 0:
            return 1.0
        return max(0.0, (amt - float(personal or 0)) / amt)
    gst_paid = sum(float(e.get("gst_paid_cad", 0) or 0) * _itc_frac(e) for e in expenses)
    qst_paid = sum(float(e.get("qst_paid_cad", 0) or 0) * _itc_frac(e) for e in expenses)
    hst_paid = sum(float(e.get("hst_paid_cad", 0) or 0) * _itc_frac(e) for e in expenses)
```

par :

```python
    # [COMPTA] Feature #7.7 — le CTI/RTI récupérable utilise la SOURCE UNIQUE
    # _expense_recovery_frac : 50 % repas + prorata télécom avec seuils 10/90 (Mémo ARC 8-1).
    # Aligné sur le grand livre (mêmes taxes récupérables) et le P&L (charge nette).
    gst_paid = sum(float(e.get("gst_paid_cad", 0) or 0) * _expense_recovery_frac(e) for e in expenses)
    qst_paid = sum(float(e.get("qst_paid_cad", 0) or 0) * _expense_recovery_frac(e) for e in expenses)
    hst_paid = sum(float(e.get("hst_paid_cad", 0) or 0) * _expense_recovery_frac(e) for e in expenses)
```

- [ ] **Step 4: Vérifier le succès**

Run: `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_net_tax.py -q 2>&1 | tail -3`
Expected: PASSED.

Run non-régression taxes : `... -m pytest backend/tests/ -q -k "sales_tax or tax_report" --ignore=backend/tests/test_bank_reconciliation_integration.py --ignore=backend/tests/test_csv_import.py 2>&1 | tail -5`
Expected: PASSED (mettre à jour les tests in-process assertant l'ancien CTI repas/télécom).

- [ ] **Step 5: Commit**

```bash
git add backend/server.py backend/tests/test_expense_net_tax.py
git commit -m "feat(F7.7-T4): rapport TPS/TVQ via _expense_recovery_frac (50% repas, seuils)"
```

---

## Task 5 : Réconciliation GL↔P&L simplifiée

**Files:** Modify `backend/server.py` — `ledger_reconciliation` (formule `expenses_diff`, ~ligne 5776-5778 + commentaires ~5719-5726) ; Test `backend/tests/test_expense_net_tax.py`

- [ ] **Step 1: Test qui échoue**

Append :

```python
def test_reconciliation_balanced_after_net(auth_headers):
    """Après le fix, P&L net == GL net → expenses_diff ≈ 0 (org autopost activé)."""
    from backend import server
    org = server.db.users.find_one({"email": "gussdub@gmail.com"})
    org_id = org.get("organization_id")
    if not org_id:
        pytest.skip("org_id indisponible")
    prev = (server.db.company_settings.find_one({"organization_id": org_id}, {"_id": 0}) or {}).get("autopost_enabled", False)
    server.db.company_settings.update_one({"organization_id": org_id},
        {"$set": {"autopost_enabled": True}}, upsert=True)
    exp_id = None
    try:
        exp_id = client.post("/api/expenses", headers=auth_headers, json={
            "amount": 114.98, "currency": "CAD", "category_code": "meals_entertainment",
            "description": "Recon diner", "expense_date": "2099-09-15",
            "gst_paid_cad": 5.0, "qst_paid_cad": 9.98}).json()["id"]
        r = client.get("/api/ledger/reconciliation?start=2099-09-01&end=2099-09-30", headers=auth_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert abs(data["expenses"]["diff"]) < 0.02, data["expenses"]
    finally:
        if exp_id:
            client.delete(f"/api/expenses/{exp_id}", headers=auth_headers)
        server.db.company_settings.update_one({"organization_id": org_id},
            {"$set": {"autopost_enabled": prev}})
```

Note : vérifier la forme réelle du JSON de `/api/ledger/reconciliation` (clé `expenses.diff`). Adapter si la structure diffère.

- [ ] **Step 2: Vérifier l'échec ou la réussite fortuite**

Run: `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_net_tax.py::test_reconciliation_balanced_after_net -q`
Expected : peut échouer si la formule actuelle (`pnl_gross − (gl_net + recoverable)`) ne vaut plus 0 maintenant que `pnl_gross` est net. C'est le point à corriger.

- [ ] **Step 3: Corriger la formule + commentaires**

Localiser (actuel) :

```python
    revenue_diff = round(revenue_pnl - revenue_gl, 2)
    # diff dépenses = brut P&L − (charge nette GL + taxes récupérables) ≈ 0.
    expenses_diff = round(
        expenses_pnl_gross - (expenses_gl_net + recoverable_taxes), 2)
```

Remplacer par :

```python
    revenue_diff = round(revenue_pnl - revenue_gl, 2)
    # [COMPTA] Feature #7.7 — le P&L compte désormais la charge NETTE des taxes récupérables
    # (comme le grand livre) : expenses_pnl_gross == expenses_gl_net directement. Les taxes
    # récupérables (recoverable_taxes) restent exposées comme LIGNE INFORMATIVE (12xx), plus
    # dans l'équation d'équilibre.
    expenses_diff = round(expenses_pnl_gross - expenses_gl_net, 2)
```

Mettre aussi à jour le docstring de `ledger_reconciliation` : dans la puce « Dépenses », remplacer la mention « `expenses.pnl_gross` = Σ `amount_cad` TTC (vue gestion P&L) » et le paragraphe « ÉCART STRUCTUREL ASSUMÉ » par : « `expenses.pnl_gross` = Σ charge nette (feature #7.7, alignée sur le GL) ; `gl_net` = Σ débits 5xxx ; les deux concordent directement ; `recoverable_taxes` (débits 12xx) est informatif. »

- [ ] **Step 4: Vérifier le succès**

Run: `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_net_tax.py::test_reconciliation_balanced_after_net -q`
Expected: PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/server.py backend/tests/test_expense_net_tax.py
git commit -m "feat(F7.7-T5): réconciliation GL↔P&L simplifiée (P&L net == GL net)"
```

---

## Task 6 : Migration idempotente (re-snapshot déductible + re-post repas)

**Files:** Modify `backend/server.py` — nouvelle `migrate_expense_net_tax_v1()` + appel startup ; Test `backend/tests/test_expense_net_tax.py`

- [ ] **Step 1: Test qui échoue**

Append :

```python
def test_migration_reposts_meals_gl_idempotent(auth_headers):
    """Une écriture de repas legacy (taxe récupérée 100%) est re-postée à 50% ; 2e passage no-op."""
    from backend import server
    org = server.db.users.find_one({"email": "gussdub@gmail.com"})
    org_id = org.get("organization_id")
    if not org_id:
        pytest.skip("org_id indisponible")
    prev = (server.db.company_settings.find_one({"organization_id": org_id}, {"_id": 0}) or {}).get("autopost_enabled", False)
    server.db.company_settings.update_one({"organization_id": org_id},
        {"$set": {"autopost_enabled": True}}, upsert=True)
    exp_id = None
    try:
        exp_id = client.post("/api/expenses", headers=auth_headers, json={
            "amount": 114.98, "currency": "CAD", "category_code": "meals_entertainment",
            "description": "Migr diner", "expense_date": "2099-10-01",
            "gst_paid_cad": 5.0, "qst_paid_cad": 9.98}).json()["id"]
        # Simuler l'ancien snapshot déductible TTC (57.49 = 50% de 114.98)
        server.db.expenses.update_one({"id": exp_id}, {"$set": {"deductible_amount": 57.49}})
        stats = server.migrate_expense_net_tax_v1()
        assert stats["resnapshotted"] >= 1 or stats["reposted"] >= 1
        exp = server.db.expenses.find_one({"id": exp_id}, {"_id": 0})
        assert exp["deductible_amount"] == 53.75, exp["deductible_amount"]  # 107.49 × 50%
        # Idempotence : 2e passage ne re-snapshotte plus cette dépense
        stats2 = server.migrate_expense_net_tax_v1()
        assert exp_id not in stats2.get("resnapshotted_ids", [])
    finally:
        if exp_id:
            client.delete(f"/api/expenses/{exp_id}", headers=auth_headers)
        server.db.company_settings.update_one({"organization_id": org_id},
            {"$set": {"autopost_enabled": prev}})
```

- [ ] **Step 2: Vérifier l'échec**

Run: `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_net_tax.py::test_migration_reposts_meals_gl_idempotent -q`
Expected: FAIL (`ImportError: migrate_expense_net_tax_v1`).

- [ ] **Step 3: Ajouter la migration**

Insérer après `_expense_net_business_cad` (ou près des autres migrations). Code :

```python
def migrate_expense_net_tax_v1():
    """Migration idempotente (feature #7.7) — recale les dérivés des dépenses vers le net de taxes :
    1. Re-snapshot `deductible_amount` = net déductible (net_business, × déductibilité hors télécom).
       Idempotent : ne réécrit que si l'écart > 0,01.
    2. Re-post GL des dépenses AFFECTÉES (repas OU télécom avec personal_use) via _repost_expense_gl
       (déjà idempotent, gaté sur autopost_enabled). Les dépenses normales ne changent pas → non re-postées.

    Ne modifie JAMAIS amount_cad ni les champs de taxe saisis. Retourne des compteurs + ids touchés."""
    resnapshotted = 0
    reposted = 0
    resnapshotted_ids = []
    settings_cache = {}
    for exp in db.expenses.find({"amount_cad": {"$exists": True}}, {"_id": 0}):
        net = _expense_net_business_cad(exp)
        if exp.get("personal_use_amount_cad") is not None:
            new_ded = net
        else:
            pct = float(exp.get("deductible_percentage", 100) or 100)
            new_ded = round(net * pct / 100, 2)
        old_ded = round(float(exp.get("deductible_amount", 0) or 0), 2)
        if abs(new_ded - old_ded) > 0.01:
            db.expenses.update_one({"id": exp["id"]}, {"$set": {"deductible_amount": new_ded}})
            resnapshotted += 1
            resnapshotted_ids.append(exp["id"])
        # Re-post GL uniquement pour les catégories dont l'écriture change (repas + télécom mixte).
        is_meals = exp.get("category_code") == "meals_entertainment"
        is_telecom_mixed = exp.get("personal_use_amount_cad") is not None
        if is_meals or is_telecom_mixed:
            org_id = exp.get("organization_id")
            if not org_id:
                continue
            if org_id not in settings_cache:
                settings_cache[org_id] = db.company_settings.find_one(
                    {"organization_id": org_id}, {"_id": 0}) or {}
            if settings_cache[org_id].get("autopost_enabled"):
                try:
                    _repost_expense_gl(org_id, exp.get("created_by_user_id") or exp.get("user_id"),
                                       exp["id"], exp)
                    reposted += 1
                except Exception:
                    pass
    return {"resnapshotted": resnapshotted, "reposted": reposted, "resnapshotted_ids": resnapshotted_ids}
```

**Note idempotence re-post** : `_repost_expense_gl` régénère l'écriture depuis `_build_expense_charge_lines` (déjà corrigé). Au 2ᵉ passage, il contre-passe l'écriture vivante et re-poste la MÊME (le net ne change plus) → pas de dérive. C'est acceptable (best-effort). Le compteur `reposted` peut donc rester > 0 aux passages suivants, mais `resnapshotted` tombe à 0 (garde d'idempotence testée).

- [ ] **Step 4: Enregistrer au startup**

Dans le handler `@app.on_event("startup")` (chercher `seed_data` / les autres `migrate_*`), ajouter après les migrations existantes :

```python
    # Feature #7.7 — recale les dépenses vers le net de taxes (déductible + re-post repas).
    try:
        migrate_expense_net_tax_v1()
    except Exception:
        pass
```

- [ ] **Step 5: Vérifier le succès**

Run: `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_net_tax.py -q 2>&1 | tail -3`
Expected: PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/server.py backend/tests/test_expense_net_tax.py
git commit -m "feat(F7.7-T6): migration idempotente (re-snapshot déductible + re-post repas)"
```

---

## Task 7 : Frontend — « Calculer auto » couvre le télécom + libellé

**Files:** Modify `frontend/src/pages/ExpensesPage.js`

- [ ] **Step 1: Localiser le bouton « Calculer auto »**

Run: `cd frontend/src && grep -n "Calculer auto\|computeTaxes\|calculer_auto\|gst_paid_cad\|taxes_auto" pages/ExpensesPage.js | head -20`

Comprendre : (a) où le bouton calcule les taxes, (b) s'il exclut telecom_cell/telecom_internet, (c) comment il pose gst/qst/hst dans le state du formulaire.

- [ ] **Step 2: S'assurer que le télécom est couvert**

Si un test type `category_code !== 'telecom_cell'` empêche le calcul auto pour le télécom, le retirer — le calcul de taxes (`_compute_taxes_paid`, diviseur provincial) s'applique à toute dépense taxable, télécom inclus. Le calcul auto doit remplir `gst_paid_cad`/`qst_paid_cad`/`hst_paid_cad` à partir du montant TTC saisi et de la province, pour le télécom comme pour le reste.

Si le calcul auto est déjà générique (aucune exclusion), aucune modif de logique — passer au libellé (Step 3).

- [ ] **Step 3: Ajouter un libellé d'aide**

Près de la section « Taxes payées » du formulaire de dépense, ajouter un texte d'aide (adapter au style inline existant) :

```jsx
<p style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>
  Le montant saisi est TTC (taxes incluses). Les taxes récupérables (CTI/RTI) sont
  automatiquement sorties du coût déductible dans les rapports.
</p>
```

- [ ] **Step 4: Build CI**

Run (depuis `frontend/`) : `CI=true GENERATE_SOURCEMAP=false npx --no-install react-scripts build 2>&1 | grep -E "Compiled|Failed|Line " | head -5`
Expected: `Compiled successfully.`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ExpensesPage.js
git commit -m "feat(F7.7-T7): calcul auto des taxes couvre le télécom + libellé TTC/net"
```

---

## Task 8 : E2E + revue adversariale + changelog + push

**Files:** Modify `CLAUDE.md`

- [ ] **Step 1: Suite backend complète**

Run: `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/ -q -k "expense or tax or pnl or t2125 or gifi or ledger or sales or bank" --ignore=backend/tests/test_bank_reconciliation_integration.py --ignore=backend/tests/test_csv_import.py --ignore=backend/tests/test_expense_categories_integration.py --ignore=backend/tests/test_receipt_ocr_integration.py --ignore=backend/tests/test_new_features_iteration7.py --ignore=backend/tests/test_pnl_report_integration.py --ignore=backend/tests/test_tax_report_integration.py --ignore=backend/tests/test_multi_currency.py 2>&1 | tail -3`
Expected: tout PASSED (in-process). Corriger tout test in-process encore rouge (mise à jour vers le comportement net documenté).

- [ ] **Step 2: Build frontend**

Run (depuis `frontend/`) : `CI=true GENERATE_SOURCEMAP=false npx --no-install react-scripts build 2>&1 | grep -E "Compiled|Failed" | head -3`
Expected: `Compiled successfully.`

- [ ] **Step 3: Revue adversariale opus (OBLIGATOIRE — money-critical)**

Le CONTRÔLEUR lance une revue adversariale (Workflow opus) du diff complet feature #7.7, ciblant : équilibre partie double du GL (Σdébits==crédit sur tous les cas : repas, télécom seuils, devise étrangère, taxes aberrantes) ; double-application de fraction (recovery_frac appliqué deux fois) ; cohérence GL == P&L == taxes (le même net partout) ; arrondis (le cap + drift) ; idempotence de la migration ; régressions sur les dépenses normales. Corriger tout finding CONFIRMED avant de continuer.

- [ ] **Step 4: Changelog CLAUDE.md**

Sous `## Features livrées`, insérer en tête :

```markdown
- **2026-07-08 — Dépenses nettes des taxes récupérables (feature #7.7)**
  - **Problème (comptable)** : le P&L / T2125 / GIFI comptaient les dépenses au montant TTC (taxes incluses), alors qu'un inscrit TPS/TVQ doit déduire le NET — la taxe récupérable (CTI/RTI) se récupère via la déclaration de taxes, pas à l'impôt. Résultat : dépenses sur-estimées, revenu imposable sous-estimé (double récupération de la taxe). Validé ARC (T4002, Mémo 8-1) + Revenu Québec (IN-203).
  - **Correctif** : helper unifié `_expense_recovery_frac` (source unique : 50 % repas, prorata télécom avec seuils ARC ≤10 %→0 / ≥90 %→100 %) → le grand livre, le P&L et le rapport TPS/TVQ dérivent tous de la MÊME charge nette (`_expense_net_business_cad`). Réconciliation GL↔P&L simplifiée (P&L net == GL net directement).
  - **Repas** : la limite ITC 50 % est désormais appliquée (le GL récupérait 100 % à tort) — écritures de repas re-postées par la migration.
  - **Migration** idempotente au startup : re-snapshot du déductible + re-post GL des dépenses repas/télécom. Aucun montant ni champ de taxe saisi modifié.
  - **Impact voulu** : rapports P&L/T2125/GIFI plus bas (nets), revenu net plus haut, CTI repas ramené à 50 %.
  - Tests : `test_expense_net_tax.py` (helpers, net, équilibre GL, P&L, taxes, réconciliation, migration idempotente) + revue adversariale opus.
```

- [ ] **Step 5: Commit changelog**

```bash
git add CLAUDE.md
git commit -m "docs(F7.7-T8): changelog dépenses nettes de taxes"
```

- [ ] **Step 6: Confirmation utilisateur avant push**

Utiliser `AskUserQuestion` : « Je pousse la feature #7.7 (dépenses nettes de taxes + migration qui re-poste les écritures de repas) en prod ? » — options « Oui, pousse » / « Non, local ».

- [ ] **Step 7: Si approuvé — push**

Run: `git push origin main 2>&1 | tail -2`

Rapporter : commits F7.7 poussés ; Render redémarre + migration ; vérifier après déploiement que les rapports affichent des dépenses nettes et le CTI repas à 50 %.
