# Bureau à domicile — prorata des frais de résidence, plafond et report

**Date :** 2026-09-15
**Statut :** design à approuver
**Demande d'origine :** « ajouter un réglage pour que l'électricité (Hydro-Québec) soit déduite
suivant le pourcentage que le bureau représente dans la superficie de la maison ».

---

## 1. Ce que la demande visait, et pourquoi le mécanisme demandé la casserait

La prémisse fiscale du propriétaire est **juste** : quand le bureau est au domicile, l'électricité
est bien déductible au prorata de la superficie. Le mécanisme demandé — un interrupteur par
catégorie, sur le modèle du réglage télécom, appliqué **à la saisie** — produirait en revanche un
montant faux.

### 1.1 Le prorata existe déjà, ailleurs

`HOME_OFFICE_CATEGORIES = {"rent", "utilities", "insurance"}` (`server.py:10218`) contient déjà
`utilities`, et Hydro-Québec y tombe. Quand `home_office_percentage > 0`, `_build_t2125_report`
retire ces catégories de leur ligne ARC et les place sur la **ligne 9945** au prorata.

L'électricité est donc **déjà** proratisée — mais uniquement dans le rapport T2125 annuel. Le P&L,
le grand livre et le rapport TPS/TVQ, eux, la traitent toujours à 100 %.

### 1.2 Le double prorata, mesuré

`_t2125_compute_home_office_adjustment` (`server.py:10351`) lit le champ **`gross`**. Or
`_aggregate_pnl` (`server.py:798`) calcule déjà ce `gross` **net de la portion personnelle**. Un
prorata posé à la saisie serait donc réappliqué au rapport.

Exécuté sur le code réel — facture Hydro de 200 $, bureau à 15 % :

| | Ligne 9945 déductible |
|---|---|
| Aujourd'hui | **26,09 $** |
| Avec un prorata à la saisie | **3,91 $** |

Le facteur devient 0,15² = 0,0225 au lieu de 0,15. **266 $ de déduction perdus par année**, sans
alerte, et aucun test existant ne le détecte (`tests/test_t2125_export.py:151-190` fabrique son
`flat_expenses` à la main et n'appelle jamais `_aggregate_pnl`).

C'est le piège déjà documenté pour le carnet de route (`CLAUDE.md:341,344`), mais aggravé : là, les
deux pourcentages décrivaient des réalités différentes ; ici ils décrivent **la même surface**, et
le même utilisateur les remplirait avec la même valeur.

### 1.3 On ne peut pas contourner en changeant de ligne

L'art. 18(12)a) LIR s'ouvre par « **Notwithstanding any other provision of this Act** » et vise
« an otherwise deductible amount for any part […] of a self-contained domestic establishment in
which the individual resides ». **La restriction suit la nature de la dépense, pas le numéro de
ligne du formulaire.** Le T4002 le dit en sens inverse sous la ligne 9220 : « The expenses for
utilities that are related to the business use of workspace in your home have to be claimed on
line 9945 in Part 5. »

Router l'électricité du domicile vers une dépense ordinaire ne change donc pas le traitement réel :
cela produit une **déclaration fausse**, qui calculerait une perte que la loi interdit.

---

## 2. Les règles fiscales à respecter

Chaque règle ci-dessous a été vérifiée contre une source officielle et soumise à un juge
adversarial. Les URL sont conservées pour qu'un lecteur futur puisse les recontrôler.

### 2.1 Admissibilité — deux critères ALTERNATIFS

LIR 18(12)a) : la déduction est refusée « except to the extent that the work space is either
(i) the individual's **principal place of business**, or (ii) **used exclusively** for the purpose
of earning income from business **and** used on a **regular and continuous basis for meeting
clients**, customers or patients ».

Revenu Québec reprend les deux mêmes critères (TP-80 note 9 ; IN-155 §6.27).

**Conséquence :** le réglage ne peut pas être une simple case « bureau à domicile » suivie d'un
pourcentage. L'admissibilité doit être qualifiée avant de collecter quoi que ce soit.

### 2.2 Le pourcentage — superficie, et un second prorata si usage mixte

ARC : « use a reasonable basis, such as **the area of the workspace divided by the total area of
your home** ». Le folio S4-F2-C2 confirme.

Si l'espace sert **aussi** à des fins personnelles, l'ARC exige un second prorata : « calculate how
many hours in the day you use the rooms for your business, and then divide that amount by 24
hours ». IN-155 §6.27.2 chiffre l'exemple : une pièce utilisée à 15 % à d'autres fins limite la
déduction à 85 %.

**Décision retenue :** le propriétaire a déclaré un usage **exclusivement** professionnel. Le
prorata horaire n'est donc pas collecté en v1, mais le modèle de données doit pouvoir l'accueillir
sans migration destructrice.

### 2.3 Le plafond et le report — la règle centrale

ARC : « The amount you can deduct for business-use-of-home expenses **cannot be more than your net
income from the business before you deduct these expenses**. In other words, you cannot use these
expenses to increase or create a business loss. »

LIR 18(12)b) : le montant déductible « shall not exceed the individual's income for the year from
the business ». LIR 18(12)c) répute l'excédent déductible **l'année suivante** ; le folio S4-F2-C2
précise qu'il « may be carried forward **indefinitely** ».

Le Québec est **identique** — TP-80 partie 8 le reproduit ligne par ligne : ligne 528 (report de
l'an dernier) + ligne 527 (dépenses de l'année) = ligne 530 ; ligne 532 = revenu avant ces frais ;
ligne 536 = **le moindre des deux** ; ligne 534 = le résidu **reporté à l'année suivante**.

**État actuel du code :** `_t2125_compute_home_office_adjustment` retourne
`original_total * home_pct / 100`. **Ni plafond, ni report, ni notion d'année antérieure.** C'est un
défaut existant, indépendant de la demande, et il produit un montant surévalué dès qu'une année est
déficitaire.

### 2.4 Le Québec coupe de moitié — mais épargne l'électricité

IN-155 §6.27.1 : « multipliez par 50 % le résultat obtenu s'il s'agit des dépenses suivantes :
**primes d'assurance, frais d'entretien et de réparation, intérêts sur un emprunt hypothécaire,
impôts fonciers et loyer** […]. Pour celles qui sont plutôt liées à l'utilisation du bureau
(**notamment les frais de chauffage et d'éclairage**), la limite de 50 % ne s'applique pas. »

TP-80 partie 8 matérialise la coupure : ligne 500 (électricité, eau, chauffage, Internet) → ligne
502 **sans** multiplication ; lignes 505-512 (assurance, entretien, intérêts, impôts fonciers,
loyer) → ligne 522 « **multiplié par 50 %** ».

**Conséquence directe de l'élargissement demandé :** tant qu'on ne visait que l'électricité, cette
règle était sans effet. Dès qu'on inclut **le loyer et l'assurance**, elle devient obligatoire,
sinon le calcul québécois est faux — et il l'est **déjà aujourd'hui**, puisque
`HOME_OFFICE_CATEGORIES` contient `rent` et `insurance` sans jamais appliquer les 50 %.

### 2.5 TPS/TVQ — condition d'accès PLUS STRICTE, et pas de plafond

LTA 170(1)a.1) refuse le CTI pour un espace de travail résidentiel sauf s'il est le principal lieu
d'affaires ou « used **exclusively** […] and […] on a regular and continuous basis for meeting
clients ». L'ARC chiffre : « used **90% or more** to earn income from your business ».

Revenu Québec applique la même condition et précise qu'elle est identique à celle de l'impôt.

Une fois l'accès ouvert, le crédit suit l'**utilisation commerciale** — sans plafond de revenu ni
report, contrairement à la déduction.

### 2.6 Local commercial — l'autre moitié de la demande

LIR 18(12) ne vise que « a self-contained domestic establishment in which the individual resides ».
Un local loué n'est pas la résidence : **ni la restriction, ni le plafond, ni le report, ni la
limite québécoise de 50 %** ne s'appliquent. T4002, ligne 9220 : « You can deduct expenses for
telephone and utilities, such as gas, oil, **electricity**, water, and cable, if you incurred the
expenses to earn income. » Le loyer va à la ligne 8910. Au Québec, TP-80 partie 3 a ses propres
lignes 239 (électricité, chauffage, eau) et 232 (loyer), distinctes de la partie 8.

**La moitié « édifice à bureaux » de la demande est donc fiscalement exacte** : 100 %, lignes
ordinaires, aucune règle spéciale.

---

## 3. Décisions de conception

| Décision | Choix retenu | Motif |
|---|---|---|
| Forme du réglage | **Lieu du bureau** (domicile / local commercial), pas un interrupteur par catégorie | §2.1 et §2.6 : ce sont deux régimes fiscaux entiers, pas une option par dépense. |
| Où s'applique le prorata | **Au rapport uniquement**, jamais à la saisie | §1.2 : un prorata à la saisie est compté deux fois et divise la déduction par 6,65. |
| Source du pourcentage | **Superficies saisies**, `home_office_percentage` calculé et persisté | Une seule source de vérité ; la méthode de calcul reste prouvable en cas de vérification (§2.2). |
| Portée | `rent`, `utilities`, `insurance` **et `repairs_maintenance`** | §2.4 : le T4002 et le TP-80 rattachent l'entretien au bureau à domicile. `repairs_maintenance` (ligne 8960) existe déjà mais manque à `HOME_OFFICE_CATEGORIES`. |
| Prorata horaire | **Non collecté en v1**, champ prévu | Usage déclaré exclusivement professionnel. |
| Plafond et report | **Implémentés** | §2.3 : sans eux la ligne 9945 est fausse dès une année déficitaire. |
| Limite québécoise de 50 % | **Implémentée** | §2.4 : devient obligatoire dès que `rent`/`insurance` sont inclus. |
| Sociétés par actions | **Hors périmètre v1**, comportement inchangé | Le T2125 leur est fermé (`server.py:10405`) et le rapport GIFI n'applique aucun ajustement. À traiter séparément. |

### 3.1 Ce qui n'est PAS fait, et pourquoi

- **Aucun prorata à la saisie.** Ni `personal_use_amount_cad`, ni `business_use_pct` sur ces
  catégories. La recherche a établi que ce champ est le pivot unique qui alimente simultanément le
  P&L, le grand livre, le rapport TPS/TVQ et le T2125 (`server.py:3437→3525→798/3609/3670`) : il
  n'existe **aucun levier « fiscal seulement »**. Trois effets de bord rédhibitoires :
  - le P&L afficherait 26,10 $ au lieu de 173,95 $ pour une facture de 200 $ (`server.py:798-800`
    écrase la colonne brute), faisant perdre la visibilité de gestion sur la dépense réelle ;
  - le grand livre porterait 170 $ par facture au compte **1300 « Dû par un actionnaire »**
    (`server.py:3637`), accumulant ~2 000 $/an de créance fictive — notion de surcroît **fausse**
    pour un travailleur autonome ;
  - la **falaise du 10 %** (`_recoverable_usage_frac`, `server.py:3437-3456`, seuils du Mémorandum
    TPS 8-1) annulerait tout le CTI/RTI : un bureau de 10 m² dans une maison de 130 m² fait 7,7 %,
    et le crédit tombe à zéro **silencieusement**. Vérifié par exécution.
- **Aucune migration de données.** Vérifié sur la copie de prod : 138 dépenses, dont **0**
  `utilities`, **0** `rent`, **0** `insurance`, **0** télécom, et **0** portant
  `personal_use_amount_cad`. Il n'y a rien à re-snapshoter. Le réglage ne vaudra que pour les
  rapports, donc la question ne se pose même pas — c'est une décision explicite, pas un oubli.
- **Le CTI/RTI du bureau à domicile n'est pas automatisé en v1.** §2.5 impose une condition d'accès
  (90 %) plus stricte que la déduction au revenu, et une base de calcul différente. L'automatiser
  sur la foi du seul pourcentage de superficie produirait des crédits réclamés en trop —
  c'est-à-dire de l'argent encaissé à rembourser avec intérêts. À traiter dans une v2 dédiée, avec
  sa propre qualification.

---

## 4. Conception

### 4.1 Réglages (`company_settings`)

| Champ | Type | Rôle |
|---|---|---|
| `office_location` | `"home"` \| `"commercial"` | Le régime fiscal. Défaut `"commercial"` — **fail-safe** : aucun ajustement tant que rien n'est déclaré. |
| `home_office_qualifies` | bool | Confirmation explicite d'un des deux critères de §2.1. |
| `home_office_area_sqm` | float | Superficie du bureau. |
| `home_total_area_sqm` | float | Superficie totale du domicile. |
| `home_office_percentage` | float | **Calculé** par le serveur = aire ÷ total × 100, borné 0-100. Champ existant, conservé. |
| `home_office_personal_use_pct` | float | Réservé au prorata horaire (§2.2). Défaut 0, non exposé en v1. |
| `home_office_carryforward_federal` | float | Solde reporté, fédéral (§2.3). |
| `home_office_carryforward_quebec` | float | Solde reporté, Québec — **distinct**, car la limite de 50 % fait diverger les montants (§2.4). |

`home_office_percentage` devient **dérivé** : il n'est plus saisi directement. Le serveur le
recalcule à chaque écriture des superficies, ce qui supprime la possibilité qu'il diverge de la
méthode déclarée.

**Validation :** à ajouter dans le bloc nommé de `update_settings` (`server.py:12246-12282`).
`update_settings` écrit tout le corps sans liste blanche (`server.py:12307`), donc un champ non
validé entrerait en base tel quel.

### 4.2 Deux catégories de frais, pas une

La limite québécoise de 50 % impose de scinder `HOME_OFFICE_CATEGORIES` :

```python
# Frais liés à l'UTILISATION du bureau. TP-80 l. 500-502 : PAS de limite de 50 % au Québec.
_HOME_OFFICE_OPERATING = {"utilities"}
# Frais liés à la RÉSIDENCE. TP-80 l. 505-522 : réduits de 50 % au Québec (IN-155 §6.27.1).
_HOME_OFFICE_OCCUPANCY = {"rent", "insurance", "repairs_maintenance"}
HOME_OFFICE_CATEGORIES = _HOME_OFFICE_OPERATING | _HOME_OFFICE_OCCUPANCY
```

⚠️ `utilities` est un fourre-tout (« Services publics ») qui couvre électricité, eau, gaz,
chauffage **et câble**. Le T4002 rattache le câble à la ligne 9220. Un prorata appliqué à la
catégorie entière proratiserait donc aussi le câble. **Accepté en v1** : la ligne 500 du TP-80
regroupe elle-même « électricité, eau et chauffage », et scinder une catégorie `electricity`
toucherait le plan comptable. **À documenter comme limite connue**, pas à découvrir plus tard.

### 4.3 Le calcul de la ligne 9945

```
  frais_exploitation  = Σ gross(_HOME_OFFICE_OPERATING) × pct_bureau
  frais_occupation    = Σ gross(_HOME_OFFICE_OCCUPANCY) × pct_bureau
  disponible_federal  = frais_exploitation + frais_occupation              + report_federal
  disponible_quebec   = frais_exploitation + frais_occupation × 0,50       + report_quebec
  revenu_avant_9945   = revenu − (toutes les dépenses SAUF celles de 9945)   ← la ligne 9369
  deductible          = min(disponible, max(0, revenu_avant_9945))
  report_an_prochain  = disponible − deductible                              ← jamais négatif
```

Deux calculs parallèles, deux compteurs de report. Le rapport expose les deux.

### 4.4 Défaut bloquant à corriger d'abord : la ligne 9369

`_build_t2125_report` (`server.py:10457-10481`) somme **toutes** les lignes, y compris la 9945
ajoutée à `grouped`, puis fait `net_income = revenue − total_deductible` et l'étiquette
`"net_income_line": "9369"`.

Or l'ordre du formulaire est : **9369** (revenu net *avant* ajustements) → **9945** (frais de
domicile) → **9946** (revenu net final). Le code produit donc la valeur de la **9946** sous
l'étiquette **9369**.

Ce n'est pas une erreur d'étiquette : **la 9369 est précisément le plafond** de §2.3. Tant que le
rapport ne l'expose pas séparément, aucun plafond n'est calculable. **Cette correction conditionne
la faisabilité du reste.**

### 4.5 Interface

Dans Réglages, un bloc « Bureau » remplaçant le champ `home_office_percentage` nu
(`SettingsPage.js:461-482`, aujourd'hui masqué derrière `entity_type === 'sole_proprietor'`) :

- un choix **domicile / local commercial** ;
- si domicile : une case d'admissibilité reprenant les deux critères de §2.1 en langage clair, puis
  deux champs de superficie, avec le pourcentage calculé affiché en direct ;
- si local commercial : aucun champ, et une phrase disant que les frais sont déductibles à 100 %.

Le pourcentage est **affiché, jamais saisi**. Contraste du texte ≥ 4,5:1.

---

## 5. Tests

La recherche a établi qu'aucun test existant n'attraperait le double prorata : la suite valide les
helpers sur des dicts fabriqués à la main, sans jamais créer de dépense
(`tests/test_t2125_export.py:151-190`, `test_t2125_export_integration.py` : 0 occurrence de
`category_code`).

Tests exigés, chacun devant **tomber** si on casse la règle correspondante :

1. **Bout en bout** : créer une dépense `utilities` via l'API, générer le T2125, vérifier le montant
   de la ligne 9945. C'est le test qui manque et qui rendrait le double prorata visible.
2. **Plafond** : frais > revenu → déductible = revenu, report = la différence.
3. **Report** : un report d'entrée s'ajoute aux frais de l'année.
4. **Report jamais négatif**.
5. **Limite québécoise** : `rent` réduit de 50 %, `utilities` **pas** réduit.
6. **Local commercial** : `office_location = "commercial"` → aucun ajustement, `utilities` reste sur
   la ligne 9220 à 100 %.
7. **Fail-safe** : réglages absents → aucun ajustement, comportement identique à aujourd'hui.
8. **9369 ≠ 9946** : le rapport expose les deux et la 9369 exclut bien la 9945.
9. **Non-régression** : aucune dépense ne porte `personal_use_amount_cad` après ce changement —
   c'est la garantie qu'aucun prorata n'a fui vers la saisie.

---

## 6. Ce que ce design ne résout pas

- Le **CTI/RTI** du bureau à domicile (§3.1). Condition d'accès distincte, base de calcul
  distincte, falaise du 10 % à trancher.
- Les **sociétés par actions** : le rapport GIFI n'applique aucun ajustement. Pour elles, le prorata
  à la saisie serait la seule voie **et fonctionnerait proprement** (aucun second pourcentage
  n'existe côté GIFI). Conception distincte à faire.
- Les **impôts fonciers** et **intérêts hypothécaires**, admissibles à la 9945 (§2.4) mais sans
  catégorie de dépense correspondante dans le plan comptable.
- Le **câble** proratisé avec l'électricité (§4.2).
- La **DPA** (déduction pour amortissement) sur la partie affaires de la résidence : admissible,
  mais elle fait perdre l'exemption pour résidence principale. Volontairement hors périmètre —
  c'est une décision fiscale personnelle, pas une fonction de logiciel.

---

## 7. Sources

- LIR 18(12) — `laws-lois.justice.gc.ca/eng/acts/i-3.3/section-18.html`
- LTA 170(1)a.1) — `laws-lois.justice.gc.ca/eng/acts/E-15/section-170.html`
- ARC, frais d'utilisation de la résidence — `canada.ca` (T2125, partie 5)
- Folio de l'impôt sur le revenu **S4-F2-C2** — `canada.ca`
- Guide **T4002**, ch. 3 (ligne 9220) et ch. 5 (pertes) — `canada.ca`
- Revenu Québec **TP-80** (2025-10), parties 3 et 8 — `revenuquebec.ca`
- Revenu Québec **IN-155** (2025-12), §6.27 à 6.27.3 — `revenuquebec.ca`

> Ce document établit des faits vérifiables et les rattache au code. **Il ne constitue pas un avis
> fiscal.** Les calculs livrés doivent être validés par un comptable avant qu'un abonné ne s'y fie
> pour produire une déclaration.
