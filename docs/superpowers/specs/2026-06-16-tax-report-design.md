# Rapport TPS/TVQ trimestriel — Sales Tax Report

**Date** : 2026-06-16
**Statut** : Brouillon, en attente de revue utilisateur
**Feature originale** : #4 dans la roadmap comptable

## Contexte et motivation

Aujourd'hui, FacturePro stocke les taxes perçues sur les factures (`gst_amount`, `pst_amount`/QST, `hst_amount`, `province`) mais ne tracke aucune taxe payée sur les dépenses. L'utilisateur ne peut pas générer le rapport TPS/TVQ trimestriel qu'il doit produire à chaque échéance fiscale (ARC + Revenu Québec).

Ce rapport est typiquement le document le plus demandé par les comptables et le plus utile à l'utilisateur final (auto-calcul net à remettre, archive d'audit). C'est aussi la base de la future feature #10 (Export T2125/T2 annuel).

L'objectif : permettre la saisie des CTI/RTI (crédits/remboursements de taxe sur intrants) côté dépenses, et générer un rapport trimestriel ou personnalisé avec sommaire visuel et détail format CRA/Revenu Québec, exportable en PDF.

## Scope

**Inclus** :
- 4 nouveaux champs sur `expenses` : `gst_paid_cad`, `qst_paid_cad`, `hst_paid_cad`, `taxes_auto_computed` (bool).
- Nouveau champ `province` sur `company_settings` (default `"QC"`, valeurs `QC/ON/BC/AB/SK/MB/NB/NS/PE/NL/YT/NU/NT`).
- Helper frontend `computeTaxesPaid(amountGross, province)` qui calcule TPS/TVQ/TVH à partir d'un brut TTC + province.
- Bouton "🧮 Calculer auto" sur le formulaire dépense qui appelle le helper et remplit les 3 champs.
- Endpoint `GET /api/reports/sales-tax?start&end` retournant un sommaire + détail ARC + détail Revenu Québec en JSON.
- Endpoint `GET /api/reports/sales-tax/pdf?start&end` retournant un PDF A4.
- Nouvelle page frontend "Rapports" avec quick-picker trimestre + custom range + cartes sommaire + détails dépliables + bouton télécharger PDF.
- Tests unitaires (calcul + parsing période) et intégration (endpoints + filtres).

**Exclus** :
- Tracking automatique des taxes payées sur dépenses CSV importées (les expenses CSV resteront sans taxes pour v1 — un futur work pourra brancher `computeTaxesPaid` dessus).
- Calcul TPS/TVQ sur dépenses en devises étrangères (USD/EUR/GBP) — pour v1, le bouton "Calculer auto" est désactivé si `currency != "CAD"`, l'utilisateur saisit manuellement.
- Export CSV du rapport — différé. Si demande, ajoutable séparément.
- Pré-remplissage automatique des taxes payées lors de la création de la dépense — toujours opt-in par bouton, sécurité contre les faux ITC.
- État des résultats (P&L) — feature #5.
- Export T2125/T2 fin d'année — feature #10.

## Décisions de design

| Question | Choix | Raison |
|---|---|---|
| Tracking taxes payées | Champs manuels + bouton "Calculer auto" | Compromis précision (utilisateur peut overrider) et UX (bouton remplit) |
| Période | Trimestre prédéfini + plage personnalisée | Couvre 90 % cas + flexibilité audit |
| Format | Sommaire visuel + détail CRA + détail Revenu Québec | Lecture rapide + copier-coller dans formulaire en ligne |
| Export | Affichage web + PDF | PDF utile pour archive et envoi comptable, CSV différé |
| Province | Stockée sur company_settings, pas sur expense | Simplicité v1, override manuel si rare cas inter-provinces |
| Currency | Auto-calc CAD seulement, manuel sinon | Évite fausses présomptions de taxabilité |
| Filtre invoices | Exclut `draft`, inclut `sent`/`paid`/`overdue` | Reflète la méthode comptabilité d'exercice (accrual basis, défaut Canada) |
| Filtre expenses | Tous statuts inclus | Le statut interne (pending/approved) ne reflète pas la déductibilité fiscale |

## Data model

### `expenses` (collection existante)

4 nouveaux champs, tous optionnels (défaut 0 ou false) :

| Champ | Type | Sens |
|---|---|---|
| `gst_paid_cad` | float | TPS payée sur cette dépense (CAD). Défaut 0. |
| `qst_paid_cad` | float | TVQ payée. Défaut 0. |
| `hst_paid_cad` | float | TVH payée (ON, NB, NS, PE, NL). Défaut 0. |
| `taxes_auto_computed` | bool | `true` si rempli via bouton, `false` si manuel ou édité manuellement après l'auto-calc. Défaut `false`. |

### `company_settings`

| Champ | Type | Valeurs | Défaut |
|---|---|---|---|
| `province` | str | `QC`, `ON`, `BC`, `AB`, `SK`, `MB`, `NB`, `NS`, `PE`, `NL`, `YT`, `NU`, `NT` | `"QC"` |

Toute autre valeur reçue en PUT est ignorée (validation souple, cohérent avec `entity_type`).

**Aucune migration nécessaire** : 0 dépenses en prod. Les anciennes dépenses sans ces champs sont traitées comme 0 dans les sommes (graceful via `.get(field, 0)`).

## Backend

### Helpers (`server.py`)

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
    autres  : 5 % TPS seulement      → diviseur 105

    Retourne {gst, qst, hst}.
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
    # BC, AB, SK, MB, YT, NU, NT
    return {"gst": round(amount_gross * 5 / 105, 2), "qst": 0, "hst": 0}


def _quarter_to_dates(year, quarter):
    """Q1=jan-mar, Q2=avr-jun, Q3=jul-sep, Q4=oct-dec.
    Retourne (start: 'YYYY-MM-DD', end: 'YYYY-MM-DD')."""
    starts = {"Q1": "01-01", "Q2": "04-01", "Q3": "07-01", "Q4": "10-01"}
    ends   = {"Q1": "03-31", "Q2": "06-30", "Q3": "09-30", "Q4": "12-31"}
    return (f"{year}-{starts[quarter]}", f"{year}-{ends[quarter]}")
```

### Endpoints modifiés

| Endpoint | Changement |
|---|---|
| `POST /api/expenses` | Accepte `gst_paid_cad`, `qst_paid_cad`, `hst_paid_cad`, `taxes_auto_computed`. Stocke tel quel, défauts 0/false. |
| `PUT /api/expenses/{id}` | Pareil. Pas de recalcul magique. L'utilisateur a la maîtrise. |
| `GET /api/settings/company` | Retourne aussi `province` (default `"QC"`). |
| `PUT /api/settings/company` | Accepte `province ∈ PROVINCES_VALID`. Autres valeurs : ignorées. |

### Nouveaux endpoints

`GET /api/reports/sales-tax?start=YYYY-MM-DD&end=YYYY-MM-DD`

Calcule et retourne :

```json
{
  "period": {"start": "2026-04-01", "end": "2026-06-30"},
  "summary": {
    "gst": {"collected": 1500.00, "paid": 320.00, "net": 1180.00},
    "qst": {"collected": 2992.50, "paid": 638.40, "net": 2354.10},
    "hst": {"collected": 0, "paid": 0, "net": 0}
  },
  "cra_detail": {
    "line_101_sales": 30000.00,
    "line_103_gst_collected": 1500.00,
    "line_103_hst_collected": 0,
    "line_106_itc_gst": 320.00,
    "line_106_itc_hst": 0,
    "line_109_net_gst": 1180.00,
    "line_109_net_hst": 0
  },
  "rq_detail": {
    "line_201_taxable_sales_qc": 30000.00,
    "line_203_qst_collected": 2992.50,
    "line_205_itr_qst": 638.40,
    "line_209_net_qst": 2354.10
  },
  "invoice_count": 12,
  "expense_count": 25
}
```

Logique :
- Invoices : `find({user_id, status: {$in: ["sent", "paid", "overdue"]}, issue_date: {$gte: start, $lte: end}})`.
- Expenses : `find({user_id, expense_date: {$gte: start, $lte: end}})`.
- Multi-devise sur invoices : `gst_amount × (1/exchange_rate_to_cad)` si `currency != "CAD"`. Hors-CAD compte normalement, contrairement à ce qu'on pourrait croire — c'est à l'utilisateur de zero-rater explicitement à la facturation s'il le faut.
- `line_101_sales` = somme des `subtotal_cad` (subtotal × `exchange_rate_to_cad`) — réutilise le code existant si déjà présent, sinon utilise `subtotal` directement pour les CAD.
- Les invoices avec `province = "ON"` (ou autre HST) alimentent `line_103_hst_collected` et `hst.collected`, jamais `gst.collected`. Logique exclusive.
- Pour les expenses : on additionne `gst_paid_cad`, `qst_paid_cad`, `hst_paid_cad` directement (déjà en CAD).

`GET /api/reports/sales-tax/pdf?start=YYYY-MM-DD&end=YYYY-MM-DD`

Génère un PDF A4 mono-page :
- Entête : logo + nom entreprise + titre "Rapport TPS / TVQ" + période + numéros d'enregistrement (snapshot via `_take_regs` de feature #2).
- Sommaire : 3 cartes côte à côte (TPS, TVQ, TVH).
- Détail format ARC : tableau 4 lignes (101, 103, 106, 109).
- Détail format Revenu Québec : tableau 4 lignes (201, 203, 205, 209).
- Footer : compteurs + date génération.

Réutilise les styles et helpers ReportLab de `generate_document_pdf`.

## Frontend

### `SettingsPage.js`

Nouveau dropdown "Province" à côté de "Type d'entité fiscale" (feature #3) :

```jsx
<select value={settings.province || 'QC'} onChange={...}>
  <option value="QC">Québec</option>
  <option value="ON">Ontario</option>
  <option value="BC">Colombie-Britannique</option>
  ...
</select>
```

13 options. Tooltip : *"Province utilisée pour le calcul automatique des taxes sur tes dépenses."*

### `ExpensesPage.js`

Après la section catégorie + helper déductible (feature #3), nouveau bloc "Taxes payées" :

```jsx
<div className="taxes-paid-section">
  <h4>Taxes payées (CTI/RTI)</h4>
  <div className="taxes-grid">
    <input label="TPS payée"   value={formData.gst_paid_cad} ... />
    <input label="TVQ payée"   value={formData.qst_paid_cad} ... />
    <input label="TVH payée"   value={formData.hst_paid_cad} ... />
  </div>
  <button onClick={handleAutoCompute} disabled={formData.currency !== 'CAD'}>
    🧮 Calculer auto (province {settings.province})
  </button>
  {formData.currency !== 'CAD' && (
    <p className="warning">Calcul auto disponible seulement en CAD.</p>
  )}
</div>
```

`handleAutoCompute` :
1. Lit `formData.amount` (gross, TTC).
2. Lit `settings.province` (fetché au mount via la même requête que d'autres données settings).
3. Appelle `computeTaxesPaid(amount, province)` — helper local JS.
4. Met à jour `formData.gst_paid_cad`, `qst_paid_cad`, `hst_paid_cad`, `taxes_auto_computed = true`.

Quand l'utilisateur édite manuellement un des 3 champs : `taxes_auto_computed → false`.

### Nouvelle page `ReportsPage.js`

Route et entrée de nav "Rapports". Composant principal :
- State : `period_mode` (`'quarter'` | `'custom'`), `year`, `quarter`, `customStart`, `customEnd`, `report` (data fetched).
- UI :
  - Radio : "Trimestre" vs "Période personnalisée"
  - Si trimestre : dropdowns année (4 dernières) + Q1-Q4
  - Si custom : 2 `<input type="date">`
  - Bouton "Générer"
- Au générer : fetch `GET /api/reports/sales-tax?start=...&end=...`, set `report`.
- Affichage `report` :
  - 3 cartes sommaire
  - `<details>` "Détail format ARC (T1 GST/HST)" avec tableau
  - `<details>` "Détail format Revenu Québec (FP-2500)" avec tableau
  - Compteurs
  - Bouton "Télécharger PDF" : `fetch(url, { headers: { Authorization: 'Bearer ...' } })` → response.blob() → `window.URL.createObjectURL(blob)` → `window.open(objectUrl)`. Le pattern existe déjà pour les invoices PDF dans `InvoicesPage.js`, à réutiliser tel quel.

## Tests

### Unitaires (`backend/tests/test_tax_report.py`)

- `_compute_taxes_paid(114.975, "QC")` → `{gst: 5.00, qst: 9.975 ≈ 9.98, hst: 0}` (à arrondir 2 décimales)
- `_compute_taxes_paid(113, "ON")` → `{gst: 0, qst: 0, hst: 13.00}`
- `_compute_taxes_paid(115, "NB")` → `{hst: 15.00}`
- `_compute_taxes_paid(105, "BC")` → `{gst: 5.00, qst: 0, hst: 0}`
- `_compute_taxes_paid(0, "QC")` → tout 0
- `_compute_taxes_paid(None, "QC")` → tout 0
- `_quarter_to_dates("2026", "Q1")` → `("2026-01-01", "2026-03-31")`
- `_quarter_to_dates("2026", "Q4")` → `("2026-10-01", "2026-12-31")`

### Intégration (`backend/tests/test_tax_report_integration.py`)

- POST `/api/expenses` avec `gst_paid_cad: 5, qst_paid_cad: 9.97, taxes_auto_computed: true` → GET retourne ces valeurs
- POST sans ces champs → tous 0, `taxes_auto_computed: false`
- `GET /api/reports/sales-tax?start&end` :
  - Pré-config : 2 invoices `paid` QC (subtotal 15000 chacune), 1 invoice `draft` (à exclure), 2 expenses avec taxes
  - Sommaire : `gst.collected = 1500, gst.paid = somme expenses, gst.net = diff`
  - Pareil pour QST
  - `hst.collected = 0` (aucune invoice ON)
  - `invoice_count: 2` (draft exclue), `expense_count: 2`
- Période vide : tous zéros, counts 0
- `GET /api/settings/company` retourne `province` (default `"QC"`)
- `PUT settings` avec `province: "ON"` → GET retourne `"ON"`
- `PUT settings` avec `province: "XX"` → ignoré, `"ON"` conservé
- `GET /api/reports/sales-tax/pdf?start&end` → 200 + Content-Type `application/pdf` + body non-vide

### Vérifications manuelles UI

| Cas | Attendu |
|---|---|
| Settings : choisir Ontario, save, reload | Province persistée |
| Nouvelle dépense : amount=113, CAD, "Calculer auto" | TVH = 13.00, TPS/TVQ = 0 |
| Settings → QC, dépense amount=114.975, "Calculer auto" | TPS=5.00, TVQ=9.98 |
| Dépense currency=USD : bouton "Calculer auto" désactivé | Tooltip explicatif visible |
| Page Rapports : sélectionner T2 2026 | Dates 2026-04-01 → 2026-06-30 |
| Générer rapport avec données existantes | 3 cartes remplies |
| Détail format ARC déplié | Tableau 4 lignes correctes |
| Cliquer "Télécharger PDF" | PDF s'ouvre dans nouvel onglet, mise en page correcte |

## Risques et limites

- **Compatibilité ascendante POST dépenses** : les anciens payloads sans les 4 nouveaux champs continuent de marcher (défauts 0/false). Aucun rejet.
- **Calcul auto pour devises étrangères** : volontairement désactivé. L'utilisateur peut entrer manuellement s'il a une dépense importée d'un fournisseur canadien facturée en USD (rare mais possible).
- **Provinces TPS-only** : pour AB/BC/MB/SK/YT/NU/NT, on ne tracke que la TPS. La PST provinciale (BC/MB/SK) n'est PAS une taxe sur la valeur ajoutée — elle n'est pas récupérable en CTI — donc volontairement hors scope.
- **Provinces avec règles complexes** : Québec a un plafond TVQ déductible sur repas (% du chiffre d'affaires). Pour v1, on calcule la TVQ payée brute sans appliquer le plafond. L'utilisateur ajuste si applicable. Notation explicite dans la doc utilisateur prévue.
- **HST déductible pour expenses ON/Maritimes** : la règle 50 % sur les repas s'applique aussi sur la TVH déductible. v1 calcule HST brute, le snapshot `deductible_percentage` de feature #3 sert juste pour le P&L (feature #5), pas pour le rapport TPS/TVQ. À noter pour feature #10 (export annuel).
- **Filtre par `issue_date`** : c'est la méthode accrual (comptabilité d'exercice), défaut au Canada. Pour les sole proprietors sous 400k qui choisissent cash-basis, le filtre serait différent (paid_date au lieu de issue_date). v1 = accrual only.
- **Multi-currency invoices** : on convertit en CAD au moment du rapport via `exchange_rate_to_cad` snapshoté. Pas de conversion temps-réel. Acceptable car l'utilisateur a snapshoté le taux au moment de la facture.
- **Pas d'arrondi cumulé** : on additionne les valeurs déjà arrondies à 2 décimales. Risque d'écart d'1 cent vs un calcul depuis le subtotal global. Acceptable pour un rapport informatif.

## Métriques de succès

- Utilisateur peut saisir `gst_paid_cad`, `qst_paid_cad`, `hst_paid_cad` sur une nouvelle dépense.
- Bouton "Calculer auto" remplit correctement les 3 champs pour les 4 régimes (QC, ON, NB/NS/PE/NL, autres).
- Settings : province modifiable, persistée.
- Page Rapports : génération sommaire en < 1 s pour un trimestre avec ~50 invoices et ~100 dépenses.
- Détail ARC et Revenu Québec montrent les lignes correctes selon la province des invoices.
- PDF téléchargé : structure correcte, données alignées avec l'affichage web.
- Aucune régression sur les endpoints expenses existants (`POST` sans nouveaux champs continue de marcher).
- Tests : tous les unitaires et intégration passent, plus de 75 tests cumulés sur le projet.
