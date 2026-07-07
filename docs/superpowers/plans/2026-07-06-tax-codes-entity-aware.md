# Codes fiscaux adaptés au type d'entité (feature #7.6) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faire porter à chaque catégorie de dépense deux codes fiscaux (T2125 pour travailleur autonome, GIFI pour société), afficher le bon dans le picker selon `entity_type`, corriger les codes ARC erronés (bank/subscriptions/subcontracts/advertising) et livrer un rapport « Sommaire GIFI » pour les sociétés.

**Architecture:** Le modèle `EXPENSE_CATEGORIES` porte désormais `t2125_line` + `t2125_label_fr` + `gifi_code` + `gifi_label_en`. Le snapshot figé sur chaque dépense inclut les deux codes ; `category_arc_line` reste snapshoté (aligné sur `t2125_line`) pour la rétrocompat du rapport T2125. Une migration idempotente au startup ré-annote les dépenses historiques.

**Tech Stack:** FastAPI + pymongo (sync), React 18 (CRA, inline styles, hook `useIsMobile`), tests pytest in-process via `TestClient`, MongoDB local (`mongodb://localhost:27017`) pour les tests, venv `.venv-test/`.

Spec de référence : [`docs/superpowers/specs/2026-07-06-tax-codes-entity-aware-design.md`](../specs/2026-07-06-tax-codes-entity-aware-design.md).

---

## Structure des fichiers

**Backend** (tout dans `backend/server.py` — monolithique, on suit le pattern) :
- `EXPENSE_CATEGORIES` (L156) : remplacer `arc_line` par les 4 nouveaux champs.
- `_build_expense_category_snapshot` (L356) : émettre les 4 nouveaux champs + `category_arc_line` = `t2125_line` (legacy).
- `T2125_LINE_LABELS` (L7077) : ajouter 8521, 8710, 8760, retirer 8520/8620/8740/9367.
- `_flatten_pnl_expenses` (rename de `_t2125_flatten_pnl_expenses`, L7103) : lecture agnostique du régime.
- Nouveau `_gifi_group_by_code` (parallèle à `_t2125_group_by_arc_line`, L7121).
- Nouveau `_build_gifi_report` (parallèle à `_build_t2125_report`).
- Nouveaux endpoints `GET /api/reports/gifi[/csv|/pdf]`.
- `_render_t2125_pdf` (L10562) : généraliser en `_render_tax_summary_pdf(report, kind)`.
- Nouveau `migrate_expense_tax_codes_v1()` appelé au startup.

**Tests backend** :
- Nouveau : `backend/tests/test_expense_tax_codes.py`.

**Frontend** :
- `frontend/src/pages/ExpensesPage.js` : picker enrichi selon `entity_type`.
- `frontend/src/components/BankCreateExpenseModal.js` : idem picker.
- Nouveau : `frontend/src/components/GifiReportSection.js` (miroir de `T2125ReportSection.js`).
- `frontend/src/pages/ReportsPage.js` : onglet GIFI conditionnel.

**Docs** :
- `CLAUDE.md` : entrée changelog feature #7.6.

---

## Contexte technique à connaître

- **Env de test** : `.venv-test/bin/python` (Python 3.11 avec toutes les deps installées). MongoDB local doit tourner (`mongod`). Commande de test : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest <path> -q`.
- **Compte de test** : `email=gussdub@gmail.com`, `password=testpass123` — pattern déjà utilisé partout dans les tests existants (voir `test_bank_expense_automatch.py`).
- **Pattern des tests d'intégration** : `TestClient(app)` in-process, avec fixture `auth_headers` qui login puis retourne `{"Authorization": f"Bearer {token}"}`. Nettoyage dans `finally` avec `db.expenses.delete_one(...)`.
- **Frontend build check** : AVANT tout push, obligatoire : `CI=true GENERATE_SOURCEMAP=false npx --no-install react-scripts build` depuis `frontend/`. Sinon Vercel casse (leçon apprise).
- **Push prod** : `git push origin main` déploie automatiquement Render (backend) + Vercel (frontend). Confirmer avec l'utilisateur avant tout push.
- **Migrations** : enregistrées dans le handler `@app.on_event("startup")` (L10673). Idempotentes.

---

## Task 0 : Créer le fichier de tests vide

**Files:**
- Create: `backend/tests/test_expense_tax_codes.py`

- [ ] **Step 1: Créer le fichier avec l'entête et la fixture auth**

```python
"""Tests — codes fiscaux adaptés au type d'entité (feature #7.6).

Vérifie que :
- EXPENSE_CATEGORIES porte les 4 nouveaux champs (t2125_line, gifi_code, etc.).
- Le snapshot de dépense fige les deux codes + garde category_arc_line legacy.
- La migration migrate_expense_tax_codes_v1 corrige les codes ARC erronés + ajoute
  les nouveaux champs sur les dépenses historiques.
- Le rapport GIFI agrège par category_gifi_code.
- Le rapport T2125 continue de fonctionner (rétrocompat via category_arc_line).
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

- [ ] **Step 2: Vérifier le collect pytest**

Run : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_tax_codes.py --collect-only -q`
Expected : `no tests collected` (pas d'erreur d'import).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_expense_tax_codes.py
git commit -m "test(bank): stub tests fichier pour codes fiscaux entity-aware (F7.6-T0)"
```

---

## Task 1 : Enrichir EXPENSE_CATEGORIES avec T2125 + GIFI

**Files:**
- Modify: `backend/server.py:156-183` (EXPENSE_CATEGORIES)
- Test: `backend/tests/test_expense_tax_codes.py`

- [ ] **Step 1: Écrire le test qui échoue**

Append à `backend/tests/test_expense_tax_codes.py` :

```python
def test_expense_categories_have_dual_codes():
    """Chaque catégorie porte les 4 nouveaux champs (t2125_line + t2125_label_fr +
    gifi_code + gifi_label_en) et n'a PLUS de arc_line."""
    from backend.server import EXPENSE_CATEGORIES
    required = {"code", "label_fr", "label_en", "t2125_line", "t2125_label_fr",
                "gifi_code", "gifi_label_en", "deductible_percentage", "group"}
    for cat in EXPENSE_CATEGORIES:
        missing = required - set(cat.keys())
        assert not missing, f"{cat['code']} manque {missing}"
        assert "arc_line" not in cat, f"{cat['code']} porte encore l'ancien arc_line"


def test_expense_categories_correct_codes():
    """Codes fiscaux corrigés par la revue adversariale multi-sources CRA."""
    from backend.server import EXPENSE_CATEGORIES
    by = {c["code"]: c for c in EXPENSE_CATEGORIES}
    # Corrections dues aux erreurs historiques
    assert by["bank_charges"]["t2125_line"] == "8710"
    assert by["bank_charges"]["gifi_code"] == "8715"
    assert by["subscriptions"]["t2125_line"] == "8760"
    assert by["subscriptions"]["gifi_code"] == "8810"
    assert by["subcontracts"]["t2125_line"] == "9060"  # pas de ligne T2125 dédiée
    assert by["subcontracts"]["gifi_code"] == "9110"
    # T2125 8521 ≠ GIFI 8520 pour la pub (à 1 chiffre d'écart)
    assert by["advertising"]["t2125_line"] == "8521"
    assert by["advertising"]["gifi_code"] == "8520"
    # Télécom : T2125 pas de ligne dédiée (convention 9220), GIFI granulaire
    assert by["telecom_cell"]["gifi_code"] == "9225"
    assert by["telecom_internet"]["gifi_code"] == "9152"
```

- [ ] **Step 2: Vérifier que les tests échouent**

Run : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_tax_codes.py -q`
Expected : 2 FAILED avec `KeyError: 't2125_line'` et `arc_line` encore présent.

- [ ] **Step 3: Remplacer EXPENSE_CATEGORIES**

Ouvrir `backend/server.py` ligne 156. Remplacer les lignes 156 à 183 par :

```python
EXPENSE_CATEGORIES = [
    # code, label_fr, label_en, t2125_line, t2125_label_fr, gifi_code, gifi_label_en, deductible_percentage, group
    # Bureau
    {"code": "office_expenses",    "label_fr": "Frais de bureau",         "label_en": "Office expenses",
     "t2125_line": "8810", "t2125_label_fr": "Frais de bureau",
     "gifi_code":  "8810", "gifi_label_en": "Office expenses",
     "deductible_percentage": 100, "group": "office"},
    {"code": "office_supplies",    "label_fr": "Fournitures",             "label_en": "Office supplies",
     "t2125_line": "8811", "t2125_label_fr": "Papeterie et fournitures de bureau",
     "gifi_code":  "8811", "gifi_label_en": "Office stationery and supplies",
     "deductible_percentage": 100, "group": "office"},
    {"code": "professional_fees",  "label_fr": "Honoraires professionnels","label_en": "Professional fees",
     "t2125_line": "8860", "t2125_label_fr": "Honoraires professionnels",
     "gifi_code":  "8860", "gifi_label_en": "Professional fees",
     "deductible_percentage": 100, "group": "office"},
    {"code": "bank_charges",       "label_fr": "Frais bancaires",         "label_en": "Bank charges",
     "t2125_line": "8710", "t2125_label_fr": "Intérêts et frais bancaires",
     "gifi_code":  "8715", "gifi_label_en": "Bank charges",
     "deductible_percentage": 100, "group": "office"},
    {"code": "subscriptions",      "label_fr": "Abonnements et licences", "label_en": "Subscriptions & licences",
     "t2125_line": "8760", "t2125_label_fr": "Taxes d'affaires, droits d'adhésion et licences",
     "gifi_code":  "8810", "gifi_label_en": "Office expenses",
     "deductible_percentage": 100, "group": "office"},
    {"code": "telecom_cell",       "label_fr": "Télécom — cellulaire",    "label_en": "Telecom — mobile",
     "t2125_line": "9220", "t2125_label_fr": "Services publics",
     "gifi_code":  "9225", "gifi_label_en": "Telephone and telecommunications",
     "deductible_percentage": 100, "group": "office"},
    {"code": "telecom_internet",   "label_fr": "Télécom — internet",      "label_en": "Telecom — internet",
     "t2125_line": "9220", "t2125_label_fr": "Services publics",
     "gifi_code":  "9152", "gifi_label_en": "Internet",
     "deductible_percentage": 100, "group": "office"},
    # Marketing
    {"code": "advertising",        "label_fr": "Publicité et promotion",  "label_en": "Advertising & promotion",
     "t2125_line": "8521", "t2125_label_fr": "Publicité",
     "gifi_code":  "8520", "gifi_label_en": "Advertising and promotion",
     "deductible_percentage": 100, "group": "marketing"},
    {"code": "meals_entertainment","label_fr": "Repas et représentation", "label_en": "Meals & entertainment",
     "t2125_line": "8523", "t2125_label_fr": "Repas et frais de représentation",
     "gifi_code":  "8523", "gifi_label_en": "Meals and entertainment",
     "deductible_percentage": 50,  "group": "marketing"},
    # Locaux
    {"code": "rent",               "label_fr": "Loyer",                   "label_en": "Rent",
     "t2125_line": "8910", "t2125_label_fr": "Loyer",
     "gifi_code":  "8910", "gifi_label_en": "Rental",
     "deductible_percentage": 100, "group": "premises"},
    {"code": "utilities",          "label_fr": "Services publics",        "label_en": "Utilities",
     "t2125_line": "9220", "t2125_label_fr": "Services publics",
     "gifi_code":  "9220", "gifi_label_en": "Utilities",
     "deductible_percentage": 100, "group": "premises"},
    {"code": "insurance",          "label_fr": "Assurances",              "label_en": "Insurance",
     "t2125_line": "8690", "t2125_label_fr": "Assurances",
     "gifi_code":  "8690", "gifi_label_en": "Insurance",
     "deductible_percentage": 100, "group": "premises"},
    {"code": "repairs_maintenance","label_fr": "Entretien et réparations","label_en": "Repairs & maintenance",
     "t2125_line": "8960", "t2125_label_fr": "Entretien et réparations",
     "gifi_code":  "8960", "gifi_label_en": "Repairs and maintenance",
     "deductible_percentage": 100, "group": "premises"},
    # Déplacements
    {"code": "travel",             "label_fr": "Frais de déplacement",    "label_en": "Travel",
     "t2125_line": "9200", "t2125_label_fr": "Frais de déplacement",
     "gifi_code":  "9200", "gifi_label_en": "Travel expenses",
     "deductible_percentage": 100, "group": "travel"},
    {"code": "vehicle_expenses",   "label_fr": "Frais de véhicule",       "label_en": "Vehicle expenses",
     "t2125_line": "9281", "t2125_label_fr": "Frais de véhicule à moteur",
     "gifi_code":  "9281", "gifi_label_en": "Vehicle expenses",
     "deductible_percentage": 100, "group": "travel"},
    {"code": "delivery",           "label_fr": "Livraison et fret",       "label_en": "Delivery & freight",
     "t2125_line": "9275", "t2125_label_fr": "Livraison, transport et messagerie",
     "gifi_code":  "9275", "gifi_label_en": "Delivery, freight and express",
     "deductible_percentage": 100, "group": "travel"},
    # Personnel
    {"code": "salaries",           "label_fr": "Salaires et avantages",   "label_en": "Salaries & benefits",
     "t2125_line": "9060", "t2125_label_fr": "Salaires, traitements et avantages",
     "gifi_code":  "9060", "gifi_label_en": "Salaries and wages",
     "deductible_percentage": 100, "group": "personnel"},
    {"code": "subcontracts",       "label_fr": "Sous-traitance",          "label_en": "Subcontracts",
     "t2125_line": "9060", "t2125_label_fr": "Salaires, traitements et avantages",
     "gifi_code":  "9110", "gifi_label_en": "Sub-contracts",
     "deductible_percentage": 100, "group": "personnel"},
    {"code": "management_fees",    "label_fr": "Frais de gestion",        "label_en": "Management fees",
     "t2125_line": "8871", "t2125_label_fr": "Frais de gestion et d'administration",
     "gifi_code":  "8871", "gifi_label_en": "Management and administration fees",
     "deductible_percentage": 100, "group": "personnel"},
    # Autre
    {"code": "other",              "label_fr": "Autre",                   "label_en": "Other",
     "t2125_line": "9270", "t2125_label_fr": "Autres dépenses",
     "gifi_code":  "9270", "gifi_label_en": "Other expenses",
     "deductible_percentage": 100, "group": "other"},
]
```

- [ ] **Step 2b: Recalibrer T2125_LINE_LABELS**

Ouvrir `backend/server.py` ligne 7077. Remplacer les lignes 7077 à 7100 par :

```python
T2125_LINE_LABELS = {
    # Revenu
    "8000": "Recettes brutes",
    # Dépenses — libellés officiels ARC (T2125 F(24))
    "8521": "Publicité",
    "8523": "Repas et frais de représentation",
    "8690": "Assurances",
    "8710": "Intérêts et frais bancaires",
    "8760": "Taxes d'affaires, droits d'adhésion et licences",
    "8810": "Frais de bureau",
    "8811": "Papeterie et fournitures de bureau",
    "8860": "Honoraires professionnels",
    "8871": "Frais de gestion et d'administration",
    "8910": "Loyer",
    "8960": "Entretien et réparations",
    "9060": "Salaires, traitements et avantages",
    "9200": "Frais de déplacement",
    "9220": "Services publics",
    "9270": "Autres dépenses",
    "9275": "Livraison, transport et messagerie",
    "9281": "Frais de véhicule à moteur",
    "9945": "Frais d'utilisation de la résidence aux fins de l'entreprise",
}
```

- [ ] **Step 3: Corriger les autres lecteurs de `arc_line`**

Aux lignes 379 et 382 (dans `_build_expense_category_snapshot`), et 591 et 655 (autres lecteurs) : remplacer toute lecture de `cat["arc_line"]` ou `cat.get("arc_line")` par `cat["t2125_line"]` ou `cat.get("t2125_line", "")`.

Utiliser Grep pour lister tous les usages puis Edit chacun :

Run : `cd backend && grep -n '\["arc_line"\]\|\.get("arc_line"' server.py`

Pour chaque hit, appliquer le remplacement `arc_line → t2125_line` (tuple `arc_line`, `arc_line = "..."`, etc. — pas les `category_arc_line` qui restent, ils sont sur le snapshot pas sur `cat`).

- [ ] **Step 4: Vérifier les tests passent**

Run : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_tax_codes.py -q`
Expected : 2 PASSED.

- [ ] **Step 5: Vérifier qu'on n'a pas cassé les tests existants**

Run : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/ -q -k "expense or bank or t2125 or pnl" --ignore=backend/tests/test_bank_reconciliation_integration.py --ignore=backend/tests/test_csv_import.py`
Expected : tout PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/server.py backend/tests/test_expense_tax_codes.py
git commit -m "feat(F7.6-T1): EXPENSE_CATEGORIES porte t2125_line + gifi_code (codes ARC corrigés)"
```

---

## Task 2 : Snapshot avec les deux codes (rétrocompat category_arc_line)

**Files:**
- Modify: `backend/server.py:356-407` (_build_expense_category_snapshot)
- Test: `backend/tests/test_expense_tax_codes.py`

- [ ] **Step 1: Écrire le test qui échoue**

Append à `backend/tests/test_expense_tax_codes.py` :

```python
def test_snapshot_writes_dual_codes():
    """Le snapshot fige category_t2125_line + category_gifi_code + garde
    category_arc_line pour la rétrocompat du rapport T2125."""
    from backend.server import _build_expense_category_snapshot
    snap = _build_expense_category_snapshot({"category_code": "subscriptions"}, 100.0)
    assert snap["category_t2125_line"] == "8760"
    assert snap["category_t2125_label_fr"] == "Taxes d'affaires, droits d'adhésion et licences"
    assert snap["category_gifi_code"] == "8810"
    assert snap["category_gifi_label_en"] == "Office expenses"
    # Rétrocompat : category_arc_line = category_t2125_line
    assert snap["category_arc_line"] == "8760"


def test_snapshot_other_code_empty_gifi_ok():
    """Le code 'other' a un gifi/t2125 dédiés (9270) — pas de champ vide."""
    from backend.server import _build_expense_category_snapshot
    snap = _build_expense_category_snapshot({"category_code": "other"}, 50.0)
    assert snap["category_t2125_line"] == "9270"
    assert snap["category_gifi_code"] == "9270"


def test_snapshot_unknown_code_graceful():
    """Un code inconnu → snapshot avec champs vides (comportement legacy conservé)."""
    from backend.server import _build_expense_category_snapshot
    snap = _build_expense_category_snapshot(
        {"category_code": "totally_made_up", "category": "Mon label libre"}, 10.0)
    assert snap["category_t2125_line"] == ""
    assert snap["category_gifi_code"] == ""
    assert snap["category_arc_line"] == ""
```

- [ ] **Step 2: Vérifier les tests échouent**

Run : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_tax_codes.py::test_snapshot_writes_dual_codes -q`
Expected : FAILED (KeyError `category_t2125_line`).

- [ ] **Step 3: Modifier `_build_expense_category_snapshot`**

Ouvrir `backend/server.py:356`. Remplacer la fonction entière (jusqu'à `return snapshot`, environ L407) par :

```python
def _build_expense_category_snapshot(expense_data, amount_cad, telecom_business_pct=None):
    """Retourne les champs catégorie à snapshoter dans une dépense.

    Args:
        expense_data: dict envoyé par le frontend (peut contenir category_code,
                      category_custom_label, ou un legacy 'category' libre).
        amount_cad: montant déjà converti en CAD (calcul indépendant de la devise).

    Returns:
        dict avec category, category_code, category_custom_label,
        category_t2125_line, category_t2125_label_fr,
        category_gifi_code, category_gifi_label_en,
        category_arc_line (LEGACY = category_t2125_line pour rétrocompat rapport T2125),
        deductible_percentage, deductible_amount.

    Comportement :
    - Si category_code est un code canonique → snapshot depuis le catalogue.
    - Si category_code == "other" → utilise category_custom_label (fallback "Autre") ;
      les codes T2125/GIFI = 9270 (Autres dépenses).
    - Sinon (vide, inconnu) → graceful : reprend le label legacy "category",
      t2125/gifi/arc_line = "", percentage = 100.
    """
    code = (expense_data.get("category_code") or "").strip()
    custom_label = expense_data.get("category_custom_label", "").strip()
    cat = _find_category(code)
    if code == "other":
        label = custom_label or "Autre"
        t2125_line = cat["t2125_line"] if cat else "9270"
        t2125_label_fr = cat["t2125_label_fr"] if cat else "Autres dépenses"
        gifi_code = cat["gifi_code"] if cat else "9270"
        gifi_label_en = cat["gifi_label_en"] if cat else "Other expenses"
        percentage = 100
    elif cat:
        label = cat["label_fr"]
        t2125_line = cat["t2125_line"]
        t2125_label_fr = cat["t2125_label_fr"]
        gifi_code = cat["gifi_code"]
        gifi_label_en = cat["gifi_label_en"]
        percentage = cat["deductible_percentage"]
    else:
        # Code inconnu ou vide : graceful — libellé legacy, aucun code fiscal figé.
        label = expense_data.get("category", "")
        t2125_line = ""
        t2125_label_fr = ""
        gifi_code = ""
        gifi_label_en = ""
        percentage = 100
    deductible = round(amount_cad * percentage / 100, 2)
    snapshot = {
        "category": label,
        "category_code": code,
        "category_custom_label": custom_label if code == "other" else "",
        "category_t2125_line": t2125_line,
        "category_t2125_label_fr": t2125_label_fr,
        "category_gifi_code": gifi_code,
        "category_gifi_label_en": gifi_label_en,
        # LEGACY (rétrocompat rapport T2125 + export CSV existants) — aligné sur T2125.
        "category_arc_line": t2125_line,
        "deductible_percentage": percentage,
        "deductible_amount": deductible,
    }
    # Feature #14 — télécom à usage mixte : la portion affaires (réglages entreprise) est
    # le VRAI coût de la société ; le % effectif devient le % déductible et on fige la
    # portion personnelle (consommée par le P&L et l'écriture du grand livre).
    if code in TELECOM_CATEGORIES:
        pct = 100 if telecom_business_pct is None else max(0, min(100, int(round(float(telecom_business_pct)))))
        biz = round(amount_cad * pct / 100, 2)
        snapshot["business_use_pct"] = pct
        snapshot["deductible_percentage"] = pct
        snapshot["deductible_amount"] = biz
        snapshot["personal_use_amount_cad"] = round(amount_cad - biz, 2)
    return snapshot
```

- [ ] **Step 4: Vérifier les tests passent**

Run : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_tax_codes.py -q`
Expected : 5 PASSED.

- [ ] **Step 5: Vérifier T2125 report + P&L pas cassés**

Run : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/ -q -k "t2125 or pnl or expense or bank_expense" --ignore=backend/tests/test_bank_reconciliation_integration.py --ignore=backend/tests/test_csv_import.py`
Expected : tout PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/server.py backend/tests/test_expense_tax_codes.py
git commit -m "feat(F7.6-T2): snapshot fige t2125_line + gifi_code (arc_line legacy conservé)"
```

---

## Task 3 : GET /api/expense-categories retourne les nouveaux champs

**Files:**
- Modify: `backend/server.py` (endpoint `/api/expense-categories`)
- Test: `backend/tests/test_expense_tax_codes.py`

- [ ] **Step 1: Localiser l'endpoint**

Run : `cd backend && grep -n '/api/expense-categories' server.py`

Noter la ligne exacte du décorateur `@app.get("/api/expense-categories")`.

- [ ] **Step 2: Écrire le test qui échoue**

Append à `backend/tests/test_expense_tax_codes.py` :

```python
def test_categories_endpoint_returns_dual_codes(auth_headers):
    """GET /api/expense-categories retourne les 4 nouveaux champs par catégorie."""
    r = client.get("/api/expense-categories", headers=auth_headers)
    assert r.status_code == 200, r.text
    cats = r.json()
    assert isinstance(cats, list) and len(cats) >= 20
    by = {c["code"]: c for c in cats}
    subs = by["subscriptions"]
    assert subs["t2125_line"] == "8760"
    assert subs["t2125_label_fr"] == "Taxes d'affaires, droits d'adhésion et licences"
    assert subs["gifi_code"] == "8810"
    assert subs["gifi_label_en"] == "Office expenses"
    # Vérifier que arc_line n'est pas retourné (deprecated)
    assert "arc_line" not in subs, "arc_line ne doit plus être retourné par l'API"
```

- [ ] **Step 3: Vérifier le test échoue**

Run : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_tax_codes.py::test_categories_endpoint_returns_dual_codes -q`
Expected : FAILED sur `subs["t2125_line"]` (KeyError).

- [ ] **Step 4: Modifier l'endpoint**

Lire le code actuel de l'endpoint (repéré au Step 1) — il projette probablement `arc_line`. Remplacer la projection par les 4 nouveaux champs. Exemple attendu :

```python
@app.get("/api/expense-categories")
def get_expense_categories(current_user: CurrentUser = Depends(get_current_user)):
    return [
        {"code": c["code"], "label_fr": c["label_fr"], "label_en": c["label_en"],
         "t2125_line": c["t2125_line"], "t2125_label_fr": c["t2125_label_fr"],
         "gifi_code": c["gifi_code"], "gifi_label_en": c["gifi_label_en"],
         "deductible_percentage": c["deductible_percentage"], "group": c["group"]}
        for c in EXPENSE_CATEGORIES
    ]
```

Adapter à la signature exacte du décorateur/require_permission utilisée dans le fichier (utiliser exactement le même style que la fonction actuelle).

- [ ] **Step 5: Vérifier le test passe**

Run : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_tax_codes.py::test_categories_endpoint_returns_dual_codes -q`
Expected : PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/server.py backend/tests/test_expense_tax_codes.py
git commit -m "feat(F7.6-T3): GET /api/expense-categories retourne t2125_line + gifi_code"
```

---

## Task 4 : Migration idempotente `migrate_expense_tax_codes_v1`

**Files:**
- Modify: `backend/server.py` (nouvelle fonction + appel dans le handler startup L10673)
- Test: `backend/tests/test_expense_tax_codes.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Append à `backend/tests/test_expense_tax_codes.py` :

```python
def test_migration_backfills_dual_codes(auth_headers):
    """Une dépense legacy (uniquement category_arc_line + arc_line erroné) reçoit
    les 4 nouveaux champs + un category_arc_line corrigé après migration."""
    from backend.server import migrate_expense_tax_codes_v1
    # Créer une dépense legacy manuellement en DB (schéma pré-migration)
    org_id = _probe_org_id(auth_headers)
    if not org_id:
        pytest.skip("org_id indisponible")
    from backend import server
    legacy_id = "test_legacy_migr_" + os.urandom(4).hex()
    server.db.expenses.insert_one({
        "id": legacy_id, "organization_id": org_id, "user_id": "test",
        "amount": 100.0, "amount_cad": 100.0, "currency": "CAD",
        "category_code": "subscriptions", "category": "Abonnements et licences",
        "category_arc_line": "8740",  # ancien code erroné
        "deductible_percentage": 100, "deductible_amount": 100.0,
        "expense_date": "2099-01-15",
    })
    try:
        stats = migrate_expense_tax_codes_v1()
        assert stats["updated"] >= 1
        migrated = server.db.expenses.find_one({"id": legacy_id}, {"_id": 0})
        assert migrated["category_t2125_line"] == "8760"
        assert migrated["category_gifi_code"] == "8810"
        assert migrated["category_arc_line"] == "8760", "arc_line legacy corrigé"
        # 2e passage : rien à faire (idempotent)
        stats2 = migrate_expense_tax_codes_v1()
        matches = [d for d in stats2.get("touched_ids", []) if d == legacy_id]
        assert legacy_id not in matches, "migration doit être idempotente"
    finally:
        server.db.expenses.delete_one({"id": legacy_id})


def _probe_org_id(auth_headers):
    """Récupère l'org_id du user de test via une dépense sonde."""
    r = client.post("/api/expenses", headers=auth_headers, json={
        "amount": 1.00, "currency": "CAD", "category_code": "office_supplies",
        "description": "PROBE", "expense_date": "2099-01-01"})
    if r.status_code not in (200, 201):
        return None
    exp_id = r.json()["id"]
    from backend import server
    doc = server.db.expenses.find_one({"id": exp_id}, {"_id": 0})
    server.db.expenses.delete_one({"id": exp_id})
    return doc.get("organization_id") if doc else None
```

- [ ] **Step 2: Vérifier les tests échouent**

Run : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_tax_codes.py::test_migration_backfills_dual_codes -q`
Expected : FAILED avec `ImportError: cannot import name 'migrate_expense_tax_codes_v1'`.

- [ ] **Step 3: Ajouter la fonction de migration**

Repérer une bonne place — juste après `_build_expense_category_snapshot` (fin de la fonction, avant `# ─── Sales tax report helpers ───` L410). Insérer :

```python
def migrate_expense_tax_codes_v1():
    """Migration idempotente (feature #7.6) — ré-annote les dépenses historiques :
    - Ajoute category_t2125_line + category_t2125_label_fr + category_gifi_code +
      category_gifi_label_en (nouveau schéma).
    - Corrige category_arc_line si erroné (bank 8620→8710, subs 8740→8760,
      subcontracts 9367→9060, advertising 8520→8521).

    Idempotente : ne cible QUE les dépenses dont category_gifi_code est absent (null,
    missing ou vide). Au 2e passage, la clause est fausse -> no-op. Montants et
    déductibilité inchangés (on ne recalcule PAS deductible_amount pour éviter tout
    effet de bord sur les livres — la migration précédente F7.5 traite l'aplatissement
    et le % télécom).

    Retourne {updated: int, touched_ids: list[str]}.
    """
    updated = 0
    touched = []
    q = {
        "category_code": {"$exists": True, "$ne": ""},
        "$or": [
            {"category_gifi_code": {"$exists": False}},
            {"category_gifi_code": None},
            {"category_gifi_code": ""},
        ],
    }
    for exp in db.expenses.find(q, {"_id": 0, "id": 1, "category_code": 1}):
        code = (exp.get("category_code") or "").strip()
        cat = _find_category(code)
        if code == "other":
            t2125_line = cat["t2125_line"] if cat else "9270"
            t2125_label_fr = cat["t2125_label_fr"] if cat else "Autres dépenses"
            gifi_code = cat["gifi_code"] if cat else "9270"
            gifi_label_en = cat["gifi_label_en"] if cat else "Other expenses"
        elif cat:
            t2125_line = cat["t2125_line"]
            t2125_label_fr = cat["t2125_label_fr"]
            gifi_code = cat["gifi_code"]
            gifi_label_en = cat["gifi_label_en"]
        else:
            # Code inconnu : on marque le gifi_code vide MAIS pas None, sinon la
            # requête idempotente re-sélectionnerait cette dépense au prochain run.
            t2125_line = t2125_label_fr = gifi_code = gifi_label_en = ""
        result = db.expenses.update_one(
            {"id": exp["id"]},
            {"$set": {
                "category_t2125_line": t2125_line,
                "category_t2125_label_fr": t2125_label_fr,
                "category_gifi_code": gifi_code or "_",  # jamais "" ni None -> idempotence
                "category_gifi_label_en": gifi_label_en,
                "category_arc_line": t2125_line,  # aligné sur T2125 (corrige les erreurs historiques)
            }})
        if result.modified_count:
            updated += 1
            touched.append(exp["id"])
    return {"updated": updated, "touched_ids": touched}
```

Note : `gifi_code or "_"` évite que le prochain run resélectionne la dépense au code inconnu. Le "_" est un sentinel purement technique (pas un code fiscal valide).

- [ ] **Step 4: Enregistrer l'appel au startup**

Ouvrir le handler `@app.on_event("startup")` (L10673). Ajouter à la fin des migrations existantes :

```python
    # Feature #7.6 — ré-annote les dépenses avec t2125_line + gifi_code, corrige arc_line.
    try:
        migrate_expense_tax_codes_v1()
    except Exception:
        pass
```

Pattern conforme aux autres migrations du fichier (silencieux, ne bloque pas le boot).

- [ ] **Step 5: Vérifier les tests passent**

Run : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_tax_codes.py -q`
Expected : tout PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/server.py backend/tests/test_expense_tax_codes.py
git commit -m "feat(F7.6-T4): migration idempotente migrate_expense_tax_codes_v1"
```

---

## Task 5 : Helper `_gifi_group_by_code` + fonction `_flatten_pnl_expenses` réutilisable

**Files:**
- Modify: `backend/server.py:7103-7150` (renommer `_t2125_flatten_pnl_expenses` en `_flatten_pnl_expenses`, ajouter `_gifi_group_by_code`)
- Test: `backend/tests/test_expense_tax_codes.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Append à `backend/tests/test_expense_tax_codes.py` :

```python
def test_gifi_group_by_code_aggregates_correctly():
    """_gifi_group_by_code agrège les dépenses par category_gifi_code + attache le label."""
    from backend.server import _gifi_group_by_code
    flat = {
        "meals_entertainment": {"gross": 200.0, "deductible": 100.0,
                                 "t2125_line": "8523", "gifi_code": "8523"},
        "rent": {"gross": 1000.0, "deductible": 1000.0,
                 "t2125_line": "8910", "gifi_code": "8910"},
        "subscriptions": {"gross": 50.0, "deductible": 50.0,
                          "t2125_line": "8760", "gifi_code": "8810"},
    }
    grouped = _gifi_group_by_code(flat)
    by_code = {g["code"]: g for g in grouped}
    assert by_code["8523"]["amount"] == 100.0  # déductible
    assert by_code["8523"]["label"] == "Meals and entertainment"
    assert by_code["8910"]["amount"] == 1000.0
    # subscriptions → 8810 GIFI (pas 8760 T2125)
    assert by_code["8810"]["amount"] == 50.0
    assert by_code["8810"]["label"] == "Office expenses"


def test_flatten_reads_both_codes():
    """_flatten_pnl_expenses attache t2125_line ET gifi_code sur chaque catégorie."""
    from backend.server import _flatten_pnl_expenses
    groups = [{
        "expenses": [
            {"category_code": "subscriptions", "gross": 50.0, "deductible": 50.0},
        ],
    }]
    flat = _flatten_pnl_expenses(groups)
    assert "subscriptions" in flat
    assert flat["subscriptions"]["t2125_line"] == "8760"
    assert flat["subscriptions"]["gifi_code"] == "8810"
```

- [ ] **Step 2: Vérifier les tests échouent**

Run : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_tax_codes.py::test_gifi_group_by_code_aggregates_correctly backend/tests/test_expense_tax_codes.py::test_flatten_reads_both_codes -q`
Expected : FAILED (`ImportError: _gifi_group_by_code`).

- [ ] **Step 3: Lire la fonction `_t2125_flatten_pnl_expenses` actuelle**

Ouvrir `backend/server.py:7103-7140` pour voir la logique existante.

- [ ] **Step 4: Ajouter les helpers**

Juste après `_t2125_group_by_arc_line` (qu'on garde tel quel — rétrocompat T2125) ajouter :

```python
def _flatten_pnl_expenses(expense_groups):
    """Convertit expense_groups (de _aggregate_pnl) en dict plat par category_code,
    en attachant les DEUX codes fiscaux (t2125_line + gifi_code) via lookup catalogue.

    Feature #7.6 : successeur agnostique de `_t2125_flatten_pnl_expenses`. Le rapport
    T2125 continue d'utiliser `_t2125_flatten_pnl_expenses` (rétrocompat) ; le nouveau
    rapport GIFI utilise ce helper puis `_gifi_group_by_code`.

    Retourne : {code: {gross, deductible, t2125_line, gifi_code}}.
    """
    flat = {}
    for group in (expense_groups or []):
        for exp in (group.get("expenses") or []):
            code = (exp.get("category_code") or "").strip() or "other"
            cat = _find_category(code)
            t2125_line = cat["t2125_line"] if cat else "9270"
            gifi_code = cat["gifi_code"] if cat else "9270"
            if code not in flat:
                flat[code] = {"gross": 0.0, "deductible": 0.0,
                              "t2125_line": t2125_line, "gifi_code": gifi_code}
            flat[code]["gross"] += float(exp.get("gross", 0) or 0)
            flat[code]["deductible"] += float(exp.get("deductible", 0) or 0)
    for code in flat:
        flat[code]["gross"] = round(flat[code]["gross"], 2)
        flat[code]["deductible"] = round(flat[code]["deductible"], 2)
    return flat


def _gifi_group_by_code(flat_expenses, exclude_codes=None):
    """Agrège les catégories par code GIFI (rapport Sommaire GIFI, feature #7.6).

    Miroir de `_t2125_group_by_arc_line`. Retourne une liste triée par code :
        [{"code": "8523", "label": "Meals and entertainment", "amount": 100.0}, ...]
    Le montant est le DÉDUCTIBLE (comme le rapport T2125). exclude_codes permet
    de retirer certains category_code (ex. home_office ajusté séparément).
    """
    exclude = set(exclude_codes or [])
    by_code = {}
    labels = {}
    for code, data in flat_expenses.items():
        if code in exclude:
            continue
        gifi = data.get("gifi_code") or "9270"
        by_code[gifi] = by_code.get(gifi, 0.0) + float(data.get("deductible", 0) or 0)
        # Label = gifi_label_en de la catégorie (source unique)
        cat = _find_category(code)
        if cat and gifi not in labels:
            labels[gifi] = cat["gifi_label_en"]
    return sorted([{"code": c, "label": labels.get(c, "Other expenses"),
                    "amount": round(a, 2)}
                   for c, a in by_code.items()],
                  key=lambda x: x["code"])
```

- [ ] **Step 5: Vérifier les tests passent**

Run : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_tax_codes.py -q`
Expected : tout PASSED.

- [ ] **Step 6: Vérifier T2125 pas cassé**

Run : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/ -q -k "t2125" --ignore=backend/tests/test_bank_reconciliation_integration.py --ignore=backend/tests/test_csv_import.py`
Expected : tout PASSED.

- [ ] **Step 7: Commit**

```bash
git add backend/server.py backend/tests/test_expense_tax_codes.py
git commit -m "feat(F7.6-T5): helpers _flatten_pnl_expenses + _gifi_group_by_code"
```

---

## Task 6 : Endpoint `GET /api/reports/gifi` (JSON)

**Files:**
- Modify: `backend/server.py` (nouvel endpoint après le T2125)
- Test: `backend/tests/test_expense_tax_codes.py`

- [ ] **Step 1: Écrire le test qui échoue**

Append à `backend/tests/test_expense_tax_codes.py` :

```python
def test_gifi_report_endpoint(auth_headers):
    """GET /api/reports/gifi?year=YYYY&basis=cash retourne l'agrégation par gifi_code."""
    # Créer deux dépenses dans deux catégories distinctes
    e1 = client.post("/api/expenses", headers=auth_headers, json={
        "amount": 100.0, "currency": "CAD", "category_code": "meals_entertainment",
        "description": "Diner client", "expense_date": "2099-04-10"}).json()["id"]
    e2 = client.post("/api/expenses", headers=auth_headers, json={
        "amount": 500.0, "currency": "CAD", "category_code": "rent",
        "description": "Loyer avril", "expense_date": "2099-04-01"}).json()["id"]
    try:
        r = client.get("/api/reports/gifi?year=2099&basis=cash", headers=auth_headers)
        assert r.status_code == 200, r.text
        report = r.json()
        assert "lines" in report and "total" in report
        by = {ln["code"]: ln for ln in report["lines"]}
        assert "8523" in by  # meals GIFI
        assert "8910" in by  # rent GIFI
        # Meals 50% déductible → 50.0
        assert by["8523"]["amount"] == 50.0
        assert by["8523"]["label"] == "Meals and entertainment"
        assert by["8910"]["amount"] == 500.0
    finally:
        from backend import server
        for eid in (e1, e2):
            server.db.expenses.delete_one({"id": eid})
```

- [ ] **Step 2: Vérifier le test échoue**

Run : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_tax_codes.py::test_gifi_report_endpoint -q`
Expected : FAILED (404 Not Found).

- [ ] **Step 3: Lire `_build_t2125_report` pour connaître la signature exacte**

Run : `sed -n '7190,7240p' backend/server.py` — voir les args (`scope`, `year`, `basis`) et le format de retour.

- [ ] **Step 4: Ajouter `_build_gifi_report` + endpoint**

Ajouter juste après `_build_t2125_report` (avant les endpoints) :

```python
def _build_gifi_report(scope, year, basis):
    """Rapport Sommaire GIFI (feature #7.6) — miroir simplifié de T2125.

    Agrège les dépenses de l'année via _aggregate_pnl (même base que P&L / T2125)
    puis groupe par code GIFI. Pas d'ajustement home/vehicle (une société traite ces
    postes différemment — hors périmètre v1).
    """
    from datetime import date
    start = date(year, 1, 1).isoformat()
    end = date(year, 12, 31).isoformat()
    pnl = _aggregate_pnl(scope, start, end, basis=basis, compare=False)
    flat = _flatten_pnl_expenses(pnl.get("expense_groups", []))
    lines = _gifi_group_by_code(flat)
    total = round(sum(ln["amount"] for ln in lines), 2)
    return {"year": year, "basis": basis, "lines": lines, "total": total}


@app.get("/api/reports/gifi")
def get_gifi_report(year: int, basis: str = "cash",
                    current_user: CurrentUser = Depends(require_permission("reports:read"))):
    scope = _org_scope(current_user)
    if basis not in ("cash", "accrual"):
        raise HTTPException(422, "basis must be cash or accrual")
    return _build_gifi_report(scope, year, basis)
```

Note : `require_permission("reports:read")` doit correspondre au pattern utilisé par l'endpoint T2125. Vérifier ligne 10485.

- [ ] **Step 5: Vérifier le test passe**

Run : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_tax_codes.py::test_gifi_report_endpoint -q`
Expected : PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/server.py backend/tests/test_expense_tax_codes.py
git commit -m "feat(F7.6-T6): GET /api/reports/gifi (JSON) — sommaire par code GIFI"
```

---

## Task 7 : Endpoint `GET /api/reports/gifi/csv`

**Files:**
- Modify: `backend/server.py` (nouvel endpoint CSV après le JSON)
- Test: `backend/tests/test_expense_tax_codes.py`

- [ ] **Step 1: Écrire le test qui échoue**

Append :

```python
def test_gifi_report_csv(auth_headers):
    e = client.post("/api/expenses", headers=auth_headers, json={
        "amount": 100.0, "currency": "CAD", "category_code": "advertising",
        "description": "Facebook ads", "expense_date": "2099-05-01"}).json()["id"]
    try:
        r = client.get("/api/reports/gifi/csv?year=2099&basis=cash", headers=auth_headers)
        assert r.status_code == 200
        body = r.text
        assert "Code GIFI" in body or "GIFI" in body
        assert "8520" in body  # advertising GIFI
        assert "Advertising and promotion" in body
        assert "100" in body
    finally:
        from backend import server
        server.db.expenses.delete_one({"id": e})
```

- [ ] **Step 2: Vérifier le test échoue**

Run : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_tax_codes.py::test_gifi_report_csv -q`
Expected : FAILED (404).

- [ ] **Step 3: Ajouter l'endpoint CSV**

Juste après `GET /api/reports/gifi` (JSON) :

```python
@app.get("/api/reports/gifi/csv")
def get_gifi_report_csv(year: int, basis: str = "cash",
                        current_user: CurrentUser = Depends(require_permission("reports:read"))):
    import csv
    import io
    scope = _org_scope(current_user)
    if basis not in ("cash", "accrual"):
        raise HTTPException(422, "basis must be cash or accrual")
    report = _build_gifi_report(scope, year, basis)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Code GIFI", "Libellé (EN)", "Montant CAD"])
    for ln in report["lines"]:
        w.writerow([ln["code"], ln["label"], f"{ln['amount']:.2f}"])
    w.writerow(["", "Total", f"{report['total']:.2f}"])
    return Response(content=buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="gifi-{year}.csv"'})
```

- [ ] **Step 4: Vérifier le test passe**

Run : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_tax_codes.py::test_gifi_report_csv -q`
Expected : PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/server.py backend/tests/test_expense_tax_codes.py
git commit -m "feat(F7.6-T7): GET /api/reports/gifi/csv — export CSV"
```

---

## Task 8 : Endpoint `GET /api/reports/gifi/pdf` (réutilise le rendu T2125)

**Files:**
- Modify: `backend/server.py` (nouvel endpoint + micro-refactor du render PDF)
- Test: `backend/tests/test_expense_tax_codes.py`

- [ ] **Step 1: Écrire le test qui échoue**

Append :

```python
def test_gifi_report_pdf(auth_headers):
    e = client.post("/api/expenses", headers=auth_headers, json={
        "amount": 200.0, "currency": "CAD", "category_code": "professional_fees",
        "description": "Comptable", "expense_date": "2099-06-01"}).json()["id"]
    try:
        r = client.get("/api/reports/gifi/pdf?year=2099&basis=cash", headers=auth_headers)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content[:4] == b"%PDF", "doit être un PDF valide"
        assert len(r.content) > 500  # taille raisonnable pour un PDF avec au moins une ligne
    finally:
        from backend import server
        server.db.expenses.delete_one({"id": e})
```

- [ ] **Step 2: Vérifier le test échoue**

Run : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_tax_codes.py::test_gifi_report_pdf -q`
Expected : FAILED (404).

- [ ] **Step 3: Lire `_render_t2125_pdf` (L10562) pour connaître sa structure**

Run : `sed -n '10562,10620p' backend/server.py`

- [ ] **Step 4: Ajouter un helper de rendu générique + endpoint**

Ne pas modifier `_render_t2125_pdf` (T2125 a des sections spécifiques home/vehicle qu'on ne veut pas dans GIFI v1). Ajouter à côté :

```python
def _render_gifi_pdf(report):
    """Rendu PDF minimaliste du sommaire GIFI (feature #7.6). Structure : titre,
    période, tableau code/label/montant, total. ReportLab, format A4."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    import io as _io
    buf = _io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=40, bottomMargin=40,
                            leftMargin=40, rightMargin=40)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"Sommaire GIFI — {report['year']}", styles["Title"]),
        Paragraph(f"Base : {report['basis']}", styles["Normal"]),
        Spacer(1, 12),
    ]
    data = [["Code GIFI", "Libellé", "Montant CAD"]]
    for ln in report["lines"]:
        data.append([ln["code"], ln["label"], f"{ln['amount']:,.2f} $"])
    data.append(["", "Total", f"{report['total']:,.2f} $"])
    tbl = Table(data, colWidths=[80, 320, 100])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#00A08C")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(tbl)
    doc.build(story)
    return buf.getvalue()


@app.get("/api/reports/gifi/pdf")
def get_gifi_report_pdf(year: int, basis: str = "cash",
                        current_user: CurrentUser = Depends(require_permission("reports:read"))):
    scope = _org_scope(current_user)
    if basis not in ("cash", "accrual"):
        raise HTTPException(422, "basis must be cash or accrual")
    report = _build_gifi_report(scope, year, basis)
    pdf_bytes = _render_gifi_pdf(report)
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="gifi-{year}.pdf"'})
```

- [ ] **Step 5: Vérifier le test passe**

Run : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/test_expense_tax_codes.py::test_gifi_report_pdf -q`
Expected : PASSED.

- [ ] **Step 6: Suite bancaire complète pour non-régression**

Run : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/ -q -k "expense or bank or t2125 or gifi or pnl" --ignore=backend/tests/test_bank_reconciliation_integration.py --ignore=backend/tests/test_csv_import.py`
Expected : tout PASSED (aucune régression).

- [ ] **Step 7: Commit**

```bash
git add backend/server.py backend/tests/test_expense_tax_codes.py
git commit -m "feat(F7.6-T8): GET /api/reports/gifi/pdf — export PDF"
```

---

## Task 9 : Frontend — picker enrichi selon `entity_type`

**Files:**
- Modify: `frontend/src/pages/ExpensesPage.js` (picker de catégorie)
- Modify: `frontend/src/components/BankCreateExpenseModal.js` (idem)

- [ ] **Step 1: Identifier le picker actuel**

Run : `cd frontend/src && grep -n "expense-categories\|category_code\|arc_line" pages/ExpensesPage.js components/BankCreateExpenseModal.js | head -20`

Repérer où le `<select>`/`<option>` de catégorie est rendu et où `entity_type` est déjà lu (probablement fetch de `/api/settings/company`).

- [ ] **Step 2: Modifier `ExpensesPage.js`**

Ouvrir `frontend/src/pages/ExpensesPage.js`. Identifier :
1. Le fetch de `/api/expense-categories` (probablement dans un `useEffect`).
2. Le state qui garde `entity_type` (probablement chargé depuis `/api/settings/company`, ou à ajouter).

Ajouter (près du haut du composant si absent) :

```jsx
const [entityType, setEntityType] = useState('sole_proprietor');

useEffect(() => {
  axios.get(`${BACKEND_URL}/api/settings/company`)
    .then(r => setEntityType(r.data?.entity_type || 'sole_proprietor'))
    .catch(() => {});
}, []);
```

Puis, dans la boucle qui rend les `<option>` de catégorie, remplacer le libellé simple par une version enrichie :

```jsx
{categories.map(c => {
  const code = entityType === 'corporation' ? c.gifi_code : c.t2125_line;
  const codeLabel = entityType === 'corporation' ? `GIFI ${code}` : `T2125 ligne ${code}`;
  return (
    <option key={c.code} value={c.code}>
      {c.label_fr}{code ? ` — ${codeLabel}` : ''}
    </option>
  );
})}
```

- [ ] **Step 3: Reproduire dans `BankCreateExpenseModal.js`**

Même pattern — récupérer `entityType`, enrichir le libellé des `<option>`. Pattern identique à Step 2.

- [ ] **Step 4: Vérifier le build CI passe**

Run (depuis `frontend/`) : `CI=true GENERATE_SOURCEMAP=false npx --no-install react-scripts build 2>&1 | grep -E "Compiled|Failed|Line " | head -5`
Expected : `Compiled successfully.`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ExpensesPage.js frontend/src/components/BankCreateExpenseModal.js
git commit -m "feat(F7.6-T9): picker de catégorie affiche T2125/GIFI selon entity_type"
```

---

## Task 10 : Frontend — composant `GifiReportSection` + onglet conditionnel

**Files:**
- Create: `frontend/src/components/GifiReportSection.js`
- Modify: `frontend/src/pages/ReportsPage.js` (ajouter l'onglet)

- [ ] **Step 1: Lire `T2125ReportSection.js` comme modèle**

Run : `cd frontend/src/components && wc -l T2125ReportSection.js && head -50 T2125ReportSection.js`

Comprendre le pattern (state `year`/`basis`, fetch JSON, boutons CSV/PDF, tableau).

- [ ] **Step 2: Créer `GifiReportSection.js` (miroir simplifié)**

Créer `frontend/src/components/GifiReportSection.js` :

```jsx
import React, { useState, useEffect } from "react";
import axios from "axios";
import { BACKEND_URL } from "../config";

export default function GifiReportSection() {
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState(currentYear);
  const [basis, setBasis] = useState("cash");
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setLoading(true); setErr(null);
    axios.get(`${BACKEND_URL}/api/reports/gifi?year=${year}&basis=${basis}`)
      .then(r => setReport(r.data))
      .catch(e => setErr(e.response?.data?.detail || "Erreur"))
      .finally(() => setLoading(false));
  }, [year, basis]);

  const download = (fmt) => {
    window.open(`${BACKEND_URL}/api/reports/gifi/${fmt}?year=${year}&basis=${basis}`);
  };

  return (
    <div style={{ padding: 16 }}>
      <h3 style={{ margin: "0 0 12px" }}>Sommaire GIFI</h3>
      <p style={{ color: "#6b7280", fontSize: 13, marginTop: 0 }}>
        Sommaire des dépenses par code GIFI (Index général des renseignements financiers,
        RC4088) — utilisé pour la déclaration T2 (fédéral) et CO-17 (Québec) d'une
        société par actions.
      </p>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
        <label>Année <input type="number" value={year} min="2000" max="2100"
                              onChange={(e) => setYear(parseInt(e.target.value || currentYear, 10))}
                              style={{ padding: 4, width: 80, border: "1px solid #d1d5db", borderRadius: 4 }} />
        </label>
        <label>Base
          <select value={basis} onChange={(e) => setBasis(e.target.value)}
                  style={{ padding: 4, marginLeft: 4, border: "1px solid #d1d5db", borderRadius: 4 }}>
            <option value="cash">Encaissements/décaissements</option>
            <option value="accrual">Comptabilité d'exercice</option>
          </select>
        </label>
        <button onClick={() => download("csv")} disabled={loading || !report}
                style={btn}>Exporter CSV</button>
        <button onClick={() => download("pdf")} disabled={loading || !report}
                style={btn}>Exporter PDF</button>
      </div>
      {loading && <p>Chargement…</p>}
      {err && <p style={{ color: "#dc2626" }}>{err}</p>}
      {report && (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ background: "#f8fafb", textAlign: "left" }}>
              <th style={th}>Code GIFI</th>
              <th style={th}>Libellé</th>
              <th style={{ ...th, textAlign: "right" }}>Montant CAD</th>
            </tr>
          </thead>
          <tbody>
            {report.lines.map(ln => (
              <tr key={ln.code}>
                <td style={td}>{ln.code}</td>
                <td style={td}>{ln.label}</td>
                <td style={{ ...td, textAlign: "right" }}>{ln.amount.toFixed(2)} $</td>
              </tr>
            ))}
            <tr style={{ fontWeight: 600, background: "#f8fafb" }}>
              <td style={td}></td>
              <td style={td}>Total</td>
              <td style={{ ...td, textAlign: "right" }}>{report.total.toFixed(2)} $</td>
            </tr>
          </tbody>
        </table>
      )}
    </div>
  );
}

const btn = { background: "#00A08C", color: "#fff", border: "none",
              padding: "6px 12px", borderRadius: 6, cursor: "pointer", fontSize: 13 };
const th = { padding: 8, borderBottom: "1px solid #e5e7eb" };
const td = { padding: 8, borderBottom: "1px solid #f3f4f6" };
```

- [ ] **Step 3: Intégrer l'onglet dans `ReportsPage.js`**

Lire `ReportsPage.js` autour de la section T2125 (grep `T2125ReportSection`). Ajouter l'import et un onglet conditionnel :

```jsx
import GifiReportSection from "../components/GifiReportSection";
```

Puis, là où l'onglet T2125 est monté conditionnellement pour `sole_proprietor`, ajouter en parallèle l'onglet GIFI pour `corporation`. Exemple (adapter au switch/render actuel) :

```jsx
{entityType === 'sole_proprietor' && (
  <button onClick={() => setTab('t2125')} style={...}>T2125</button>
)}
{entityType === 'corporation' && (
  <button onClick={() => setTab('gifi')} style={...}>Sommaire GIFI</button>
)}
```

Et dans le corps :

```jsx
{tab === 't2125' && <T2125ReportSection ... />}
{tab === 'gifi' && <GifiReportSection />}
```

- [ ] **Step 4: Build CI**

Run (depuis `frontend/`) : `CI=true GENERATE_SOURCEMAP=false npx --no-install react-scripts build 2>&1 | grep -E "Compiled|Failed|Line " | head -5`
Expected : `Compiled successfully.`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/GifiReportSection.js frontend/src/pages/ReportsPage.js
git commit -m "feat(F7.6-T10): rapport Sommaire GIFI (onglet corporation)"
```

---

## Task 11 : E2E, changelog, push prod

**Files:**
- Modify: `CLAUDE.md` (entrée changelog)

- [ ] **Step 1: Suite backend complète + build frontend**

Run backend : `MONGO_URL=mongodb://localhost:27017 JWT_SECRET=test DB_NAME=facturepro .venv-test/bin/python -m pytest backend/tests/ -q --ignore=backend/tests/test_bank_reconciliation_integration.py --ignore=backend/tests/test_csv_import.py 2>&1 | tail -3`
Expected : tout PASSED.

Run frontend : `cd frontend && CI=true GENERATE_SOURCEMAP=false npx --no-install react-scripts build 2>&1 | grep -E "Compiled|Failed|Line " | head -5`
Expected : `Compiled successfully.`.

- [ ] **Step 2: Ajouter l'entrée changelog CLAUDE.md**

Ouvrir `CLAUDE.md`. Sous `## Features livrées`, insérer juste avant l'entrée « 2026-07-06 — Fix audit : dépenses créées depuis une transaction bancaire invisibles aux rapports (feature #7.5) » :

```markdown
- **2026-07-06 — Codes fiscaux adaptés au type d'entité (feature #7.6)**
  - **Problème** : les catégories de dépenses affichaient un unique code `arc_line` — soit erroné (bank 8620, subs 8740, subcontracts 9367 n'existent pas au T2125), soit inadapté au type d'entité. Une société par actions voyait le code T2125 (autonome) alors qu'elle déclare avec des codes **GIFI** (T2 fédéral + CO-17 Québec).
  - **Correctif** : chaque catégorie porte désormais DEUX codes fiscaux — `t2125_line` (autonome) + `gifi_code` (société). Le snapshot fige les deux ; le picker affiche celui du régime en cours (« T2125 ligne 8760 » ou « GIFI 8810 ») ; le rapport T2125 reste pour l'autonome, un nouveau **rapport « Sommaire GIFI »** apparaît pour la société.
  - **Corrections des codes historiques** : bank 8620 → T2125 8710 / GIFI 8715 ; subscriptions 8740 → T2125 8760 / GIFI 8810 ; subcontracts 9367 → T2125 9060 / GIFI 9110 ; advertising T2125=8521 ≠ GIFI=8520 ; télécom cell/internet raffiné en GIFI 9225/9152. Corrections verrouillées par 2 rondes de recherche adversariale multi-sources CRA (RC4088, T2 SCH125, canada.ca) — 15 claims confirmés 3/3.
  - **Migration** idempotente au startup (`migrate_expense_tax_codes_v1`) : ré-annote les dépenses historiques avec les deux codes + aligne `category_arc_line` sur le T2125 corrigé (P&L / T2125 automatiquement plus exacts). Aucun montant ni % déductible touché.
  - Tests : `test_expense_tax_codes.py` (constants, snapshot, endpoint, migration idempotente, rapport GIFI JSON/CSV/PDF).
```

- [ ] **Step 3: Commit CLAUDE.md**

```bash
git add CLAUDE.md
git commit -m "docs(F7.6-T11): changelog codes fiscaux entity-aware"
```

- [ ] **Step 4: Vérifier tout est propre**

Run : `git status --short && git log --oneline -12`
Expected : working tree clean, 11 commits F7.6 (T0 à T11) en tête.

- [ ] **Step 5: Demander confirmation utilisateur avant push**

Utiliser l'outil `AskUserQuestion` : « Je pousse la feature #7.6 (codes fiscaux entity-aware + migration DB) en prod ? »

Options :
- « Oui, pousse maintenant » → `git push origin main`
- « Non, je garde en local »

- [ ] **Step 6: Si approuvé — pousser**

Run : `git push origin main 2>&1 | tail -2`
Expected : `main -> main` reçu.

Rapporter à l'utilisateur : commits F7.6 poussés, Render déploie backend + migration idempotente au restart, Vercel déploie frontend, ~2 min. Bien vérifier que le rapport GIFI s'affiche et que le picker montre les bons codes selon le type d'entité de la société.
