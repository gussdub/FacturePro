# État des résultats simplifié (P&L) — Profit & Loss Report

**Date** : 2026-06-16
**Statut** : Brouillon, en attente de revue utilisateur
**Feature originale** : #5 dans la roadmap comptable

## Contexte et motivation

Avec les features #3 (catégories ARC + `deductible_amount`) et #4 (rapport TPS/TVQ + champ `province`), FacturePro contient toutes les données nécessaires pour produire un **état des résultats** (Profit & Loss) sans nouveau champ DB. C'est le rapport le plus utile au quotidien pour un travailleur autonome / TPE : "où est passé mon argent et combien j'ai gagné ?".

Le rapport doit servir deux usages :

- **Gestion** : combien j'ai dépensé brut (cash out réel), combien j'ai gagné, où va l'argent.
- **Fiscal** : combien est déductible du revenu imposable (compte tenu des règles ARC comme les repas à 50 %).

Pour rester utile pour la déclaration fiscale tout en restant intuitif au quotidien, le rapport présente les deux montants (brut + déductible) côte à côte et calcule deux nets distincts (gestion + imposable).

## Scope

**Inclus** :
- Endpoint `GET /api/reports/pnl?start&end&basis&compare` retournant une structure complète : revenus, dépenses groupées par catégorie ARC + sous-totaux par groupe, totaux, deux nets.
- Endpoint `GET /api/reports/pnl/pdf?<mêmes params>` retournant un PDF A4.
- Helper backend `_aggregate_pnl(user_id, start, end, basis)` qui centralise la logique.
- Helper `_compute_compare_period(start, end, mode)` qui calcule la fenêtre comparée (previous / prior_year / none).
- Onglet "État des résultats" dans la page Rapports existante (créée en feature #4).
- Sélecteur de période multi-mode (mensuel, trimestriel, annuel, personnalisé).
- Toggle de base (Comptabilité d'exercice / Comptabilité de caisse).
- Sélecteur de comparaison (Aucune / Période précédente / Année précédente).
- Tableau collapsible par groupe + lignes par catégorie, 2 colonnes par période (brut + déductible).

**Exclus** :
- Tracking du `paid_date` sur invoices (utile pour un vrai cash basis mais demande migration). Pour v1, le filtre cash utilise `issue_date` avec status `paid` — approximation documentée.
- Comparaison sur plus de 2 périodes (current + 1 compare seulement).
- Export CSV — différé, demande quasi-nulle.
- Breakdown des revenus par client ou produit — feature future, hors scope P&L standard.
- Dépenses sans `category_code` agrégées dans une bucket "Non classé" — pour v1, elles tombent dans le groupe "Autre" (`other`) via le fallback de `_build_expense_category_snapshot` de feature #3.
- Multi-devise sur expenses : on additionne `amount_cad` / `deductible_amount` directement (déjà en CAD).

## Décisions de design

| Question | Choix | Raison |
|---|---|---|
| Basis | Toggle accrual/cash | Couvre gestion + fiscal sans imposer un modèle |
| Détail dépenses | Par catégorie + sous-totaux par groupe | Lisibilité hiérarchique |
| Brut vs déductible | Les deux côte à côte | Comprendre la règle 50 % repas, préparer la déclaration |
| Période | Multi (mensuel/trimestre/année/custom) | P&L sert pour plusieurs cadences |
| Comparaison | Configurable (none / previous / prior_year) | Trend analysis pour ceux qui veulent |
| Export | Affichage + PDF | Cohérent avec feature #4, suffisant pour archivage et comptable |
| Data model | Aucun changement | Tout est déjà là depuis #3 et #4 |
| Paid date | `issue_date` comme proxy v1 | Évite migration. Future enhancement noté. |

## Backend

### Helpers (`server.py`)

```python
from datetime import date, timedelta

def _parse_date(s):
    """YYYY-MM-DD → date. Retourne None si invalide."""
    try:
        y, m, d = map(int, s.split("-"))
        return date(y, m, d)
    except Exception:
        return None


def _compute_compare_period(start, end, mode):
    """Retourne (start, end) de la période de comparaison, ou None si mode == 'none'.

    - mode='previous' : fenêtre de même durée juste avant start.
    - mode='prior_year' : même fenêtre, année précédente.
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
        # Naïf : soustraction de l'année. Cas limite : 29 février → 28 février.
        try:
            new_s = s.replace(year=s.year - 1)
        except ValueError:
            new_s = s.replace(year=s.year - 1, day=28)
        try:
            new_e = e.replace(year=e.year - 1)
        except ValueError:
            new_e = e.replace(year=e.year - 1, day=28)
        return (new_s.isoformat(), new_e.isoformat())
    return None


def _aggregate_pnl(user_id, start, end, basis):
    """Calcule la portion 'current' (sans comparaison) du P&L pour la période.

    Retourne dict :
    {
      "revenue": float,
      "expense_groups": [
        {"group": str, "label": str, "categories": [{"code", "label", "arc_line",
                                                    "gross": float, "deductible": float}],
         "subtotal": {"gross": float, "deductible": float}},
        ...
      ],
      "total_expenses": {"gross": float, "deductible": float},
      "net_income": {"management": float, "taxable": float},
      "invoice_count": int,
      "expense_count": int,
    }
    """
    # Revenue
    invoice_filter = {
        "user_id": user_id,
        "issue_date": {"$gte": start, "$lte": end},
    }
    if basis == "cash":
        invoice_filter["status"] = "paid"
    else:
        invoice_filter["status"] = {"$in": ["sent", "paid", "overdue"]}
    invoices = list(db.invoices.find(invoice_filter, {"_id": 0}))
    revenue = 0.0
    for inv in invoices:
        rate = inv.get("exchange_rate_to_cad", 1.0) or 1.0
        cur = inv.get("currency", "CAD")
        subtotal = float(inv.get("subtotal", 0) or 0)
        if cur != "CAD" and float(rate) > 0:
            subtotal = subtotal / float(rate)
        revenue += subtotal

    # Expenses — groupées par groupe (via EXPENSE_CATEGORIES) puis par catégorie
    expenses = list(db.expenses.find({
        "user_id": user_id,
        "expense_date": {"$gte": start, "$lte": end},
    }, {"_id": 0}))

    # Index par code
    by_code = {}  # code → {"gross": float, "deductible": float}
    for e in expenses:
        code = e.get("category_code") or "other"
        if code not in by_code:
            by_code[code] = {"gross": 0.0, "deductible": 0.0}
        by_code[code]["gross"] += float(e.get("amount_cad", 0) or 0)
        by_code[code]["deductible"] += float(e.get("deductible_amount", 0) or 0)

    # Structurer par groupe selon l'ordre de EXPENSE_CATEGORIES
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

### Endpoint principal

```python
@app.get("/api/reports/pnl")
def get_pnl_report(
    start: str = Query(...),
    end: str = Query(...),
    basis: str = Query("accrual"),
    compare: str = Query("none"),
    current_user: User = Depends(get_current_user_with_access),
):
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
        "expense_groups": [],  # filled below
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
        # Merger expense groups : pour chaque groupe/catégorie présent dans current ou previous,
        # renvoyer les deux périodes (gross/deductible).
        out["expense_groups"] = _merge_expense_groups(current["expense_groups"], previous["expense_groups"])
    else:
        # Pas de comparaison : restructurer en {current: {...}} pour cohérence
        for g in current["expense_groups"]:
            out["expense_groups"].append({
                "group": g["group"],
                "label": g["label"],
                "categories": [{**c, "current": {"gross": c["gross"], "deductible": c["deductible"]}} for c in [{"code": cat["code"], "label": cat["label"], "arc_line": cat["arc_line"], "gross": cat["gross"], "deductible": cat["deductible"]} for cat in g["categories"]]],
                "subtotal": {"current": g["subtotal"]},
            })
    return out


def _pct_delta(previous, current):
    if previous == 0:
        return 0.0 if current == 0 else 100.0
    return round((current - previous) / previous * 100, 1)


def _merge_expense_groups(current_groups, previous_groups):
    """Aligne les groupes/catégories des deux périodes en un seul tableau."""
    # Index par code de catégorie
    p_by_code = {}
    p_subtotals = {}
    for pg in previous_groups:
        p_subtotals[pg["group"]] = pg["subtotal"]
        for cat in pg["categories"]:
            p_by_code[cat["code"]] = {"gross": cat["gross"], "deductible": cat["deductible"]}

    # Liste tous les groupes apparaissant dans current OU previous
    seen_groups = set(g["group"] for g in current_groups) | set(p_subtotals.keys())
    groups_order = ["office", "marketing", "premises", "travel", "personnel", "other"]
    merged = []
    for g_key in groups_order:
        if g_key not in seen_groups:
            continue
        c_group = next((g for g in current_groups if g["group"] == g_key), None)
        p_subtotal = p_subtotals.get(g_key, {"gross": 0, "deductible": 0})
        c_subtotal = c_group["subtotal"] if c_group else {"gross": 0, "deductible": 0}

        # Catégories : union des codes apparaissant dans c_group ou previous (filtrer par groupe)
        cats_in_group = {c["code"] for c in EXPENSE_CATEGORIES if c["group"] == g_key}
        rows = []
        for cat_def in [c for c in EXPENSE_CATEGORIES if c["group"] == g_key]:
            code = cat_def["code"]
            c_cat = next((cc for cc in (c_group["categories"] if c_group else []) if cc["code"] == code), None)
            p_cat = p_by_code.get(code)
            if not c_cat and not p_cat:
                continue
            rows.append({
                "code": code,
                "label": cat_def["label_fr"],
                "arc_line": cat_def["arc_line"],
                "current": {"gross": c_cat["gross"] if c_cat else 0, "deductible": c_cat["deductible"] if c_cat else 0},
                "previous": {"gross": p_cat["gross"] if p_cat else 0, "deductible": p_cat["deductible"] if p_cat else 0},
            })
        merged.append({
            "group": g_key,
            "label": EXPENSE_CATEGORY_GROUPS[g_key],
            "categories": rows,
            "subtotal": {"current": c_subtotal, "previous": p_subtotal},
        })
    return merged
```

### Endpoint PDF

```python
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

`generate_pnl_report_pdf` réutilise les helpers ReportLab et `_take_regs`/`_reg_label_parts` de feature #2.

## Frontend

### `ReportsPage.js` — onglets en haut

Convertir la page existante (qui affiche uniquement le rapport TPS/TVQ depuis feature #4) en page à onglets :

```jsx
const [activeTab, setActiveTab] = useState("sales_tax");

return (
  <div>
    <h2>Rapports</h2>
    <div className="tabs">
      <button onClick={() => setActiveTab("sales_tax")}
        className={activeTab === "sales_tax" ? "active" : ""}>
        Rapport TPS / TVQ
      </button>
      <button onClick={() => setActiveTab("pnl")}
        className={activeTab === "pnl" ? "active" : ""}>
        État des résultats (P&L)
      </button>
    </div>
    {activeTab === "sales_tax" && <SalesTaxReportSection />}
    {activeTab === "pnl" && <PnlReportSection />}
  </div>
);
```

### Composant `PnlReportSection`

État local :
- `periodMode` : `"month"` | `"quarter"` | `"year"` | `"custom"`
- `year`, `quarter`, `month` (selon mode)
- `customStart`, `customEnd`
- `basis` : `"accrual"` | `"cash"`
- `compare` : `"none"` | `"previous"` | `"prior_year"`
- `report` : data du backend
- `loading`

Helpers JS :
- `getDates()` : retourne `{start, end}` selon mode
- `fmt(v)` : format CAD
- `pctColor(delta)` : rouge si < 0, vert si > 0, gris si = 0
- `pctArrow(delta)` : `'↑'` / `'↓'` / `''`

Génération : `axios.get('/api/reports/pnl', {params: {start, end, basis, compare}})`.

Téléchargement PDF : fetch + blob + `window.open(URL.createObjectURL(blob))`, comme dans feature #4.

UI sections :
1. Période (quickpickers + custom)
2. Base (radio Accrual/Cash)
3. Comparaison (radio None/Previous/Prior year)
4. Bouton Générer
5. Tableau collapsible (groupes `<details>` expanded par défaut)
6. Lignes de totaux + nets en bas
7. Counts + bouton PDF

### Détails UI

- Les colonnes "previous" et "Δ %" disparaissent si `compare === "none"`.
- Les lignes "Repas et représentation" affichent un badge ⚠ 50 % discret quand brut > déductible.
- `aria-live="polite"` sur le badge ⚠ et sur les totaux pour annoncer la mise à jour.
- Net income management vs taxable affichés en gras avec couleurs distinctes.

## Tests

### Unitaires (`backend/tests/test_pnl_report.py`)

- `_compute_compare_period("2026-04-01", "2026-06-30", "none")` → `None`
- `_compute_compare_period("2026-04-01", "2026-06-30", "previous")` → couple précédant directement la fenêtre
- `_compute_compare_period("2026-04-01", "2026-06-30", "prior_year")` → `("2025-04-01", "2025-06-30")`
- `_compute_compare_period("2024-02-29", "2024-02-29", "prior_year")` → gère le cas 29 février
- `_pct_delta(100, 120)` → 20.0
- `_pct_delta(0, 50)` → 100.0
- `_pct_delta(0, 0)` → 0.0
- `_pct_delta(50, 0)` → -100.0
- `_aggregate_pnl` avec données seed : revenue correct, groupes structurés, totaux et nets corrects
- `_aggregate_pnl(..., basis="cash")` n'inclut que les invoices `paid` → revenue ≤ accrual

### Intégration (`backend/tests/test_pnl_report_integration.py`)

- `GET /api/reports/pnl?start&end&basis=accrual&compare=none` retourne structure complète sans `compare_period`
- `compare=previous` ajoute `compare_period`, `revenue.previous`, `revenue.delta_pct`, et `expense_groups[i].categories[j].previous`
- `compare=prior_year` : même structure mais `compare_period` un an plus tôt
- `basis=cash` retourne `revenue.current ≤ revenue obtenu en accrual` sur même période
- Période vide (2020) → zéros, counts 0
- Valeurs invalides : `basis="xyz"` → fallback `accrual`. `compare="bad"` → fallback `none`
- `GET /api/reports/pnl/pdf?...` → 200 + `Content-Type: application/pdf` + magic bytes `%PDF`

### Vérifications manuelles UI

| Cas | Attendu |
|---|---|
| Cliquer onglet "État des résultats" | Composant P&L s'affiche |
| Mode "Ce trimestre" | Dates auto-remplies |
| Toggle Basis : Cash | Revenue diminue (factures non payées exclues) |
| Compare : Période précédente | Colonnes T-1 et Δ apparaissent |
| Compare : Année précédente | Colonnes année-1 et Δ apparaissent |
| Groupe Marketing avec dépense Repas | Badge ⚠ 50 %, écart brut/déductible visible |
| Δ rouge si négatif, vert si positif | Couleur visible |
| Bouton "Télécharger PDF" | PDF s'ouvre, structure correcte |

## Risques et limites

- **Cash basis = approximation v1** : on filtre par `issue_date` + `status=paid`. Une facture émise en mars payée en avril compte sur mars, pas avril. Conséquence : la ligne entre "le mois où j'ai facturé" et "le mois où j'ai été payé" reste floue. Future enhancement : ajouter `paid_date` sur invoices.
- **Multi-devise revenue** : on convertit `subtotal × (1/exchange_rate)` en CAD au moment du rapport, comme feature #4. Si le taux a changé entre la création de la facture et la consultation du rapport, le snapshot prévaut.
- **Dépenses sans `category_code`** : tombent dans le groupe `"other"` via le fallback de `_build_expense_category_snapshot` (feature #3). Acceptable.
- **Aucune validation des dates** : le backend ne vérifie pas que `start ≤ end`. Si inversé, la requête Mongo retourne 0 résultats — comportement graceful mais silencieux. À noter dans la doc utilisateur.
- **Comparaison sur petites valeurs** : `_pct_delta(1, 100)` = 9900 %. Visuellement extrême mais mathématiquement correct. Pas de cap.
- **Sémantique des couleurs delta naïve v1** : positif = vert, négatif = rouge, partout. Pour les revenus et le net income, c'est cohérent (hausse = bien). Pour les dépenses, c'est contre-intuitif (hausse = mal). Pour v1, on garde la règle uniforme avec un libellé clair ("Δ %"). Future enhancement : inverser la sémantique sur les lignes de dépenses, ou afficher une flèche neutre + tooltip explicatif.
- **Niveaux de récursivité** : ReportLab tronque les tableaux trop longs. Avec 18 catégories possibles, le PDF tient sur 1 page max ; au-delà, ReportLab fait du multi-page automatique.

## Métriques de succès

- L'utilisateur peut générer un P&L pour un trimestre en moins de 5 clics depuis la page Rapports.
- Le toggle Basis a un impact visible (revenue change) avec des données seed mixtes (paid + sent).
- Comparaison "période précédente" affiche des deltas cohérents (vérifiable manuellement avec des données fabriquées).
- PDF téléchargé : structure correcte, alignée avec l'affichage web.
- Aucune régression sur le rapport TPS/TVQ existant après la mise en onglets.
- Tests : > 110 backend tests cumulés sur le projet.
