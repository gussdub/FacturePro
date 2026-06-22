# Export T2125 fin d'année (feature #10) — Design

**Statut :** design approuvé 2026-06-17 (révisé après critique multi-angles : 12 blockers + 24 important findings intégrés)
**Auteur :** Claude (brainstorming session avec gussdub)

## 1. Objectif

Permettre à un utilisateur de FacturePro (entreprise individuelle canadienne, `entity_type = "sole_proprietor"`) d'exporter en fin d'année tous les chiffres dont il a besoin pour remplir sa déclaration **T2125 — État des résultats des activités d'une entreprise** auprès de l'ARC.

Cas d'usage : en mars/avril, l'utilisateur va dans Rapports → onglet « Déclaration T2125 » → sélectionne l'année → clique Générer → obtient un PDF récapitulatif (à donner à son comptable) et un CSV (à importer dans Excel ou copier-coller dans le formulaire ARC officiel).

## 2. Décisions de design (brainstorming — fixes)

| # | Question | Décision |
|---|----------|----------|
| 1 | Portée entity_type | **T2125 seulement** (sole_proprietor). Corporation → message informatif renvoyant au P&L. |
| 2 | Format de sortie | **PDF + CSV**. Pas de reproduction fidèle du formulaire ARC. |
| 3 | Base et période | **Année civile forcée**. Base **accrual ou cash au choix**. |
| 4 | Inclusions | Revenus + dépenses par ligne ARC + bureau à domicile + véhicule + encadré « à compléter ». |
| 5 | Capture bureau/véhicule | **2 champs globaux Settings** (`home_office_percentage`, `vehicle_business_percentage`). |
| 6 | Emplacement UI | **Nouvel onglet « Déclaration T2125 »** dans Rapports. |

## 3. Réalité du code existant — contraintes à respecter

**Avant tout : le spec d'origine assumait des structures qui ne correspondent pas au code réel. Voici la vérité du codebase :**

### 3.1 `EXPENSE_CATEGORIES` (feature #3, `server.py:142`)

17 catégories, chacune avec `arc_line` réellement attribué :

| code | arc_line | deductible_% |
|---|---|---|
| office_expenses | **8810** | 100 |
| office_supplies | **8811** | 100 |
| professional_fees | 8860 | 100 |
| bank_charges | **8620** | 100 |
| subscriptions | **8740** | 100 |
| advertising | 8520 | 100 |
| meals_entertainment | 8523 | **50** |
| rent | 8910 | 100 |
| utilities | **9220** | 100 |
| insurance | **8690** | 100 |
| repairs_maintenance | **8960** | 100 |
| travel | **9200** | 100 |
| **vehicle_expenses** | 9281 | 100 |
| delivery | **9275** | 100 |
| salaries | 9060 | 100 |
| subcontracts | **9367** | 100 |
| management_fees | **8871** | 100 |
| other | **""** (chaîne vide) | 100 |

**Implications critiques** :
- Pas de catégorie `internet_phone` — utilities et téléphone/internet sont tous regroupés sous `utilities` (9220).
- Un seul code véhicule : `vehicle_expenses` (PAS `vehicle_fuel` + `vehicle_maintenance`).
- `other` a `arc_line = ""` (chaîne vide), pas None. Le fallback doit utiliser `or "9270"`, pas `.get(..., "9270")`.

### 3.2 `_aggregate_pnl` (feature #5, `server.py:314`)

Signature : `_aggregate_pnl(user_id, start, end, basis)`. Retourne :

```python
{
  "revenue": float,
  "expense_groups": [           # LISTE de groupes, PAS un dict plat
    {
      "group": "office",
      "label": "Bureau et administration",
      "categories": [          # LISTE de catégories par groupe
        {"code", "label", "arc_line", "gross", "deductible"},
        ...
      ],
      "subtotal": {"gross", "deductible"},
    },
    ...
  ],
  "total_expenses": {"gross", "deductible"},
  "net_income": {"management", "taxable"},
  "invoice_count": int,
  "expense_count": int,
}
```

**Pas de clé `expenses_by_category`.** Toute la logique T2125 doit itérer `expense_groups[*].categories`.

**Base cash** : filtre `status == "paid"` sur `issue_date`. **Approximation** : une facture émise en décembre et payée en janvier compte dans l'année d'émission. Documenté en §8 Limites.

### 3.3 `_compute_taxes_paid` (feature #4, `server.py:228`)

Signature réelle : `_compute_taxes_paid(amount_gross, province) -> dict`. C'est un **helper pur de calcul** (pas une requête DB). On NE peut PAS l'appeler avec `(user_id, start, end)`. Pour le T2125, on a besoin d'un agrégateur DB séparé.

## 4. Architecture & nouveaux helpers

### 4.1 Nouveaux champs Settings

Ajout sur `company_settings` :

```python
"home_office_percentage": float       # 0.0 à 100.0, défaut 0
"vehicle_business_percentage": float  # 0.0 à 100.0, défaut 0
```

**Validation backend dans `PUT /api/settings/company`** :
```python
import math  # à ajouter en haut si pas déjà
for field in ("home_office_percentage", "vehicle_business_percentage"):
    if field in settings_data:
        try:
            v = float(settings_data[field])
        except (ValueError, TypeError):
            raise HTTPException(422, f"{field} doit être un nombre")
        if not math.isfinite(v):  # bloque NaN, inf, -inf
            raise HTTPException(422, f"{field} doit être un nombre fini")
        if not (0 <= v <= 100):
            raise HTTPException(422, f"{field} doit être entre 0 et 100")
        settings_data[field] = v
```

### 4.2 Nouveaux helpers backend (tous dans `server.py`)

#### `_t2125_flatten_pnl_expenses(expense_groups)` — flatten

```python
def _t2125_flatten_pnl_expenses(expense_groups: list) -> dict:
    """Convertit la liste expense_groups de _aggregate_pnl en dict plat
    {code: {gross, deductible, arc_line}}."""
    flat = {}
    for group in expense_groups or []:
        for cat in group.get("categories", []):
            flat[cat["code"]] = {
                "gross": float(cat.get("gross", 0) or 0),
                "deductible": float(cat.get("deductible", 0) or 0),
                "arc_line": cat.get("arc_line") or "9270",
            }
    return flat
```

#### `_t2125_group_by_arc_line(flat_expenses, exclude_codes=None)` — agrégation par ligne T2125

```python
def _t2125_group_by_arc_line(flat_expenses: dict, exclude_codes: set = None) -> list:
    """Regroupe les catégories partageant la même ligne T2125.
    Ignore les codes dans exclude_codes (utilisé pour le mode exclusif home_office)."""
    exclude_codes = exclude_codes or set()
    by_line = {}
    for code, data in flat_expenses.items():
        if code in exclude_codes:
            continue
        arc_line = data.get("arc_line") or "9270"
        entry = by_line.setdefault(arc_line, {
            "arc_line": arc_line,
            "label": T2125_LINE_LABELS.get(arc_line, "Autres dépenses"),
            "gross": 0.0,
            "deductible": 0.0,
            "categories": [],
        })
        entry["gross"] += data["gross"]
        entry["deductible"] += data["deductible"]
        entry["categories"].append(code)
    out = []
    for arc_line in sorted(by_line.keys()):
        entry = by_line[arc_line]
        entry["gross"] = round(entry["gross"], 2)
        entry["deductible"] = round(entry["deductible"], 2)
        if arc_line == "8523":
            entry["note"] = "50 % déductible"
        out.append(entry)
    return out
```

#### `_t2125_compute_home_office_adjustment(flat_expenses, home_pct)`

**Mode EXCLUSIF** : si `home_pct > 0`, les catégories `rent`, `utilities`, `insurance` sont **retirées de leur ligne ARC** et **remplacées** par une ligne 9945 unique avec `(somme gross) × home_pct / 100`.

```python
HOME_OFFICE_CATEGORIES = {"rent", "utilities", "insurance"}


def _t2125_compute_home_office_adjustment(flat_expenses: dict, home_pct: float) -> dict | None:
    """Calcule l'ajustement bureau à domicile (mode exclusif).
    Retourne le dict ajustement ou None si home_pct = 0."""
    if home_pct <= 0:
        return None
    original_total = sum(
        float(flat_expenses.get(cat, {}).get("gross", 0) or 0)
        for cat in HOME_OFFICE_CATEGORIES
    )
    return {
        "percentage": home_pct,
        "applies_to": sorted(HOME_OFFICE_CATEGORIES),
        "original_total": round(original_total, 2),
        "deductible_amount": round(original_total * home_pct / 100.0, 2),
        "saved_to_arc_line": "9945",
        "label": "Frais d'utilisation de la résidence aux fins de l'entreprise",
    }
```

Note : si `home_pct > 0` mais aucune dépense dans les 3 catégories → `original_total = 0`, deductible_amount = 0. L'ajustement est quand même retourné (pour transparence dans le rapport), juste à 0.

#### `_t2125_compute_vehicle_adjustment(flat_expenses, vehicle_pct)`

Idem mais pour `vehicle_expenses` seulement (le seul code véhicule existant).

```python
VEHICLE_CATEGORIES = {"vehicle_expenses"}


def _t2125_compute_vehicle_adjustment(flat_expenses: dict, vehicle_pct: float) -> dict | None:
    if vehicle_pct <= 0:
        return None
    original_total = sum(
        float(flat_expenses.get(cat, {}).get("gross", 0) or 0)
        for cat in VEHICLE_CATEGORIES
    )
    return {
        "percentage": vehicle_pct,
        "applies_to": sorted(VEHICLE_CATEGORIES),
        "original_total": round(original_total, 2),
        "deductible_amount": round(original_total * vehicle_pct / 100.0, 2),
        "saved_to_arc_line": "9281",
        "label": "Frais relatifs aux véhicules à moteur",
    }
```

#### `_build_t2125_report` — orchestrateur

```python
T2125_VALID_BASES = {"accrual", "cash"}
T2125_MIN_YEAR = 2020


def _build_t2125_report(user_id: str, year: int, basis: str) -> dict:
    """Construit le rapport T2125 pour une année et base données.
    Implémentation mode EXCLUSIF : si home_office_percentage > 0, les catégories
    rent/utilities/insurance sont retirées de leurs lignes ARC et regroupées
    sur la ligne 9945 avec le pourcentage appliqué (logique T2125 correcte)."""
    # Validations
    # +1 pour absorber la dérive timezone (Quebec local Dec 31 = UTC Jan 1)
    upper_year = datetime.now(timezone.utc).year + 1
    if not (T2125_MIN_YEAR <= year <= upper_year):
        raise HTTPException(422, f"Année hors plage admissible ({T2125_MIN_YEAR}–{upper_year})")
    if basis not in T2125_VALID_BASES:
        raise HTTPException(422, "basis must be 'accrual' or 'cash'")

    settings = db.company_settings.find_one({"user_id": user_id}, {"_id": 0})
    if not settings:
        raise HTTPException(422, "Complète tes informations dans Réglages avant de générer ton T2125")
    if settings.get("entity_type", "sole_proprietor") != "sole_proprietor":
        raise HTTPException(422, "T2125 export only available for sole proprietors")

    period = {"start": f"{year}-01-01", "end": f"{year}-12-31"}

    # 1. Aggregate via _aggregate_pnl (feature #5)
    pnl = _aggregate_pnl(user_id, period["start"], period["end"], basis=basis)

    # 2. Flatten expense_groups → {code: {gross, deductible, arc_line}}
    flat_expenses = _t2125_flatten_pnl_expenses(pnl.get("expense_groups", []))

    # 3. Lire les % depuis Settings
    home_pct = float(settings.get("home_office_percentage", 0) or 0)
    vehicle_pct = float(settings.get("vehicle_business_percentage", 0) or 0)

    # 4. Calculer les ajustements + déterminer les exclusions
    home_adj = _t2125_compute_home_office_adjustment(flat_expenses, home_pct)
    vehicle_adj = _t2125_compute_vehicle_adjustment(flat_expenses, vehicle_pct)

    excluded = set()
    if home_adj is not None:
        excluded.update(HOME_OFFICE_CATEGORIES)
    if vehicle_adj is not None:
        excluded.update(VEHICLE_CATEGORIES)

    # 5. Grouper par ligne ARC en excluant les catégories déplacées
    grouped = _t2125_group_by_arc_line(flat_expenses, exclude_codes=excluded)

    # 6. Ajouter les lignes d'ajustement (9945, 9281) comme entrées séparées dans grouped
    if home_adj is not None:
        grouped.append({
            "arc_line": "9945",
            "label": home_adj["label"],
            "gross": home_adj["original_total"],
            "deductible": home_adj["deductible_amount"],
            "categories": list(HOME_OFFICE_CATEGORIES),
            "note": f"{home_pct:g} % de l'utilisation totale",
        })
    if vehicle_adj is not None:
        grouped.append({
            "arc_line": "9281",
            "label": vehicle_adj["label"],
            "gross": vehicle_adj["original_total"],
            "deductible": vehicle_adj["deductible_amount"],
            "categories": list(VEHICLE_CATEGORIES),
            "note": f"{vehicle_pct:g} % d'utilisation commerciale",
        })

    # Re-trier par arc_line après ajout des ajustements
    grouped.sort(key=lambda x: x["arc_line"])

    # 7. Total déductible — SOMME SIMPLE des lignes (mode exclusif évite double-count)
    total_deductible = round(sum(line["deductible"] for line in grouped), 2)
    net_income = round(pnl["revenue"] - total_deductible, 2)

    adjustments = {}
    if home_adj is not None:
        adjustments["home_office"] = home_adj
    if vehicle_adj is not None:
        adjustments["vehicle"] = vehicle_adj

    return {
        "year": year,
        "basis": basis,
        "period": period,
        "entity_type": "sole_proprietor",
        "province": settings.get("province", "QC"),
        "company_name": settings.get("company_name", ""),
        "bn_number": settings.get("bn_number", ""),
        "gross_income": round(pnl["revenue"], 2),
        "income_line": "8000",
        "expenses_by_arc_line": grouped,
        "total_expenses_deductible": total_deductible,
        "business_use_adjustments": adjustments,
        "net_income": net_income,
        "net_income_line": "9369",
        "is_partial_year": year >= datetime.now(timezone.utc).year,
    }
```

**`is_partial_year`** : true si l'année demandée est >= année courante UTC → le rapport peut couvrir une période incomplète. Frontend/PDF affiche un avertissement.

#### Drop YAGNI

Les éléments suivants ont été retirés vs proposition initiale (per critique multi-angles) :
- `manual_sections_to_complete` (liste statique) → remplacé par bloc de texte fixe dans le PDF.
- `double_counting_warning` (flag conditionnel) → non pertinent en mode EXCLUSIF (les catégories sont déplacées, plus de double-comptabilisation possible).
- `_compute_taxes_collected` + section audit TPS/TVQ → retiré (duplique le rapport TPS/TVQ feature #4). UI propose un lien « Pour la déclaration TPS/TVQ, consulte l'onglet TPS/TVQ. »
- `_t2125_arc_line_label` helper → inline dans `_t2125_group_by_arc_line`.
- Banner « ajustement non configuré » → retiré (faux positif pour les users sans bureau/véhicule).

### 4.3 Table de libellés T2125 (couverture complète)

```python
T2125_LINE_LABELS = {
    # Revenu
    "8000": "Recettes brutes",
    # Lignes ARC réellement utilisées par EXPENSE_CATEGORIES
    "8520": "Publicité et promotion",
    "8523": "Repas et représentation",
    "8620": "Frais bancaires",
    "8690": "Assurances",
    "8740": "Abonnements et licences",
    "8810": "Frais de bureau",
    "8811": "Fournitures de bureau",
    "8860": "Honoraires professionnels",
    "8871": "Frais de gestion",
    "8910": "Loyer",
    "8960": "Entretien et réparations",
    "9060": "Salaires et avantages",
    "9200": "Frais de déplacement",
    "9220": "Services publics",
    "9270": "Autres dépenses",
    "9275": "Livraison et fret",
    "9281": "Frais relatifs aux véhicules à moteur",
    "9367": "Sous-traitance",
    "9945": "Frais d'utilisation de la résidence aux fins de l'entreprise",
}

T2125_LABEL_TABLE_TAX_YEAR = 2024  # version de référence du formulaire ARC
```

**Test de couverture obligatoire** (§ 9.1) : vérifier que TOUT `arc_line` non-vide dans `EXPENSE_CATEGORIES` existe dans `T2125_LINE_LABELS`.

**Note sur les libellés** : on conserve les libellés simples FR. Quelques arc_lines (8620, 8740, 8811, 8960, 9220) sont des codes GIFI plutôt que des lignes officielles du T2125 — le comptable saura les ré-affecter aux bonnes lignes T2125 quand il transcrit. C'est documenté en §8.

## 5. API REST

### 5.1 Endpoints (3)

Tous sous `/api/reports/t2125`, auth requise via `Depends(get_current_user_with_access)`.

```
GET /api/reports/t2125?year=YYYY&basis=accrual|cash
  → 200 {report dict — voir §5.2}
  → 422 si year ∉ [2020, current_utc_year + 1] / basis invalide / entity_type != sole_proprietor / settings absents

GET /api/reports/t2125/pdf?year=YYYY&basis=accrual|cash
  → 200 application/pdf
  Headers: Content-Disposition: attachment; filename=t2125-YYYY-basis.pdf
           Cache-Control: no-store, no-cache, must-revalidate, max-age=0
           Pragma: no-cache

GET /api/reports/t2125/csv?year=YYYY&basis=accrual|cash
  → 200 text/csv; charset=utf-8
  Headers: Content-Disposition: attachment; filename=t2125-YYYY-basis.csv
           Cache-Control: no-store, no-cache, must-revalidate, max-age=0
  Body commence par BOM UTF-8 \xef\xbb\xbf
```

### 5.2 Format du dict `report`

```json
{
  "year": 2025,
  "basis": "accrual",
  "period": {"start": "2025-01-01", "end": "2025-12-31"},
  "entity_type": "sole_proprietor",
  "province": "QC",
  "company_name": "Mon Entreprise",
  "bn_number": "123456789",
  "gross_income": 85000.00,
  "income_line": "8000",
  "expenses_by_arc_line": [
    {"arc_line": "8520", "label": "Publicité et promotion",
     "gross": 1200.00, "deductible": 1200.00, "categories": ["advertising"]},
    {"arc_line": "8523", "label": "Repas et représentation",
     "gross": 2400.00, "deductible": 1200.00, "categories": ["meals_entertainment"],
     "note": "50 % déductible"},
    {"arc_line": "8810", "label": "Frais de bureau",
     "gross": 1200.00, "deductible": 1200.00, "categories": ["office_expenses"]},
    {"arc_line": "8811", "label": "Fournitures de bureau",
     "gross": 600.00, "deductible": 600.00, "categories": ["office_supplies"]},
    {"arc_line": "9281", "label": "Frais relatifs aux véhicules à moteur",
     "gross": 5000.00, "deductible": 2000.00, "categories": ["vehicle_expenses"],
     "note": "40 % d'utilisation commerciale"},
    {"arc_line": "9945", "label": "Frais d'utilisation de la résidence aux fins de l'entreprise",
     "gross": 8000.00, "deductible": 1200.00, "categories": ["rent", "utilities", "insurance"],
     "note": "15 % de l'utilisation totale"}
  ],
  "total_expenses_deductible": 7400.00,
  "business_use_adjustments": {
    "home_office": {
      "percentage": 15.0,
      "applies_to": ["insurance", "rent", "utilities"],
      "original_total": 8000.00,
      "deductible_amount": 1200.00,
      "saved_to_arc_line": "9945",
      "label": "Frais d'utilisation de la résidence aux fins de l'entreprise"
    },
    "vehicle": {
      "percentage": 40.0,
      "applies_to": ["vehicle_expenses"],
      "original_total": 5000.00,
      "deductible_amount": 2000.00,
      "saved_to_arc_line": "9281",
      "label": "Frais relatifs aux véhicules à moteur"
    }
  },
  "net_income": 77600.00,
  "net_income_line": "9369",
  "is_partial_year": false
}
```

**Note importante** : la ligne 9945 dans `expenses_by_arc_line` contient déjà `deductible = 1200` (le montant ajusté). La somme de `total_expenses_deductible` est mathématiquement correcte en mode exclusif — pas de double-comptage.

### 5.3 Modification d'endpoint existant

**`PUT /api/settings/company`** accepte 2 nouveaux champs optionnels avec validation `math.isfinite()` + `[0, 100]` (cf. §4.1).

## 6. Format CSV

UTF-8 avec BOM `\xef\xbb\xbf`. Délimiteur `,`. Une ligne par enregistrement.

```csv
section,arc_line,label,gross_cad,deductible_cad,note
revenu,8000,Recettes brutes,85000.00,85000.00,
depense,8520,Publicité et promotion,1200.00,1200.00,
depense,8523,Repas et représentation,2400.00,1200.00,50% déductible
depense,8810,Frais de bureau,1200.00,1200.00,
depense,8811,Fournitures de bureau,600.00,600.00,
depense,9281,Frais relatifs aux véhicules à moteur,5000.00,2000.00,40% utilisation commerciale
depense,9945,Frais d'utilisation de la résidence aux fins de l'entreprise,8000.00,1200.00,15% utilisation totale
total,,Total dépenses déductibles,,7400.00,
total,9369,Bénéfice net,,77600.00,
```

**Sécurité CSV injection** : tous les champs string qui pourraient contenir une entrée utilisateur (`company_name` notamment dans une éventuelle ligne entête) **doivent** passer par `_sanitize_cell` existant (helper feature #7) avant d'être écrits. Les labels ARC sont des constantes — exempts.

**Valeurs section** (normatives, ASCII sans accents) : `revenu`, `depense`, `total`. Pas de section `ajustement` séparée (les ajustements sont des lignes `depense` avec note explicite). Pas de section `audit` (dropée).

## 7. Format PDF (ReportLab, ~1 page)

Pattern miroir du PDF P&L (feature #5). Couleurs cohérentes.

**Sécurité — escaping HTML** : tous les strings user-fournis (`company_name`, `bn_number`, `province`) passent par `html.escape()` avant interpolation dans `Paragraph(...)`. ReportLab parse un sous-ensemble XML — un `<` non-échappé casse le rendu.

```python
from html import escape as html_escape
# ...
title_text = f"État T2125 — Année fiscale {report['year']}"
company_text = html_escape(report.get("company_name") or "(sans nom)")
```

Structure :

1. **En-tête** :
   - Titre : « État T2125 — Année fiscale YYYY »
   - Nom entreprise + BN + base (Exercice/Caisse) + période
   - Date de génération : « Généré le DD mois YYYY à HH:MM »

2. **Section Revenus** : ligne unique 8000 avec total.

3. **Si `is_partial_year`** : bandeau orange en haut : « ⚠ Rapport partiel — l'année YYYY n'est pas terminée. Données du 1er janvier au DD mois YYYY uniquement. »

4. **Section Dépenses** : tableau colonnes ARC line / Libellé / Brut / Déductible / Note. Une ligne par `arc_line`. Lignes 9945 et 9281 (ajustements) sont visuellement distinctes (fond bleu pâle) pour signaler qu'elles résultent d'un calcul.

5. **Bénéfice net** : grand total teal (`#008F7A`).

6. **Encadré « À compléter manuellement sur le T2125 officiel »** (texte statique, encadré 1pt bordure `#d1d5db`, fond `#fef3c7` pour attirer l'œil) :
   - Déduction pour amortissement (DPA) — Annexe T2125-DPA (ligne 9936)
   - Bureau à domicile, si applicable : taxes municipales, intérêts hypothécaires, assurance habitation (non capturés par FacturePro) — ligne 9945
   - Véhicule : amortissement et intérêts du véhicule (DPA véhicule) — sous-ligne 9281

7. **Note cross-feature** (petite, en bas) : « Pour le rapport TPS/TVQ détaillé, consulte l'onglet TPS/TVQ. »

**Formatage des montants** : `f"{value:,.2f} $".replace(",", " ")` — séparateur milliers = espace fine insécable, virgule décimale forcée (cohérent FR-CA). Helper `_t2125_format_money(v: float) -> str`.

## 8. UI flow

### 8.1 Modification `ReportsPage`

Ajouter un 3ᵉ onglet « Déclaration T2125 » à côté de TPS/TVQ et P&L. Le composant tab affiche `T2125ReportSection`.

### 8.2 Composant `T2125ReportSection` (nouveau)

`frontend/src/components/T2125ReportSection.js`.

**State local** :
```jsx
const [year, setYear] = useState(new Date().getFullYear() - 1);
const [basis, setBasis] = useState("accrual");
const [report, setReport] = useState(null);
const [loading, setLoading] = useState(false);
const [settings, setSettings] = useState(null);
const [error, setError] = useState(null);
```

**useEffect au mount** : `axios.get(BACKEND_URL + "/api/settings/company")` → `setSettings(r.data)`.

**Si `settings === null` (pas encore chargé)** : afficher spinner.

**Si `settings.entity_type !== "sole_proprietor"`** : afficher un encart info plein conteneur :
> ℹ **Ce rapport est destiné aux entreprises individuelles.** Pour ta société, utilise l'onglet « État des résultats » — ton comptable saura adapter pour le T2.

**Sinon** : afficher le formulaire (sélecteur année + radio basis + bouton Générer).

**Sélecteurs** :
- Année : `<select>` listant `current_year-4` à `current_year` (5 options). Backend accepte `2020` minimum mais l'UI montre 5 ans.
- Base : 2 radios « Exercice » (accrual) / « Caisse » (cash). Default = accrual.

**Bouton Générer** :
```js
try {
  setLoading(true);
  setError(null);
  const r = await axios.get(`${BACKEND_URL}/api/reports/t2125?year=${year}&basis=${basis}`);
  setReport(r.data);
} catch (e) {
  setError(e.response?.data?.detail || "Erreur lors de la génération du rapport");
} finally {
  setLoading(false);
}
```

**Affichage du rapport** (après set) :
- En-tête : entreprise, BN, période, base, indicateur partiel si applicable.
- Tableau revenus + dépenses par ligne ARC (toutes les lignes y compris 9945/9281 ajustements).
- Si `business_use_adjustments` non vide → sous-section expliquant les calculs.
- Bénéfice net.
- Encadré « À compléter manuellement » (mêmes 3 items que le PDF).
- Note vers onglet TPS/TVQ.
- 2 boutons : **Télécharger PDF** et **Télécharger CSV**.

**Téléchargements** (pattern blob auth identique feature #8) :

```jsx
const downloadPdf = async () => {
  try {
    const r = await axios.get(
      `${BACKEND_URL}/api/reports/t2125/pdf?year=${year}&basis=${basis}`,
      { responseType: "blob" }
    );
    const url = URL.createObjectURL(r.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = `t2125-${year}-${basis}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    setError("Erreur lors du téléchargement du PDF");
  }
};
// Idem pour CSV (responseType: blob, MIME text/csv géré par le navigateur)
```

### 8.3 Modifications `SettingsPage`

Dans la section « Informations fiscales » existante :

```jsx
<label>Bureau à domicile — % surface utilisée pour l'entreprise
  <input type="number" min="0" max="100" step="0.1"
         value={settings.home_office_percentage ?? 0}
         onChange={e => {
           const v = e.target.value;
           setSettings({...settings,
             home_office_percentage: v === "" ? 0 : parseFloat(v) || 0});
         }}
         placeholder="0" />
  <small style={{color:"#6b7280"}}>
    Ex: bureau de 15 m² dans une maison de 100 m² = 15. Mettre 0 si bureau commercial.
  </small>
</label>

<label>Véhicule — % utilisation commerciale
  <input type="number" min="0" max="100" step="0.1"
         value={settings.vehicle_business_percentage ?? 0}
         onChange={e => {
           const v = e.target.value;
           setSettings({...settings,
             vehicle_business_percentage: v === "" ? 0 : parseFloat(v) || 0});
         }}
         placeholder="0" />
  <small style={{color:"#6b7280"}}>
    Ex: 12 000 km commerciaux / 30 000 km total = 40. Mettre 0 si véhicule purement commercial.
  </small>
</label>
```

**Notes** :
- Utilisation de `??` (nullish coalescing) au lieu de `===` — `null`/`undefined` sont traités comme `0` pour les nouveaux utilisateurs dont les champs n'existent pas encore.
- `step="0.1"` pour permettre les valeurs décimales (cohérent avec le backend float).

## 9. Edge cases

| Cas | Comportement |
|-----|--------------|
| `entity_type != "sole_proprietor"` | 422 + UI affiche message informatif. |
| `year < 2020 ou > current_utc_year + 1` | 422. Le `+1` absorbe la dérive Quebec UTC. |
| `basis` invalide | 422. |
| **Aucun document `company_settings`** | 422 « Complète tes infos dans Réglages ». Le frontend ouvre Settings au lieu de générer. |
| Aucune dépense pour l'année | `expenses_by_arc_line = []` (ou seulement ajustements si home_pct>0 mais 0 dépenses), totaux à 0. |
| Aucun revenu | `gross_income = 0`, `net_income` négatif possible. |
| `home_office_percentage = 0` ou absent | Pas de ligne 9945. Catégories `rent`/`utilities`/`insurance` sur leurs lignes ARC normales. |
| `home_office_percentage > 0` mais aucune dépense rent/utilities/insurance | Ligne 9945 avec `gross=0, deductible=0`. Non bloquant — montre transparence. |
| `home_office_percentage = 100` | Ligne 9945 = 100% du original_total (cas extrême). |
| `vehicle_business_percentage = 0` | Pas d'ajustement véhicule. `vehicle_expenses` sur ligne 9281 à 100% comme une dépense normale. |
| `vehicle_business_percentage > 0` | Ligne 9281 remplacée par le calcul `gross × %`. |
| Tentative `home_office_percentage = NaN/inf` via PUT | 422 « doit être un nombre fini ». |
| Tentative `home_office_percentage = 150` | 422 « entre 0 et 100 ». |
| Catégorie `other` (arc_line = `""`) | `_t2125_flatten_pnl_expenses` utilise `or "9270"` → tombe sur ligne 9270. |
| Catégorie inconnue dans expense snapshot (futur) | Pareil — ligne 9270. |
| Multi-devise USD/EUR | `_aggregate_pnl` convertit déjà via `exchange_rate_to_cad`. |
| Année courante (rapport partiel) | `is_partial_year = true`. Frontend + PDF affichent bandeau orange. |
| Quebec timezone (Dec 31 23:30 local = Jan 1 04:30 UTC) | Le `+1` sur `upper_year` permet de soumettre l'année voulue. |
| `company_name` contenant `<script>` ou caractères CSV-injection (`=cmd`) | PDF : `html.escape` neutralise. CSV : `_sanitize_cell` strip le préfixe injection. |
| Invoice `status="partial"` (feature #6) en cash basis | Reuse `_aggregate_pnl` qui filtre `status="paid"` seulement → les `partial` sont exclus en cash basis. **Limitation documentée en §10.** |
| Expense créée via bank-recon (feature #7) | Inclus si `category_code` est défini et `expense_date` dans la plage. Pareil pour OCR feature #8. |
| Internal exception dans `_aggregate_pnl` | Propagé comme 500. Frontend affiche toast « Erreur lors de la génération — réessaie. » |

## 10. Limites v1

- **T2125 seulement** (sole_proprietor). T2 corporation hors scope.
- **Pas de reproduction fidèle du formulaire ARC** (rapport synthèse).
- **Pas de calcul DPA** (amortissement). Encadré « à compléter ».
- **Pas de capture détaillée bureau à domicile** (taxes municipales, hypothèque, assurance habitation distincts). L'utilisateur ajoute manuellement.
- **Pas de capture véhicule détaillée** (DPA véhicule, intérêt prêt auto, assurance véhicule séparée).
- **Année civile forcée** (loi 249.1 LIR).
- **Pas d'historique des rapports générés**.
- **Cash basis = approximation** : utilise `issue_date` (filtré `status="paid"`) — une facture émise en décembre et payée en janvier compte dans l'année d'émission. **Les factures `status="partial"` (feature #6) sont exclues en cash basis** — le revenu partiellement reçu n'apparaît pas, ce qui peut sous-estimer le revenu cash. Le comptable devrait vérifier avec les payments[] si exact.
- **Quelques arc_lines sont des codes GIFI plutôt que des lignes T2125 officielles** (8620, 8740, 8811, 8960, 9220). Le comptable les re-affecte aux bonnes lignes T2125 lors de la transcription. Documenté.
- **Section TPS/TVQ audit retirée** — consulter l'onglet TPS/TVQ séparément.
- **`T2125_LINE_LABELS` figé sur la version T2125 2024**. À mettre à jour si l'ARC publie une nouvelle version (constante `T2125_LABEL_TABLE_TAX_YEAR = 2024`).
- **Pas de bouton "vérifier données" préalable** — l'utilisateur génère et lit le rapport. Si vide, il revient.

## 11. Tests

### 11.1 Unitaires — `backend/tests/test_t2125_export.py`

- **`_t2125_flatten_pnl_expenses`** :
  - `expense_groups` vide → dict vide.
  - 2 groupes avec catégories → flatten correct.
  - Catégorie `other` (arc_line = `""`) → arc_line `"9270"` dans le flat.
- **`_t2125_group_by_arc_line`** :
  - 2 catégories partageant l'arc_line → sommées (mais ce cas n'existe pas dans EXPENSE_CATEGORIES actuel ; on teste avec fixtures custom).
  - `exclude_codes` retire les catégories listées.
  - Note "50 % déductible" présente sur ligne 8523.
  - Tri par arc_line croissant.
- **`_t2125_compute_home_office_adjustment`** :
  - `home_pct=0` → None.
  - `home_pct=15` + utilities `gross=8000` → deductible_amount = 1200.
  - `home_pct=100` + rent `gross=12000` → deductible_amount = 12000.
  - Catégories absentes (rent=0) → original_total exclut.
  - `applies_to` est trié alphabétiquement.
- **`_t2125_compute_vehicle_adjustment`** :
  - Idem pour vehicle_expenses uniquement (un seul code).
  - `vehicle_pct=40` + vehicle_expenses 5000 → 2000.
- **`_build_t2125_report`** :
  - Année 2099 + données mockées via fixture MongoDB → `net_income` correct.
  - `entity_type=corporation` → HTTPException 422.
  - `year=1999` → 422.
  - `year=current_utc_year + 2` → 422.
  - `year=current_utc_year + 1` → OK (timezone buffer).
  - `basis="xxx"` → 422.
  - Aucun `company_settings` → 422 avec message "Complète tes infos dans Réglages".
  - `home_office_percentage=15` + dépenses rent/utilities présentes → ligne 9945 émise, catégories ABSENTES de leurs lignes ARC originales (mode exclusif).
  - `home_office_percentage=0` + dépenses rent/utilities → catégories sur leurs lignes ARC normales, pas de ligne 9945.
  - `is_partial_year=True` quand year >= current_utc_year.
- **Couverture T2125_LINE_LABELS** :
  - Parametrize test sur EXPENSE_CATEGORIES : pour chaque `c["arc_line"]` non-vide → `c["arc_line"] in T2125_LINE_LABELS`. Fails si une catégorie est ajoutée sans libellé correspondant.

### 11.2 Intégration — `backend/tests/test_t2125_export_integration.py`

Utilise `TestClient(server.app)` + fixtures `client` + `auth_headers` (pattern feature #8).

- `GET /api/reports/t2125?year=2099&basis=accrual` → 200 + dict valide avec `entity_type` + `period`.
- `GET /api/reports/t2125/pdf?year=2099&basis=accrual` → 200, `Content-Type: application/pdf`, body commence par `%PDF`.
- `GET /api/reports/t2125/csv?year=2099&basis=accrual` → 200, `Content-Type: text/csv`, body commence par BOM `\xef\xbb\xbf`, contient ligne `total,9369,Bénéfice net,...`.
- E2E mode exclusif : créer 2 invoices `sent` (issue_date 2099) + expenses (rent 12000, advertising 1200), set `home_office_percentage=15`, GET t2125 → vérifier (a) pas de ligne 8910 (rent retirée), (b) ligne 9945 avec gross=12000, deductible=1800, (c) net_income = 85000 - 1200 - 1800 = 82000.
- E2E pas d'ajustement : même expenses, `home_office_percentage=0`, GET t2125 → ligne 8910 présente, pas de ligne 9945.
- `entity_type=corporation` → 422.
- `year=1999` → 422.
- `year=current_utc_year + 1` → 200 (timezone buffer).
- `basis="xxx"` → 422.
- PUT `/api/settings/company` `{home_office_percentage: 50}` → 200.
- PUT `{home_office_percentage: 150}` → 422.
- PUT `{home_office_percentage: -5}` → 422.
- PUT `{home_office_percentage: "abc"}` → 422.
- PUT `{home_office_percentage: float("inf")}` → 422 (testé via json string `"Infinity"` qui parse en inf Python).
- **Isolation multi-tenant** : user_A crée des données 2099, user_B fait GET t2125 année 2099 → `gross_income=0` et `expenses_by_arc_line=[]` (zéro fuite).
- **company_name avec `<script>`** + génération PDF → body PDF ne contient pas `<script>` (escape).
- **company_name commençant par `=`** + génération CSV → première cellule ne commence pas par `=`.

**Cible : ~25 tests** (14 unitaires + 11 intégration).

### 11.3 E2E manuel après push

- Settings : entity_type=sole_proprietor + home_office_percentage=15 + vehicle_business_percentage=40.
- Rapports → onglet Déclaration T2125 → Année=2025, Base=Exercice → Générer.
- Vérifier aperçu UI (totaux, ajustements visibles avec note %, encadré « à compléter »).
- Télécharger PDF (ouvrir Aperçu macOS), vérifier mise en forme + escapes corrects.
- Télécharger CSV (ouvrir Excel FR), vérifier accents corrects via BOM + montants format dot.
- Tester entity_type=corporation → vérifier message informatif.
- Modifier home_office à 0 → regénérer → vérifier que la ligne 9945 disparaît et que rent/utilities apparaissent normalement.

## 12. Observabilité

Logs Python `print()` (Render streaming) :

- Par génération réussie : `INFO t2125_report user=<id> year=<year> basis=<basis> expense_line_count=<n>`.
  - **NE PAS logger `net_income`** (PII financière).
- Par 422 sur validation : pas de log (cas normal).
- Par 500 imprévu : `ERROR t2125_report_failed user=<id> type=<exception_class>` (sans `str(e)` pour éviter leak).

## 13. Performance

Latence cible : < 500 ms (réutilise `_aggregate_pnl`). PDF gen ReportLab : < 1 s. Aucun appel externe.

## 14. Rollout

1. Push main → Render redéploie backend, Vercel redéploie frontend.
2. Pas de feature flag.
3. Pas de variable d'env nouvelle.
4. Pas de migration de données.
5. Les utilisateurs existants verront `home_office_percentage` et `vehicle_business_percentage` à `0`/absents au premier chargement de Settings. Le frontend les traite comme 0 via `??`.

## 15. Dépendances

Aucune nouvelle. ReportLab, pymongo, fastapi déjà utilisés. `html.escape` et `math.isfinite` sont stdlib.

## 16. Migration

Aucune. Les nouveaux champs `home_office_percentage` et `vehicle_business_percentage` apparaissent sur `company_settings` au prochain PUT contenant ces clés.
