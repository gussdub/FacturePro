# Dépenses nettes des taxes récupérables (feature #7.7) — spec

**Statut** : à approuver
**Date** : 2026-07-08
**Auteur** : gussdub + Claude
**Feature #** : 7.7

## Contexte

Signalé par la comptable de l'utilisateur : « le montant des taxes ne doit pas être dans le
total de la dépense ». Confirmé par recherche multi-sources ARC / Revenu Québec.

**Règle fiscale (HAUTE confiance)** — pour un **inscrit** à la TPS/TVH et à la TVQ, une dépense
d'affaires se comptabilise et se déduit au montant **NET des taxes récupérables** (CTI/RTI). La
taxe récupérable n'est pas une charge : elle est récupérée via la déclaration de taxes, pas à
l'impôt sur le revenu. Inscrire le TTC en charge = **double récupération** de la taxe → sur-estime
les dépenses, sous-estime le revenu imposable (redressement ARC/RQ).

Citation ARC, Guide T4002 (verbatim) :
> « soustrayez aux montants des dépenses d'entreprise que vous inscrivez sur le formulaire T2125 […]
> le montant des crédits de taxe sur les intrants. […] **Inscrivez le montant de la dépense nette**
> sur la ligne appropriée. »

Cas particuliers de taxe NON récupérable (restent dans le coût, TTC) :
- Entreprise **non inscrite** (petit fournisseur) → aucun CTI/RTI.
- **Repas et représentation** : seulement **50 %** de la taxe est récupérable (limite ITC repas).
- **Télécom à usage mixte** : seule la fraction affaires est récupérable, avec **seuils** (Mémorandum
  ARC 8-1, par. 24/27) : ≤ 10 % affaires → **0 crédit** ; ≥ 90 % → **100 %** ; entre → prorata.

## État actuel du code (diagnostic)

| Composant | Aujourd'hui | Correct ? |
|---|---|---|
| Grand livre normal (`_build_expense_charge_lines`) | charge nette (amount − taxes) au 5xxx, taxes au 12xx | ✅ |
| Grand livre repas | récupère **100 %** de la taxe (devrait être 50 %) | ❌ sur-réclame le CTI |
| Grand livre télécom | prorata affaires SANS seuils 10/90 | ⚠️ imprécis aux extrêmes |
| P&L (`_aggregate_pnl`) | `gross` = `amount_cad` **TTC** ; `deductible` = snapshot TTC | ❌ sur-estime les dépenses |
| T2125 / GIFI | dérivés du P&L | ❌ par transitivité |
| Rapport TPS/TVQ (`_aggregate_sales_tax`) | `_itc_frac` = prorata télécom sans seuils, PAS de limite repas 50 % | ⚠️ |
| Réconciliation GL↔P&L | absorbe l'écart TTC via `recoverable_taxes` (« écart structurel assumé ») | à simplifier |

La saisie est en **TTC + champs de taxes** (confirmé par l'utilisateur) — donc le bug affecte
réellement ses rapports de résultat et fiscaux déjà produits.

## Principe directeur

**Une seule source de vérité pour la taxe récupérable.** Un helper `_expense_recovery_frac(exp)`
et `_expense_recoverable_tax_cad(exp)` alimentent le grand livre, le P&L, et le rapport de taxes.
Impossible qu'ils divergent.

### Modèle unifié

```
category_rate   = 0.5 si category_code == "meals_entertainment" sinon 1.0
usage_frac      = _recoverable_usage_frac(exp)      # fraction affaires télécom avec seuils 10/90 ; 1.0 sinon
recovery_frac   = category_rate * usage_frac         # _expense_recovery_frac(exp)

recoverable_gst = gst_paid_cad * recovery_frac
recoverable_qst = qst_paid_cad * recovery_frac
recoverable_hst = hst_paid_cad * recovery_frac
recoverable_total = recoverable_gst + recoverable_qst + recoverable_hst   # capé à amount_cad - personal

net_business    = amount_cad - personal_use_amount_cad(0 si absent) - recoverable_total
```

`_recoverable_usage_frac(exp)` :
- Dépense non télécom (pas de `personal_use_amount_cad`) → `1.0`.
- Sinon `business_frac = (amount_cad - personal) / amount_cad` puis :
  - `business_frac <= 0.10` → `0.0`
  - `business_frac >= 0.90` → `1.0`
  - sinon → `business_frac`

**Note importante** : les seuils 10/90 s'appliquent au **crédit de taxe** (`usage_frac`), PAS à la
déductibilité du revenu. La portion affaires déductible reste la fraction réelle (via
`personal_use_amount_cad`, inchangé). Ex. télécom 8 % affaires : déduction = 8 % du coût, CTI = 0
(la taxe reste donc dans le coût déductible).

### Vérification numérique (repas 114,98 $ = 100 $ + 14,98 $ taxes QC)

- `recovery_frac` = 0,5 × 1,0 = 0,5 → `recoverable_total` = 14,98 × 0,5 = **7,49 $**
- `net_business` = 114,98 − 0 − 7,49 = **107,49 $** (charge 5xxx / P&L gross)
- `deductible` = 107,49 × 50 % (limite repas) = **53,75 $** (ligne T2125/GIFI)
- GL : Dr 5xxx 107,49 / Dr 12xx 7,49 / Cr 1000 114,98 → équilibré ✓

### Vérification (télécom 60 %, 114,98 $)

- `personal` = 45,99 ; `usage_frac` = 0,60 ; `recovery_frac` = 0,60
- `recoverable_total` = 14,98 × 0,60 = 8,99 ; `net_business` = 114,98 − 45,99 − 8,99 = **60,00 $**
- `deductible` (télécom) = net_business = **60,00 $**

## Architecture

### Backend — helpers (nouveaux, section « GL helpers »)

1. `_recoverable_usage_frac(exp) -> float` — fraction affaires avec seuils 10/90 (1.0 non-télécom).
2. `_expense_recovery_frac(exp) -> float` — `category_rate * usage_frac`. `category_rate = 0.5`
   pour `meals_entertainment`, `1.0` sinon.
3. `_expense_recoverable_tax_cad(exp) -> (gst, qst, hst)` — taxes récupérables en CAD (reconverties
   au taux de change pour une dépense en devise, comme aujourd'hui), chacune `× recovery_frac`,
   le total capé à `amount_cad - personal`.
4. `_expense_net_business_cad(exp) -> float` — `amount_cad - personal - Σ recoverable` (le chiffre
   qui va au 5xxx et au P&L). Clamp `>= 0`.

### Backend — Volet A : grand livre refactoré

`_build_expense_charge_lines` réécrit pour dériver ses lignes des helpers ci-dessus :
- Dr 5xxx = `_expense_net_business_cad(exp)` (si > 0)
- Dr 1200/1210/1220 = taxes récupérables de `_expense_recoverable_tax_cad(exp)` (si > 0)
- Dr offset actionnaire = `personal` (si > 0, télécom)
- Cr 1000/2000 = `amount_cad`
- Conserver TOUS les garde-fous existants : équilibre exact partie double, plafonnement des taxes,
  clamp `personal ∈ [0, amount]`, compte offset de bilan (jamais 5xxx/12xx). L'équilibre
  `Σ débits == crédit` reste garanti par construction (net = amount − personal − taxes).

**Changement de comportement GL** : repas (taxe récupérable 100 % → 50 %) et télécom aux seuils
(≤10 % / ≥90 %). Les dépenses normales sont **inchangées** (recovery_frac = 1.0 → net identique).

### Backend — Volet A : P&L net

`_aggregate_pnl`, par dépense (remplace les lignes actuelles `gross_val`/`deductible`) :
```python
gross_val = _expense_net_business_cad(e)
if e.get("personal_use_amount_cad") is not None:   # télécom : portion affaires 100 % déductible
    ded_val = gross_val
else:
    pct = float(e.get("deductible_percentage", 100) or 100)
    ded_val = round(gross_val * pct / 100, 2)
by_code[code]["gross"] += gross_val
by_code[code]["deductible"] += ded_val
```
Corrige automatiquement P&L, T2125 (`deductible`), GIFI (`deductible`).

### Backend — Volet B : rapport TPS/TVQ

`_aggregate_sales_tax` : remplacer `_itc_frac(e)` par `_expense_recovery_frac(e)` sur les trois
sommes `gst_paid`/`qst_paid`/`hst_paid`. Un seul point : seuils 10/90 (télécom) + limite 50 %
(repas) appliqués au crédit déclaré. (Le helper `_itc_frac` local est supprimé au profit du
helper partagé.)

### Backend — Volet A : réconciliation

`/api/ledger/reconciliation` : après le fix, `expenses_pnl_gross == expenses_gl_net` (les deux
nets). Mettre à jour :
- `expenses_diff = expenses_pnl_gross - expenses_gl_net` (≈ 0).
- `recoverable_taxes` reste calculé et exposé, mais comme **ligne informative** (plus dans
  l'équation d'équilibre). Mettre à jour le commentaire « écart structurel assumé » (supprimé).
- `balanced` sur `|expenses_diff| < 0.02` inchangé.

### Backend — Volet D : migration idempotente `migrate_expense_net_tax_v1()`

Au startup, deux effets, idempotents :
1. **Re-snapshot `deductible_amount`** de chaque dépense pour refléter le net (via
   `_expense_net_business_cad` + la règle de déductibilité), pour que la colonne « déductible »
   affichée corresponde aux rapports. Idempotent : ne réécrit que si la valeur diffère de > 0,01.
2. **Re-post GL des dépenses affectées** (catégorie `meals_entertainment` OU télécom avec
   `personal_use_amount_cad` défini) via `_repost_expense_gl(org_id, user_id, id, exp)` — déjà
   idempotent (contre-passe l'ancienne écriture vivante + poste la nouvelle, anti-trou). Ne touche
   PAS les dépenses normales (GL déjà correct). Gaté sur `autopost_enabled` par org.

Aucune modification de `amount_cad` ni des champs de taxes saisis — seuls les dérivés se recalculent.

### Frontend — Volet C : saisie taxes télécom

`ExpensesPage.js` — vérifier que le bouton « Calculer auto » (feature #4) appelle bien le calcul
de taxes (`_compute_taxes_paid` côté backend, ou son équivalent front) pour les catégories
`telecom_cell` / `telecom_internet`. Si un garde exclut le télécom, le retirer. Objectif : que le
CTI proratisé ne soit pas 0 faute de taxe saisie. Ajouter un libellé d'aide « Le montant est TTC ;
les taxes récupérables sont sorties du coût déductible. »

## Testing

Nouveau `backend/tests/test_expense_net_tax.py` :

1. **Helper recovery_frac** : normal → 1.0 ; repas → 0.5 ; télécom 60 % → 0.6 ; télécom 8 % → 0.0
   (seuil) ; télécom 95 % → 1.0 (seuil).
2. **net_business** : office 114,98 → 100,00 ; repas 114,98 → 107,49 ; télécom 60 % → 60,00.
3. **P&L net** : créer 1 office + 1 repas (TTC + taxes), vérifier `gross`/`deductible` nets dans
   `GET /api/reports/pnl` (office deductible 100,00 ; repas deductible 53,75).
4. **T2125 + GIFI** reflètent le net (déductible repas 53,75).
5. **Rapport TPS/TVQ** : CTI repas = 50 % de la taxe ; télécom 8 % → CTI 0.
6. **GL équilibré** : `_build_expense_charge_lines` d'un repas → Σ débits == crédit, 12xx = 7,49,
   5xxx = 107,49.
7. **Migration idempotente** : dépense repas legacy (GL 100 % taxe) → après migration, GL re-posté
   (12xx = 50 %) ; 2ᵉ passage = no-op.
8. **Réconciliation** : `expenses_diff ≈ 0` après le fix (P&L net == GL net).
9. **Non-régression** : dépense normale CAD → net inchangé vs comportement GL actuel.

Revue adversariale opus **obligatoire** avant push (équilibre partie double, capping, arrondis,
double-application de fractions, cohérence GL/P&L/taxes).

## Files

**Backend** (`backend/server.py`) :
- Nouveaux helpers `_recoverable_usage_frac`, `_expense_recovery_frac`,
  `_expense_recoverable_tax_cad`, `_expense_net_business_cad`.
- `_build_expense_charge_lines` refactoré sur ces helpers.
- `_aggregate_pnl` — gross/deductible nets.
- `_aggregate_sales_tax` — `_itc_frac` remplacé par `_expense_recovery_frac`.
- `ledger_reconciliation` — équation simplifiée + commentaire.
- `migrate_expense_net_tax_v1()` + appel au startup.
- `backend/tests/test_expense_net_tax.py` (nouveau).

**Frontend** :
- `frontend/src/pages/ExpensesPage.js` — « Calculer auto » couvre le télécom + libellé d'aide.

**Docs** : `CLAUDE.md` — changelog feature #7.7.

## Rollout

Un commit backend + frontend, push prod (confirmer avant). Migration idempotente au redémarrage
Render. **Impact attendu et voulu** : les rapports P&L/T2125/GIFI affichent des dépenses plus
BASSES (nettes de taxes) → revenu net plus HAUT ; les écritures de repas récupèrent 50 % du CTI au
lieu de 100 %. À communiquer à l'utilisateur (vérifier ses totaux après déploiement).

## Rejected / hors périmètre

- **Détection automatique inscrit vs non-inscrit** : inutile — les champs de taxe saisis encodent
  déjà la récupérabilité (un non-inscrit ne saisit pas de taxe récupérable → net = TTC
  automatiquement). Aucun flag « inscrit » requis.
- **Méthode rapide de comptabilité** (taxe non récupérable) : rare, hors périmètre v1.
- **Immobilisations (règle 50 % tout-ou-rien)** : ne concerne pas les dépenses courantes visées ici.
