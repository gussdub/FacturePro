# Expense Categories ARC — Catégorisation des dépenses pour conformité fiscale canadienne

**Date** : 2026-06-16
**Statut** : Brouillon, en attente de revue utilisateur
**Feature originale** : #3 dans la roadmap comptable (gap QuickBooks)

## Contexte et motivation

Aujourd'hui, le champ `category` de `db.expenses` est du texte libre — aucune validation, aucun lien avec les formulaires fiscaux canadiens. Le dashboard groupe dynamiquement par ce qu'il trouve, ce qui rend impossible :

- Un export T2125 propre en fin d'année (les libellés varient d'une dépense à l'autre).
- La distinction des règles de déductibilité (les repas sont 50 % seulement — l'utilisateur doit le calculer mentalement).
- La comparaison entre catégories sur plusieurs années si les libellés changent.

L'objectif est de **structurer les catégories de dépenses** en s'appuyant sur les lignes officielles de l'ARC (T2125 pour les travailleurs autonomes, GIFI partagé pour les sociétés T2), tout en gardant la possibilité d'une catégorie "Autre" libre pour les cas hors-standards.

Un futur travail (feature #10) — l'export T2125/T2 de fin d'année — s'appuiera directement sur les snapshots stockés ici.

## Scope

**Inclus** :
- Liste canonique de ~20 catégories ARC, organisées en 5 groupes thématiques.
- Catégorie spéciale "Autre" avec libellé libre.
- Snapshot des métadonnées de catégorie (code, libellé, ligne ARC, % déductible) au moment de la création de chaque dépense.
- Calcul automatique du montant déductible (`deductible_amount = amount_cad × deductible_percentage / 100`).
- Picker UI groupé (`<optgroup>` natif) avec zone d'aide contextuelle quand `deductible_percentage < 100`.
- Sélecteur d'entité fiscale dans Settings (`sole_proprietor` ou `corporation`) — métadonnée pour la future feature export.
- Endpoint public `GET /api/expense-categories`.

**Exclus** :
- Export T2125/T2 PDF ou CSV — sera la feature #10 séparée.
- Catégorisation automatique par IA depuis le libellé de la dépense — possible future enhancement.
- Catégories personnalisées créées par l'utilisateur (au-delà du fourre-tout "Autre").
- Sous-catégories ou hiérarchie (le champ `description` reste pour les détails).
- Règles fiscales avancées (plafond TVQ sur repas, % CCA sur véhicule, etc.) — la v1 a juste le 50 % sur les repas.

## Décisions de design

| Question | Choix | Raison |
|---|---|---|
| Formulaire cible | T2125 + T2 | Couvre travailleurs autonomes ET corporations (codes GIFI partagés à ~90 %) |
| Catégories libres | Non, sauf "Autre" | Standardisation pour export fiscal cohérent |
| Calcul déductible | Auto, % par catégorie | Soulage l'utilisateur du calcul manuel des repas 50 % |
| UI picker | Dropdown groupé + zone d'aide contextuelle | Natif mobile/desktop, scannable, calcul visible en temps réel |
| Type d'entité | Settings (radio/select) | Donnée stable par entreprise, pas par dépense |
| Migration data existante | Aucune (0 dépense en prod) | Trivial — pas de stratégie nécessaire |

## Catégories ARC canoniques

Stockées en constante module-level `EXPENSE_CATEGORIES` dans `backend/server.py`. Chaque entrée :

```python
{
    "code": str,              # identifiant stable, ex: "office_expenses"
    "label_fr": str,          # libellé affiché, ex: "Frais de bureau"
    "label_en": str,          # libellé anglais (pour future i18n / export)
    "arc_line": str,          # numéro ligne T2125 / code GIFI, ex: "8810"
    "deductible_percentage": int,  # 100 par défaut, 50 pour repas
    "group": str,             # groupe affichage : office | marketing | premises | travel | personnel
}
```

**Liste complète** :

| Code | Libellé FR | Ligne ARC | Déductible | Groupe |
|---|---|---|---|---|
| `office_expenses` | Frais de bureau | 8810 | 100 % | office |
| `office_supplies` | Fournitures | 8811 | 100 % | office |
| `professional_fees` | Honoraires professionnels | 8860 | 100 % | office |
| `bank_charges` | Frais bancaires | 8620 | 100 % | office |
| `subscriptions` | Abonnements et licences | 8740 | 100 % | office |
| `advertising` | Publicité et promotion | 8520 | 100 % | marketing |
| `meals_entertainment` | Repas et représentation | 8523 | **50 %** | marketing |
| `rent` | Loyer | 8910 | 100 % | premises |
| `utilities` | Services publics | 9220 | 100 % | premises |
| `insurance` | Assurances | 8690 | 100 % | premises |
| `repairs_maintenance` | Entretien et réparations | 8960 | 100 % | premises |
| `travel` | Frais de déplacement | 9200 | 100 % | travel |
| `vehicle_expenses` | Frais de véhicule | 9281 | 100 % | travel |
| `delivery` | Livraison et fret | 9275 | 100 % | travel |
| `salaries` | Salaires et avantages | 9060 | 100 % | personnel |
| `subcontracts` | Sous-traitance | 9367 | 100 % | personnel |
| `management_fees` | Frais de gestion | 8871 | 100 % | personnel |
| `other` | Autre | (vide) | 100 % | other |

**Libellés de groupes** (utilisés dans `<optgroup>`) :

| Clé | Label affiché |
|---|---|
| `office` | Bureau et administration |
| `marketing` | Marketing |
| `premises` | Local et services publics |
| `travel` | Déplacements et véhicule |
| `personnel` | Personnel et services |
| `other` | Autre |

## Data model

### `expenses` (collection existante)

Le champ `category` (texte libre) **reste** pour la rétrocompatibilité d'affichage — c'est le libellé que le frontend lit dans les vues de liste. On **ajoute** 5 champs, tous snapshotés à la création :

| Champ | Type | Valeur |
|---|---|---|
| `category_code` | str | Code canonique (`office_expenses`), `"other"`, ou `""` si non choisie |
| `category_custom_label` | str | Libellé libre — seulement si `category_code === "other"` |
| `category_arc_line` | str | Snapshot de `arc_line` (ex: `"8810"`, ou `""` pour Autre) |
| `deductible_percentage` | int | Snapshot (défaut 100, 50 pour repas) |
| `deductible_amount` | float | Calculé : `round(amount_cad × deductible_percentage / 100, 2)` |

Le champ `category` (le label affiché) est dérivé au moment du POST :
- Si `category_code === "other"` → `category = category_custom_label`
- Si `category_code` est canonique → `category = catalog_entry["label_fr"]`
- Sinon → `category = expense_data.get("category", "")` (legacy free text)

**Snapshot, pas calcul à la volée** — si l'ARC change la ligne 8810 dans 3 ans, ou si la règle des repas passe à 60 %, les vieilles dépenses gardent leurs valeurs originales. Cohérent avec le pattern `tax_registrations` (feature #2).

### `company_settings`

Un champ ajouté :

| Champ | Type | Valeurs | Défaut |
|---|---|---|---|
| `entity_type` | str | `"sole_proprietor"` \| `"corporation"` | `"sole_proprietor"` |

Toute autre valeur reçue en PUT est ignorée silencieusement (validation souple, cohérent avec le projet).

## Backend

### Constante et helpers (`server.py`)

```python
EXPENSE_CATEGORIES = [
    {"code": "office_expenses", "label_fr": "Frais de bureau", "label_en": "Office expenses",
     "arc_line": "8810", "deductible_percentage": 100, "group": "office"},
    # ... 17 autres
]

EXPENSE_CATEGORY_GROUPS = {
    "office":    "Bureau et administration",
    "marketing": "Marketing",
    "premises":  "Local et services publics",
    "travel":    "Déplacements et véhicule",
    "personnel": "Personnel et services",
    "other":     "Autre",
}

def _find_category(code):
    """Retourne le dict catalog correspondant à code, ou None si inconnu."""
    return next((c for c in EXPENSE_CATEGORIES if c["code"] == code), None)

def _build_expense_category_snapshot(expense_data, amount_cad):
    """Retourne les 5 champs catégorie à snapshoter dans le doc expense.
    Accepts dict expense_data and the computed amount_cad."""
    code = (expense_data.get("category_code") or "").strip()
    custom_label = expense_data.get("category_custom_label", "").strip()
    cat = _find_category(code)
    if code == "other":
        label = custom_label or "Autre"
        arc_line, percentage = "", 100
    elif cat:
        label = cat["label_fr"]
        arc_line = cat["arc_line"]
        percentage = cat["deductible_percentage"]
    else:
        # Unknown or empty code: graceful, use whatever raw category text was sent
        label = expense_data.get("category", "")
        arc_line, percentage = "", 100
        code = code  # preserve whatever was sent (could be empty)
    deductible = round(amount_cad * percentage / 100, 2)
    return {
        "category": label,
        "category_code": code,
        "category_custom_label": custom_label if code == "other" else "",
        "category_arc_line": arc_line,
        "deductible_percentage": percentage,
        "deductible_amount": deductible,
    }
```

### Endpoints

| Endpoint | Méthode | Changement |
|---|---|---|
| `/api/expense-categories` | GET | **Nouveau**. Retourne `{"categories": EXPENSE_CATEGORIES, "groups": EXPENSE_CATEGORY_GROUPS}`. Pas d'auth requise (données publiques). |
| `/api/expenses` | POST | Branche `_build_expense_category_snapshot` avant `insert_one`. Les 5 nouveaux champs et le `category` label sont ajoutés au doc. |
| `/api/expenses/{id}` | PUT | Deux cas distincts : (a) `category_code` dans le body → re-snapshote les 5 champs catégorie + recalcule `deductible_amount`. (b) seul `amount` change (sans `category_code`) → recalcule UNIQUEMENT `deductible_amount` en utilisant le `deductible_percentage` déjà stocké (le snapshot reste figé). |
| `/api/settings/company` | GET | Retourne aussi `entity_type` (`"sole_proprietor"` si absent). |
| `/api/settings/company` | PUT | Accepte `entity_type ∈ {"sole_proprietor", "corporation"}`. Autres valeurs : ignorées silencieusement (non stockées, valeur précédente conservée). |
| `/api/dashboard/expense-analytics` | GET | **Inchangé v1** (continue de grouper par `category` label). Pourra plus tard ajouter `total_deductible` calculé depuis `deductible_amount`. |

### Validation

- `category_code` doit être un code canonique, `"other"`, ou vide. **Aucune valeur n'est rejetée** — un code inconnu tombe en graceful degradation (label = ce que l'utilisateur a tapé, % = 100).
- `entity_type` autre que les 2 valeurs canoniques → ignoré.
- Tous les champs sont optionnels en POST (cohérent avec le comportement actuel).

## Frontend

### `ExpensesPage.js`

**Au mount** : `useEffect` qui appelle `axios.get('/api/expense-categories')` et stocke dans state local `{categories, groups}`.

**Formulaire dépense** — remplace l'input texte libre `category` par :

1. `<select>` groupé avec `<optgroup>` (un par groupe), libellés français des groupes.
2. Chaque option affiche : `"{label_fr}{ deductible_percentage if < 100 } ({arc_line})"` — ex : `"Repas et représentation 50% (8523)"`.
3. Option finale `<option value="other">Autre catégorie…</option>`.

**Si `category_code === "other"`** : afficher un `<input>` libre juste sous le select, label "Préciser la catégorie", placeholder `"ex: Cotisations syndicales"`. Lié à state `category_custom_label`.

**Si la catégorie sélectionnée a `deductible_percentage < 100`** : afficher une zone d'aide jaune sous le select :

```
ℹ 50 % seulement déductible — montant déductible : 90,00 $ sur 180,00 $
```

Calcul côté frontend = `(amount × percentage / 100).toFixed(2)`. Backend recalcule à la sauvegarde (snapshot fait foi).

**Édition d'une dépense** : à l'ouverture, peupler `category_code` depuis le doc, puis :
- Si le code n'existe pas dans la liste (ex: dépense créée avant cette feature ou code obsolète) → afficher en mode "Autre" avec le libellé legacy.
- Sinon, sélectionner la bonne option.

### `SettingsPage.js`

Ajouter dans la section infos entreprise (avant ou après la section "Numéros officiels" existante) :

```jsx
<div style={{ marginBottom: 16 }}>
  <label>
    Type d'entité fiscale
    <span title="Détermine le formulaire de déclaration fiscale utilisé pour exporter tes dépenses.">ⓘ</span>
  </label>
  <select value={settings.entity_type} onChange={...}>
    <option value="sole_proprietor">Travailleur autonome (T2125)</option>
    <option value="corporation">Société par actions (T2)</option>
  </select>
</div>
```

## Tests

### Unitaires (`backend/tests/test_expense_categories.py`)

- `_find_category("office_expenses")` retourne le dict avec `arc_line == "8810"`.
- `_find_category("nonexistent")` retourne `None`.
- `EXPENSE_CATEGORIES` contient exactement 18 entrées (17 canoniques + "other") — count précis pour catcher les ajouts accidentels.
- Chaque entrée a les 6 clés requises et types attendus.
- `meals_entertainment` a `deductible_percentage == 50`.
- Toutes les autres entrées ont `deductible_percentage == 100`.
- `_build_expense_category_snapshot` pour chaque chemin (canonical, other, unknown) retourne la forme attendue.

### Intégration (`backend/tests/test_expense_categories_integration.py`)

- `GET /api/expense-categories` : 200, retourne `{categories, groups}` avec les bonnes longueurs.
- `POST /api/expenses` avec `category_code: "office_expenses"`, `amount: 100` → doc DB a `category: "Frais de bureau"`, `category_arc_line: "8810"`, `deductible_percentage: 100`, `deductible_amount: 100`.
- `POST /api/expenses` avec `category_code: "meals_entertainment"`, `amount: 200` → `deductible_percentage: 50`, `deductible_amount: 100`.
- `POST /api/expenses` avec `category_code: "other"`, `category_custom_label: "Cotisations"` → `category: "Cotisations"`, `category_arc_line: ""`, `deductible_percentage: 100`.
- `POST /api/expenses` avec `category_code: "invalid_xyz"` → 200, `deductible_percentage: 100`, pas de 4xx.
- `PUT /api/expenses/{id}` avec nouveau `category_code` → re-snapshot des 5 champs.
- `PUT /api/expenses/{id}` avec nouvel `amount`, même `category_code: meals_entertainment` → `deductible_amount` recalculé.
- `GET /api/settings/company` retourne `entity_type` (défaut `"sole_proprietor"`).
- `PUT /api/settings/company` avec `entity_type: "corporation"` → `GET` retourne `"corporation"`.
- `PUT /api/settings/company` avec `entity_type: "invalid"` → ignoré, `GET` retourne valeur précédente.

### Vérifications manuelles UI

| Cas | Attendu |
|---|---|
| Ouvrir dropdown catégorie | 6 groupes optgroup + "Autre" |
| Choisir "Frais de bureau" | Pas de zone d'aide jaune |
| Choisir "Repas et représentation 50%", amount = 200 $ | Zone jaune : "50% — 100,00 $ déductible" |
| Choisir "Autre" | Input libre "Préciser…" apparaît |
| Settings → switch corp/sole prop, save, refresh | Valeur persiste |
| Édition vieille dépense (code absent du catalog) | Mode "Autre" avec legacy label |

## Risques et limites

- **`POST /api/expenses` rétrocompatible** : si le frontend envoie le vieux payload avec `category` (texte libre) mais pas `category_code`, le doc DB enregistre `category_code: ""`, `deductible_percentage: 100`. Le dashboard continue de marcher.
- **Calcul `deductible_amount` côté backend lit `amount_cad`** : utilise déjà le code existant qui convertit en CAD via Frankfurter. Pas de calcul devises supplémentaire à faire.
- **Le `category` label est snapshoté FR uniquement** : pas de i18n v1. Si un utilisateur passe en EN plus tard, son dashboard verra des labels FR sur les vieilles dépenses (acceptable, label_en est dans le catalog pour une future bascule).
- **Le picker n'est pas searchable** : 18 catégories tiennent dans un dropdown natif sans souci. Si on monte à 50+, il faudra passer à un combobox.
- **Pas de validation côté frontend du code envoyé** : si le frontend envoie un code obsolète, le backend dégrade gracefully. Pas de message d'erreur explicite — c'est OK pour la v1.

## Métriques de succès

- Utilisateur peut catégoriser une nouvelle dépense en moins de 3 clics (dropdown + sélection + sauvegarde).
- Pour une dépense "Repas", le montant déductible apparaît automatiquement et est correct (50 % du `amount_cad`).
- Dashboard expense-analytics continue d'afficher les bonnes catégories sans modification de code.
- Settings → switch `sole_proprietor` / `corporation` round-trip persiste.
- Aucune régression sur la rétrocompatibilité du POST `/api/expenses` (test : payload sans `category_code` continue de marcher).
- `GET /api/expense-categories` retourne la liste sans authentification.
