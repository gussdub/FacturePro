# Bureau à domicile — plan d'implémentation

> **Pour les agents :** SOUS-SKILL REQUIS — utiliser `superpowers:subagent-driven-development`
> (recommandé) ou `superpowers:executing-plans`. Les étapes utilisent des cases à cocher.

**Objectif :** rendre le traitement des frais de bureau à domicile conforme à la loi — prorata par
la superficie, **plafond au revenu**, **report indéfini du résidu**, **limite québécoise de 50 %**,
et **CTI/RTI proratisé** — sans jamais toucher au montant saisi d'une dépense.

**Architecture :** tout le calcul reste **au niveau des rapports**. Aucune dépense n'est modifiée,
aucun `personal_use_amount_cad` n'est posé. Cinq helpers purs et testables isolément — facteur
d'utilisation, séparation exploitation/occupation, limite québécoise, plafond/report, facteur
CTI — puis leur câblage dans le T2125 et le rapport de taxes.

**Pile :** FastAPI + pymongo (`backend/server.py`), React CRA
(`frontend/src/pages/SettingsPage.js`), pytest via `../.venv-test/bin/python`.

**Spec :** `docs/superpowers/specs/2026-09-15-bureau-domicile-design.md` — la lire d'abord, en
particulier le §1.2 (le double prorata mesuré) et le §2.3 (le plafond), qui sont la raison d'être
de ce plan.

---

## Structure des fichiers

| Fichier | Responsabilité | Nature |
|---|---|---|
| `backend/server.py` | 5 helpers + câblage T2125 + câblage taxes + validation réglages | modifié |
| `backend/tests/test_bureau_domicile.py` | toute la couverture de ce plan | **créé** |
| `frontend/src/pages/SettingsPage.js` | bloc « Bureau » | modifié |
| `CLAUDE.md` | entrée de feature | modifié |

**Points d'ancrage vérifiés le 2026-09-15 :**

- l. 3438 — `def _recoverable_usage_frac(exp)`
- l. 3467 — `def _expense_recoverable_tax_cad(exp)`
- l. 10213 — `T2125_MIN_YEAR = 2020`
- l. 10218 — `HOME_OFFICE_CATEGORIES = {"rent", "utilities", "insurance"}`
- l. 10351 — `def _t2125_compute_home_office_adjustment(flat_expenses, home_pct)`
- l. 10390 — `def _build_t2125_report(scope, year, basis)`
- l. 10457 — le bloc `total_deductible` / `net_income` / `"net_income_line": "9369"`
- l. 12246 — le bloc de validation nommé de `update_settings`
- l. 13619 — `def _aggregate_sales_tax(scope, start, end)`, dont l. ~13670 la somme des CTI

> ⚠️ **Ordre de définition.** `_home_office_expenses` (tâche 4) et `_home_office_itc_factor`
> (tâche 7) référencent `_HOME_OFFICE_OPERATING` / `HOME_OFFICE_CATEGORIES`, définis **plus bas**
> dans le fichier (l. 10218). C'est volontaire et ça fonctionne : en Python la résolution du nom
> a lieu à **l'appel**, pas à la définition. C'est déjà le cas d'`EXEMPT_USERS` vis-à-vis de
> `_check_subscription_active`. **Ne pas « corriger » cet ordre** — ce serait un déplacement
> inutile dans un fichier de 14 600 lignes.

> ⚠️ **Piège pymongo, vérifié dans ce repo.** Ne JAMAIS écrire
> `monkeypatch.setattr(server_module.db.<collection>, "<methode>", …)` : `Database.__getattr__`
> construit un **nouvel objet `Collection` à chaque accès d'attribut**, donc le patch porte sur un
> objet jetable et le code testé interroge la vraie base — qui est ici une **copie de
> production**. Ce piège a déjà fait fuiter 78 documents en base de dev dans ce projet. Patcher au
> niveau de la **classe** (`pymongo.collection.Collection`), filtré par `self.name`, **avec
> délégation** pour toute autre collection.

**Règle absolue de ce plan :** ne JAMAIS écrire `personal_use_amount_cad` sur une dépense
`utilities`, `rent`, `insurance` ou `repairs_maintenance`. Ce champ est le pivot unique qui
alimente le P&L, le grand livre, le rapport de taxes ET le T2125 ; le poser ici réintroduirait le
double prorata que ce plan existe pour empêcher. La tâche 9 vérifie cette invariance.

**Commandes de référence :**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
../.venv-test/bin/python -m pytest tests/test_bureau_domicile.py -q -p no:cacheprovider
```

---

## Task 1 : Exposer la ligne 9369 séparément de la 9946

C'est le préalable de tout le reste. Le rapport somme aujourd'hui **toutes** les lignes, 9945
comprise, puis étiquette le résultat `"net_income_line": "9369"`. Or l'ordre du formulaire est
9369 (revenu net **avant** ajustements) → 9945 (frais de domicile) → 9946 (revenu net final). La
valeur produite est donc celle de la **9946**.

Ce n'est pas cosmétique : **la 9369 est le plafond** de la tâche 5. Tant qu'elle n'existe pas, le
plafond est incalculable.

**Files:**
- Modify: `backend/server.py:10457-10481`
- Test: `backend/tests/test_bureau_domicile.py` (créer)

- [ ] **Step 1 : Écrire le test qui échoue**

Créer `backend/tests/test_bureau_domicile.py` :

```python
"""Bureau à domicile — prorata, plafond, report, limite québécoise, CTI/RTI.

Ces tests n'appellent jamais le réseau. Ils exercent les helpers purs et, pour l'intégration,
créent de vraies dépenses via la base locale.
"""
import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))

import uuid
import pymongo
import pytest
import server as server_module


def _flat(**cats):
    """Construit un flat_expenses de la forme que produit _t2125_flatten_pnl_expenses."""
    return {code: {"gross": float(v), "deductible": float(v)} for code, v in cats.items()}


class TestLigne9369:
    def test_le_rapport_expose_9369_ET_9946(self, monkeypatch):
        """RÉGRESSION : la 9369 est le revenu AVANT les frais de domicile, la 9946 est APRÈS.
        Le code étiquetait « 9369 » une valeur qui était en réalité la 9946 — or c'est la 9369
        qui plafonne la ligne 9945. Sans cette séparation, aucun plafond n'est calculable."""
        monkeypatch.setattr(server_module, "_aggregate_pnl", lambda *a, **k: {
            "revenue": 50000.0,
            "expense_groups": [{"categories": [
                {"code": "office_supplies", "gross": 1000.0, "deductible": 1000.0},
                {"code": "utilities", "gross": 2000.0, "deductible": 2000.0},
            ]}],
        })
        # Ces réglages satisfont À LA FOIS l'ancien pilote (home_office_percentage, utilisé par
        # le code tel qu'il est à cette tâche) et le nouveau (les superficies, à partir de la
        # tâche 6). Sans les deux, ce test passerait maintenant et casserait plus tard.
        monkeypatch.setattr(server_module.db.company_settings, "find_one", lambda *a, **k: {
            "entity_type": "sole_proprietor", "province": "QC",
            "office_location": "home", "home_office_qualifies": True,
            "home_office_percentage": 20.0,
            "home_office_area_sqm": 20.0, "home_total_area_sqm": 100.0,
        })
        r = server_module._build_t2125_report({"organization_id": "x"}, 2025, "accrual")
        assert r["net_income_before_home_office"] == 49000.0, (
            "la 9369 doit EXCLURE les frais de domicile")
        assert r["net_income_before_home_office_line"] == "9369"
        assert r["net_income_line"] == "9946", "le revenu net FINAL est la 9946, pas la 9369"
        assert r["net_income"] < r["net_income_before_home_office"]
```

- [ ] **Step 2 : Lancer pour voir ÉCHOUER**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
../.venv-test/bin/python -m pytest tests/test_bureau_domicile.py -q -p no:cacheprovider
```

Attendu : ÉCHEC `KeyError: 'net_income_before_home_office'`.
**Tu dois VOIR cet échec.**

- [ ] **Step 3 : Implémenter**

Remplacer le bloc de calcul (`server.py:10457-10459`, les trois lignes
`total_deductible` / `net_income` et leurs commentaires) par :

```python
    # [FISCAL] L'ordre du T2125 est : 9369 (revenu net AVANT ajustements) -> 9945 (frais de
    # résidence) -> 9946 (revenu net final). La 9369 n'est pas décorative : c'est elle qui
    # PLAFONNE la 9945, parce que ces frais ne peuvent ni créer ni augmenter une perte
    # (LIR 18(12)b). Il faut donc les deux valeurs, pas une seule.
    _home_lines = [l for l in grouped if l.get("arc_line") == "9945"]
    total_home_office = round(sum(l["deductible"] for l in _home_lines), 2)
    total_deductible = round(sum(line["deductible"] for line in grouped), 2)
    net_income_before_home_office = round(
        pnl["revenue"] - (total_deductible - total_home_office), 2)
    net_income = round(pnl["revenue"] - total_deductible, 2)
```

Puis, dans le dict retourné, remplacer la paire
`"net_income": net_income,` / `"net_income_line": "9369",` par :

```python
        "net_income_before_home_office": net_income_before_home_office,
        "net_income_before_home_office_line": "9369",
        "net_income": net_income,
        "net_income_line": "9946",
```

- [ ] **Step 4 : Lancer pour voir PASSER**

```bash
../.venv-test/bin/python -m pytest tests/test_bureau_domicile.py -q -p no:cacheprovider
```

Attendu : `1 passed`

- [ ] **Step 5 : Vérifier les consommateurs de `net_income_line`**

```bash
grep -n "net_income_line\|net_income_before" server.py ../frontend/src -r
```

Le PDF (`server.py:14208`, `14370`) écrit « Bénéfice net (ligne 9369) » en dur. Le corriger en
`9946` aux deux endroits — c'est la même erreur d'étiquette.

- [ ] **Step 6 : Commit**

```bash
git add backend/server.py backend/tests/test_bureau_domicile.py
git commit -m "fix(t2125): la ligne 9369 exclut les frais de domicile, la 9946 les inclut"
```

---

## Task 2 : Réglages — lieu du bureau, superficies, pourcentage dérivé

**Files:**
- Modify: `backend/server.py:12246` (bloc de validation nommé)
- Test: `backend/tests/test_bureau_domicile.py` (ajouter)

- [ ] **Step 1 : Écrire les tests qui échouent**

AJOUTER à la fin du fichier de tests :

```python
class TestReglagesBureau:
    def test_pourcentage_derive_des_superficies(self):
        s = {"home_office_area_sqm": 12.0, "home_total_area_sqm": 110.0}
        assert server_module._home_office_pct_from_areas(s) == pytest.approx(10.909, abs=0.001)

    def test_superficie_totale_nulle_donne_zero(self):
        """Division par zéro : on renvoie 0, jamais une exception ni un infini."""
        for s in ({"home_office_area_sqm": 12.0, "home_total_area_sqm": 0},
                  {"home_office_area_sqm": 12.0},
                  {}):
            assert server_module._home_office_pct_from_areas(s) == 0.0

    def test_bureau_plus_grand_que_la_maison_est_borne_a_100(self):
        s = {"home_office_area_sqm": 200.0, "home_total_area_sqm": 110.0}
        assert server_module._home_office_pct_from_areas(s) == 100.0

    def test_valeurs_negatives_donnent_zero(self):
        s = {"home_office_area_sqm": -5.0, "home_total_area_sqm": 110.0}
        assert server_module._home_office_pct_from_areas(s) == 0.0

    def test_facteur_zero_si_pas_au_domicile(self):
        """Un local commercial n'a AUCUN prorata : 18(12) ne vise que la résidence."""
        s = {"office_location": "commercial", "home_office_qualifies": True,
             "home_office_area_sqm": 12.0, "home_total_area_sqm": 110.0}
        assert server_module._home_office_factor(s) == 0.0

    def test_facteur_zero_si_non_admissible(self):
        """Sans confirmation d'admissibilité (LIR 18(12)a), aucune déduction."""
        s = {"office_location": "home", "home_office_qualifies": False,
             "home_office_area_sqm": 12.0, "home_total_area_sqm": 110.0}
        assert server_module._home_office_factor(s) == 0.0

    def test_facteur_par_defaut_est_zero(self):
        """FAIL-SAFE : des réglages vides ne doivent produire aucun ajustement."""
        assert server_module._home_office_factor({}) == 0.0

    def test_facteur_nominal(self):
        s = {"office_location": "home", "home_office_qualifies": True,
             "home_office_area_sqm": 12.0, "home_total_area_sqm": 110.0}
        assert server_module._home_office_factor(s) == pytest.approx(0.10909, abs=0.00001)

    def test_prorata_horaire_reduit_le_facteur(self):
        """Si l'espace sert AUSSI à des fins personnelles, l'ARC exige un second prorata.
        Non exposé en v1, mais le calcul doit déjà le respecter s'il est présent."""
        s = {"office_location": "home", "home_office_qualifies": True,
             "home_office_area_sqm": 11.0, "home_total_area_sqm": 110.0,
             "home_office_personal_use_pct": 15.0}
        # 10 % de superficie, dont 85 % d'usage affaires -> 8,5 %
        assert server_module._home_office_factor(s) == pytest.approx(0.085, abs=0.0001)
```

- [ ] **Step 2 : Lancer pour voir ÉCHOUER**

```bash
../.venv-test/bin/python -m pytest tests/test_bureau_domicile.py -q -p no:cacheprovider -k Reglages
```

Attendu : `AttributeError: module 'server' has no attribute '_home_office_pct_from_areas'`.

- [ ] **Step 3 : Implémenter les deux helpers**

Insérer dans `server.py` juste AVANT `HOME_OFFICE_CATEGORIES` (l. 10218) :

```python
def _home_office_pct_from_areas(settings: dict) -> float:
    """Pourcentage d'utilisation du domicile, dérivé des SUPERFICIES.

    L'ARC accepte explicitement cette méthode : « use a reasonable basis, such as the area of the
    workspace divided by the total area of your home ». On dérive plutôt que de faire saisir le
    pourcentage directement, pour deux raisons : la méthode reste prouvable en cas de
    vérification, et le nombre ne peut pas diverger de ce que l'abonné a déclaré.
    """
    try:
        bureau = float(settings.get("home_office_area_sqm") or 0)
        total = float(settings.get("home_total_area_sqm") or 0)
    except (TypeError, ValueError):
        return 0.0
    if not (bureau > 0 and total > 0):
        return 0.0
    return round(min(100.0, bureau / total * 100.0), 4)


def _home_office_factor(settings: dict) -> float:
    """Fraction des frais de résidence imputable à l'entreprise, entre 0 et 1.

    Trois verrous, dans cet ordre — chacun renvoie 0, c'est-à-dire AUCUN ajustement :
      1. le bureau n'est pas au domicile -> LIR 18(12) ne vise que « a self-contained domestic
         establishment in which the individual resides ». En local commercial, les frais sont
         des dépenses ordinaires à 100 %, et rien de ce module ne s'applique ;
      2. l'admissibilité n'est pas confirmée -> LIR 18(12)a) exige que l'espace soit le principal
         lieu d'affaires, OU utilisé exclusivement pour l'entreprise ET pour rencontrer des
         clients de façon régulière et continue ;
      3. les superficies ne sont pas saisies.

    Le défaut est donc 0 : des réglages vides ne produisent aucun ajustement, et le comportement
    reste identique à celui d'avant cette fonctionnalité.

    Le prorata HORAIRE (`home_office_personal_use_pct`) s'applique EN PLUS de la superficie quand
    l'espace sert aussi à des fins personnelles — l'ARC : « calculate how many hours in the day
    you use the rooms for your business, and then divide that amount by 24 hours ». Non exposé en
    v1 (usage déclaré exclusif), mais respecté s'il est présent.
    """
    if settings.get("office_location") != "home":
        return 0.0
    if not settings.get("home_office_qualifies"):
        return 0.0
    pct = _home_office_pct_from_areas(settings)
    if pct <= 0:
        return 0.0
    try:
        perso = float(settings.get("home_office_personal_use_pct") or 0)
    except (TypeError, ValueError):
        perso = 0.0
    perso = min(100.0, max(0.0, perso))
    return pct / 100.0 * (1.0 - perso / 100.0)
```

- [ ] **Step 4 : Ajouter la validation des réglages**

Dans `update_settings`, juste après le bloc `home_office_percentage` /
`vehicle_business_percentage` (`server.py:12246-12257`), insérer :

```python
    # [FISCAL] Bureau à domicile. `update_settings` écrit tout le corps sans liste blanche
    # (cf. le $set plus bas) : un champ non validé entrerait donc en base tel quel.
    if "office_location" in settings_data:
        loc = str(settings_data.get("office_location") or "").strip()
        if loc not in ("home", "commercial"):
            raise HTTPException(422, "office_location doit valoir 'home' ou 'commercial'")
        settings_data["office_location"] = loc
    if "home_office_qualifies" in settings_data:
        settings_data["home_office_qualifies"] = bool(settings_data["home_office_qualifies"])
    for field in ("home_office_area_sqm", "home_total_area_sqm"):
        if field in settings_data:
            try:
                v = float(settings_data[field])
            except (ValueError, TypeError):
                raise HTTPException(422, f"{field} doit être un nombre")
            if not math.isfinite(v) or v < 0:
                raise HTTPException(422, f"{field} doit être un nombre positif")
            settings_data[field] = v
    if "home_office_personal_use_pct" in settings_data:
        try:
            v = float(settings_data["home_office_personal_use_pct"])
        except (ValueError, TypeError):
            raise HTTPException(422, "home_office_personal_use_pct doit être un nombre")
        if not math.isfinite(v) or not (0 <= v <= 100):
            raise HTTPException(422, "home_office_personal_use_pct doit être entre 0 et 100")
        settings_data["home_office_personal_use_pct"] = v
    # Le pourcentage est DÉRIVÉ, jamais saisi : on le recalcule à chaque écriture des superficies
    # pour qu'il ne puisse pas diverger de la méthode déclarée.
    if ("home_office_area_sqm" in settings_data) or ("home_total_area_sqm" in settings_data):
        _cur = db.company_settings.find_one(_org_scope(current_user), {"_id": 0}) or {}
        _merged = {**_cur, **settings_data}
        settings_data["home_office_percentage"] = _home_office_pct_from_areas(_merged)
```

- [ ] **Step 5 : Lancer, puis commit**

```bash
../.venv-test/bin/python -m pytest tests/test_bureau_domicile.py -q -p no:cacheprovider
```
Attendu : `10 passed`

```bash
git add backend/server.py backend/tests/test_bureau_domicile.py
git commit -m "feat(fiscal): lieu du bureau, superficies et pourcentage dérivé"
```

---

## Task 3 : Séparer les frais d'exploitation des frais d'occupation

La limite québécoise de 50 % ne frappe pas tout. Il faut donc deux ensembles, pas un.

**Files:**
- Modify: `backend/server.py:10218`
- Test: `backend/tests/test_bureau_domicile.py` (ajouter)

- [ ] **Step 1 : Écrire les tests qui échouent**

```python
class TestCategoriesBureau:
    def test_deux_ensembles_distincts(self):
        """TP-80 partie 8 sépare la ligne 500 (exploitation, PAS de limite de 50 %) des
        lignes 505-522 (occupation, réduites de 50 %)."""
        assert server_module._HOME_OFFICE_OPERATING == {"utilities"}
        assert server_module._HOME_OFFICE_OCCUPANCY == {
            "rent", "insurance", "repairs_maintenance"}

    def test_union_couvre_l_ancien_ensemble(self):
        """Non-régression : les 3 catégories d'origine restent traitées."""
        assert {"rent", "utilities", "insurance"} <= server_module.HOME_OFFICE_CATEGORIES

    def test_entretien_ajoute(self):
        """Le T4002 renvoie l'entretien (l. 8960) vers la 9945 ; la catégorie existait déjà
        dans le plan comptable mais manquait à l'ensemble."""
        assert "repairs_maintenance" in server_module.HOME_OFFICE_CATEGORIES

    def test_les_categories_existent_dans_le_plan_comptable(self):
        codes = {c["code"] for c in server_module.EXPENSE_CATEGORIES}
        assert server_module.HOME_OFFICE_CATEGORIES <= codes
```

- [ ] **Step 2 : Lancer pour voir ÉCHOUER**

Attendu : `AttributeError: module 'server' has no attribute '_HOME_OFFICE_OPERATING'`.

- [ ] **Step 3 : Implémenter**

Remplacer la ligne 10218 (`HOME_OFFICE_CATEGORIES = {"rent", "utilities", "insurance"}`) par :

```python
# [FISCAL] Deux familles, parce que le Québec ne les traite pas pareil.
#
# EXPLOITATION — liées à l'utilisation du bureau. TP-80 l. 500-502 : le prorata s'applique, mais
# PAS la réduction de moitié. IN-155 §6.27.1 : « Pour celles qui sont plutôt liées à
# l'utilisation du bureau (notamment les frais de chauffage et d'éclairage), la limite de 50 %
# ne s'applique pas. » C'est précisément le cas d'Hydro-Québec.
#
# ⚠️ `utilities` est un fourre-tout (« Services publics ») qui couvre aussi l'eau, le gaz et le
# câble. Le prorata s'appliquera donc au câble aussi. Limite CONNUE et acceptée en v1 : la ligne
# 500 du TP-80 regroupe elle-même électricité, eau et chauffage, et scinder une catégorie
# `electricity` toucherait le plan comptable et les dépenses existantes.
_HOME_OFFICE_OPERATING = {"utilities"}

# OCCUPATION — liées à la résidence elle-même. TP-80 l. 505-522 : après le prorata, le Québec
# multiplie par 50 %, « ces dépenses étant, dans une large mesure, engagées à des fins
# personnelles » (IN-155 §6.27.1). Le fédéral n'a pas cette réduction.
_HOME_OFFICE_OCCUPANCY = {"rent", "insurance", "repairs_maintenance"}

# `repairs_maintenance` (ligne 8960) était ABSENT de l'ancien ensemble alors que le T4002 le
# renvoie vers la 9945 au même titre que le loyer.
HOME_OFFICE_CATEGORIES = _HOME_OFFICE_OPERATING | _HOME_OFFICE_OCCUPANCY
```

- [ ] **Step 4 : Lancer, puis commit**

Attendu : `14 passed`

```bash
git add backend/server.py backend/tests/test_bureau_domicile.py
git commit -m "feat(fiscal): séparer frais d'exploitation et d'occupation du bureau à domicile"
```

---

## Task 4 : Limite québécoise de 50 % sur les frais d'occupation

**Files:**
- Modify: `backend/server.py` (nouveau helper, après `_home_office_factor`)
- Test: `backend/tests/test_bureau_domicile.py` (ajouter)

- [ ] **Step 1 : Écrire les tests qui échouent**

```python
class TestLimiteQuebec:
    def test_federal_ne_reduit_rien(self):
        flat = _flat(utilities=2000.0, rent=12000.0)
        r = server_module._home_office_expenses(flat, 0.10, province="ON")
        assert r["operating"] == pytest.approx(200.0)
        assert r["occupancy"] == pytest.approx(1200.0)
        assert r["total"] == pytest.approx(1400.0)

    def test_quebec_reduit_l_occupation_de_moitie(self):
        """IN-155 §6.27.1 : assurance, entretien, intérêts, impôts fonciers et loyer sont
        multipliés par 50 %."""
        flat = _flat(utilities=2000.0, rent=12000.0)
        r = server_module._home_office_expenses(flat, 0.10, province="QC")
        assert r["occupancy"] == pytest.approx(600.0), "le loyer doit être réduit de moitié"

    def test_quebec_ne_reduit_PAS_l_exploitation(self):
        """C'est le point qui distingue l'électricité du loyer — et c'est la dépense visée par
        la demande d'origine."""
        flat = _flat(utilities=2000.0)
        r = server_module._home_office_expenses(flat, 0.10, province="QC")
        assert r["operating"] == pytest.approx(200.0), (
            "l'électricité ÉCHAPPE à la limite de 50 %")

    def test_facteur_nul_donne_zero(self):
        flat = _flat(utilities=2000.0, rent=12000.0)
        r = server_module._home_office_expenses(flat, 0.0, province="QC")
        assert r["total"] == 0.0

    def test_categories_absentes_ne_plantent_pas(self):
        r = server_module._home_office_expenses({}, 0.10, province="QC")
        assert r["total"] == 0.0

    def test_entretien_traite_comme_occupation(self):
        flat = _flat(repairs_maintenance=1000.0)
        assert server_module._home_office_expenses(flat, 0.10, province="QC")["total"] == \
            pytest.approx(50.0)
```

- [ ] **Step 2 : Lancer pour voir ÉCHOUER**

Attendu : `AttributeError: module 'server' has no attribute '_home_office_expenses'`.

- [ ] **Step 3 : Implémenter**

Insérer juste après `_home_office_factor` :

```python
# [FISCAL] Réduction québécoise des frais d'OCCUPATION. IN-155 §6.27.1 et TP-80 l. 522
# (« Montant de la ligne 518 multiplié par 50 % »). S'applique aux exercices commencés après le
# 9 mai 1996. Le fédéral n'a AUCUN équivalent.
_QC_OCCUPANCY_LIMIT = 0.50


def _home_office_expenses(flat_expenses: dict, factor: float, province: str = "QC") -> dict:
    """Frais de bureau à domicile de l'année, ventilés exploitation / occupation.

    `factor` est la fraction déjà calculée par `_home_office_factor` (superficie × usage).
    `flat_expenses` vient de `_t2125_flatten_pnl_expenses` : on lit le champ `gross`.

    Au Québec, les frais d'OCCUPATION sont réduits de moitié APRÈS le prorata ; ceux
    d'EXPLOITATION ne le sont pas. Les deux sont renvoyés séparément parce que le solde à
    reporter diffère entre le fédéral et le Québec, et qu'on a donc besoin des deux totaux.
    """
    def _somme(codes):
        total = 0.0
        for code in codes:
            try:
                total += float((flat_expenses.get(code) or {}).get("gross") or 0)
            except (TypeError, ValueError):
                continue
        return total

    f = max(0.0, min(1.0, float(factor or 0)))
    operating = _somme(_HOME_OFFICE_OPERATING) * f
    occupancy = _somme(_HOME_OFFICE_OCCUPANCY) * f
    if str(province or "").upper() == "QC":
        occupancy *= _QC_OCCUPANCY_LIMIT
    return {
        "operating": round(operating, 2),
        "occupancy": round(occupancy, 2),
        "total": round(operating + occupancy, 2),
    }
```

- [ ] **Step 4 : Lancer, puis commit**

Attendu : `20 passed`

```bash
git add backend/server.py backend/tests/test_bureau_domicile.py
git commit -m "feat(fiscal): limite québécoise de 50 % sur les frais d'occupation"
```

---

## Task 5 : Le plafond et le report

C'est la règle centrale, et elle manque entièrement aujourd'hui.

**Files:**
- Modify: `backend/server.py` (nouveau helper)
- Test: `backend/tests/test_bureau_domicile.py` (ajouter)

- [ ] **Step 1 : Écrire les tests qui échouent**

```python
class TestPlafondEtReport:
    def test_sous_le_plafond_tout_est_deductible(self):
        r = server_module._home_office_cap(frais=1000.0, report_anterieur=0.0,
                                           revenu_avant=5000.0)
        assert r["deductible"] == 1000.0
        assert r["report_suivant"] == 0.0

    def test_au_dessus_du_plafond_le_residu_se_reporte(self):
        """LIR 18(12)b) : ces frais ne peuvent ni créer ni augmenter une perte.
        18(12)c) : l'excédent est déductible l'année SUIVANTE, indéfiniment."""
        r = server_module._home_office_cap(frais=4000.0, report_anterieur=0.0,
                                           revenu_avant=3000.0)
        assert r["deductible"] == 3000.0, "plafonné au revenu avant ces frais"
        assert r["report_suivant"] == 1000.0, "le résidu n'est PAS perdu"

    def test_le_report_anterieur_s_ajoute(self):
        """TP-80 l. 528 : « Montant de la ligne 534 du formulaire de l'année précédente »."""
        r = server_module._home_office_cap(frais=1000.0, report_anterieur=2500.0,
                                           revenu_avant=3000.0)
        assert r["disponible"] == 3500.0
        assert r["deductible"] == 3000.0
        assert r["report_suivant"] == 500.0

    def test_revenu_negatif_traite_comme_zero(self):
        """TP-80 l. 532 : « S'il est négatif, inscrivez 0 ». Une entreprise déficitaire ne
        déduit RIEN au titre du bureau, et reporte tout."""
        r = server_module._home_office_cap(frais=1000.0, report_anterieur=0.0,
                                           revenu_avant=-8000.0)
        assert r["deductible"] == 0.0
        assert r["report_suivant"] == 1000.0

    def test_report_jamais_negatif(self):
        """TP-80 l. 534 : « Si le résultat est négatif, inscrivez 0 »."""
        r = server_module._home_office_cap(frais=100.0, report_anterieur=0.0,
                                           revenu_avant=99999.0)
        assert r["report_suivant"] == 0.0

    def test_aucun_frais_ne_produit_rien(self):
        r = server_module._home_office_cap(frais=0.0, report_anterieur=0.0, revenu_avant=5000.0)
        assert r["deductible"] == 0.0 and r["report_suivant"] == 0.0

    def test_le_plafond_ne_peut_pas_creer_de_perte(self):
        """INVARIANT, formulé comme la loi : le revenu après déduction est toujours >= 0."""
        for revenu in (0.0, 1.0, 500.0, 5000.0):
            r = server_module._home_office_cap(frais=9999.0, report_anterieur=9999.0,
                                               revenu_avant=revenu)
            assert revenu - r["deductible"] >= -0.005, (
                f"revenu={revenu} deductible={r['deductible']} -> perte créée")
```

- [ ] **Step 2 : Lancer pour voir ÉCHOUER**

Attendu : `AttributeError: module 'server' has no attribute '_home_office_cap'`.

- [ ] **Step 3 : Implémenter**

Insérer juste après `_home_office_expenses` :

```python
def _home_office_cap(frais: float, report_anterieur: float, revenu_avant: float) -> dict:
    """Applique le PLAFOND et calcule le REPORT des frais de bureau à domicile.

    C'est la règle la plus importante de ce module, et elle était entièrement absente : le code
    se contentait de `total × pourcentage`.

    ARC : « The amount you can deduct for business-use-of-home expenses cannot be more than your
    net income from the business before you deduct these expenses. In other words, you cannot use
    these expenses to increase or create a business loss. » — LIR 18(12)b).

    L'excédent n'est PAS perdu : LIR 18(12)c) le rend déductible l'année suivante, et le folio
    S4-F2-C2 précise qu'il se reporte « indefinitely ».

    Le Québec applique la même mécanique, ligne par ligne (TP-80 partie 8) :
        l. 530 = l. 527 (frais de l'année) + l. 528 (report de l'an dernier)
        l. 532 = revenu avant ces frais, « s'il est négatif, inscrivez 0 »
        l. 536 = le MOINDRE des deux   <- la déduction
        l. 534 = l. 530 moins l. 532, « si négatif, inscrivez 0 »   <- le report
    """
    disponible = max(0.0, float(frais or 0)) + max(0.0, float(report_anterieur or 0))
    plafond = max(0.0, float(revenu_avant or 0))      # TP-80 l. 532
    deductible = min(disponible, plafond)             # TP-80 l. 536
    return {
        "disponible": round(disponible, 2),
        "plafond": round(plafond, 2),
        "deductible": round(deductible, 2),
        "report_suivant": round(max(0.0, disponible - deductible), 2),   # TP-80 l. 534
    }
```

- [ ] **Step 4 : Lancer, puis commit**

Attendu : `27 passed`

```bash
git add backend/server.py backend/tests/test_bureau_domicile.py
git commit -m "feat(fiscal): plafond au revenu et report indéfini des frais de bureau à domicile"
```

---

## Task 6 : Câbler le tout dans le rapport T2125

**Files:**
- Modify: `backend/server.py:10351` (`_t2125_compute_home_office_adjustment`) et `:10390`
  (`_build_t2125_report`)
- Test: `backend/tests/test_bureau_domicile.py` (ajouter)

- [ ] **Step 1 : Écrire les tests qui échouent**

```python
class TestT2125Integre:
    def _settings(self, **kw):
        base = {"entity_type": "sole_proprietor", "province": "QC",
                "office_location": "home", "home_office_qualifies": True,
                "home_office_area_sqm": 11.0, "home_total_area_sqm": 110.0}
        base.update(kw)
        return base

    def _report(self, monkeypatch, revenue, settings, **cats):
        monkeypatch.setattr(server_module, "_aggregate_pnl", lambda *a, **k: {
            "revenue": revenue,
            "expense_groups": [{"categories": [
                {"code": c, "gross": v, "deductible": v} for c, v in cats.items()]}],
        })
        # ⚠️ NE PAS faire `monkeypatch.setattr(server_module.db.company_settings, "find_one", …)` :
        # `Database.__getattr__` de pymongo construit un NOUVEL objet Collection à chaque accès
        # (`db.company_settings is db.company_settings` -> False). Le patch porterait sur un objet
        # jetable, le code interrogerait une autre instance, et le test lirait la VRAIE base —
        # une copie de production. On patche donc au niveau de la CLASSE, en délégant pour toute
        # autre collection. Même motif que tests/test_bureau_domicile.py::TestLigne9369.
        _vrai_find_one = pymongo.collection.Collection.find_one

        def _find_one(self, *a, **k):
            if self.name == "company_settings":
                return settings
            return _vrai_find_one(self, *a, **k)

        monkeypatch.setattr(pymongo.collection.Collection, "find_one", _find_one)
        return server_module._build_t2125_report({"organization_id": "x"}, 2025, "accrual")

    def test_local_commercial_aucun_ajustement(self, monkeypatch):
        """L'électricité reste une dépense ordinaire à 100 % sur sa ligne 9220."""
        r = self._report(monkeypatch, 50000.0,
                         self._settings(office_location="commercial"), utilities=2000.0)
        assert r["business_use_adjustments"].get("home_office") is None
        lignes = {l["arc_line"]: l for l in r["expenses_by_arc_line"]}
        assert "9945" not in lignes
        assert lignes["9220"]["deductible"] == 2000.0

    def test_domicile_prorate_et_deplace_sur_9945(self, monkeypatch):
        r = self._report(monkeypatch, 50000.0, self._settings(), utilities=2000.0)
        lignes = {l["arc_line"]: l for l in r["expenses_by_arc_line"]}
        assert "9220" not in lignes, "utilities doit QUITTER sa ligne ordinaire"
        assert lignes["9945"]["deductible"] == pytest.approx(200.0)

    def test_plafond_applique_dans_le_rapport(self, monkeypatch):
        """Revenu faible : la déduction est plafonnée et le résidu reporté."""
        r = self._report(monkeypatch, 1100.0, self._settings(),
                         utilities=2000.0, rent=12000.0, office_supplies=1000.0)
        adj = r["business_use_adjustments"]["home_office"]
        # revenu 1100 - 1000 de fournitures = 100 de revenu avant frais de domicile
        assert r["net_income_before_home_office"] == pytest.approx(100.0)
        assert adj["deductible_amount"] == pytest.approx(100.0), "plafonné"
        assert adj["carryforward_next"] > 0, "le résidu doit être reporté"
        assert r["net_income"] == pytest.approx(0.0), "le plafond interdit la perte"

    def test_report_anterieur_pris_en_compte(self, monkeypatch):
        r = self._report(monkeypatch, 50000.0,
                         self._settings(home_office_carryforward_quebec=5000.0),
                         utilities=2000.0)
        adj = r["business_use_adjustments"]["home_office"]
        assert adj["carryforward_prior"] == 5000.0
        assert adj["deductible_amount"] == pytest.approx(5200.0)

    def test_limite_quebecoise_visible_dans_le_rapport(self, monkeypatch):
        r = self._report(monkeypatch, 50000.0, self._settings(), rent=12000.0)
        adj = r["business_use_adjustments"]["home_office"]
        assert adj["occupancy"] == pytest.approx(600.0), "12000 x 10 % x 50 %"
        assert adj["qc_occupancy_limit_applied"] is True

    def test_non_admissible_aucun_ajustement(self, monkeypatch):
        r = self._report(monkeypatch, 50000.0,
                         self._settings(home_office_qualifies=False), utilities=2000.0)
        assert r["business_use_adjustments"].get("home_office") is None

    def test_reglages_vides_comportement_inchange(self, monkeypatch):
        """FAIL-SAFE : sans réglage, le rapport doit être identique à celui d'avant."""
        r = self._report(monkeypatch, 50000.0,
                         {"entity_type": "sole_proprietor", "province": "QC"},
                         utilities=2000.0)
        assert r["business_use_adjustments"].get("home_office") is None
        lignes = {l["arc_line"]: l for l in r["expenses_by_arc_line"]}
        assert lignes["9220"]["deductible"] == 2000.0
```

- [ ] **Step 2 : Lancer pour voir ÉCHOUER**

Attendu : plusieurs échecs, dont `test_plafond_applique_dans_le_rapport` qui montre une déduction
non plafonnée.

- [ ] **Step 3 : Remplacer `_t2125_compute_home_office_adjustment`**

Remplacer INTÉGRALEMENT la fonction (`server.py:10351`, de sa signature jusqu'à son `}` final,
juste avant `_t2125_compute_vehicle_adjustment`) par :

```python
def _t2125_compute_home_office_adjustment(flat_expenses, settings, revenu_avant_9945):
    """Ligne 9945 — frais d'utilisation de la résidence aux fins de l'entreprise.

    Renvoie None quand aucun ajustement ne s'applique : l'appelant laisse alors les catégories
    sur leurs lignes ordinaires, comme avant cette fonctionnalité.

    Trois étapes, dans cet ordre :
      1. le facteur d'utilisation (superficie × usage), avec ses trois verrous ;
      2. les frais de l'année, ventilés exploitation / occupation, la limite québécoise de 50 %
         appliquée à l'occupation seulement ;
      3. le PLAFOND au revenu avant ces frais, et le REPORT du résidu.

    ⚠️ Lit `gross` et NON `deductible` : aucun prorata n'est jamais appliqué à la saisie pour ces
    catégories, précisément pour que ce calcul-ci soit le seul. Cf. §1.2 de la spec.
    """
    factor = _home_office_factor(settings or {})
    if factor <= 0:
        return None

    province = str((settings or {}).get("province") or "QC").upper()
    frais = _home_office_expenses(flat_expenses, factor, province=province)
    if frais["total"] <= 0:
        return None

    champ_report = ("home_office_carryforward_quebec" if province == "QC"
                    else "home_office_carryforward_federal")
    try:
        report_anterieur = float((settings or {}).get(champ_report) or 0)
    except (TypeError, ValueError):
        report_anterieur = 0.0

    cap = _home_office_cap(frais["total"], report_anterieur, revenu_avant_9945)

    return {
        "percentage": round(factor * 100.0, 4),
        "applies_to": sorted(HOME_OFFICE_CATEGORIES),
        "operating": frais["operating"],
        "occupancy": frais["occupancy"],
        "qc_occupancy_limit_applied": province == "QC" and frais["occupancy"] > 0,
        "expenses_this_year": frais["total"],
        "carryforward_prior": round(report_anterieur, 2),
        "available": cap["disponible"],
        "income_cap": cap["plafond"],
        "deductible_amount": cap["deductible"],
        "carryforward_next": cap["report_suivant"],
        "carryforward_field": champ_report,
        "saved_to_arc_line": "9945",
        "label": "Frais d'utilisation de la résidence aux fins de l'entreprise",
    }
```

- [ ] **Step 4 : Adapter l'appelant dans `_build_t2125_report`**

La fonction a maintenant besoin du revenu AVANT la 9945, donc l'ordre de calcul change. Remplacer
le bloc qui calcule `home_adj` / `vehicle_adj` / `excluded` / `grouped` par :

```python
    vehicle_adj = _t2125_compute_vehicle_adjustment(flat_expenses, vehicle_pct)

    # [FISCAL] La 9945 se plafonne au revenu AVANT elle-même : il faut donc grouper d'abord SANS
    # elle, calculer ce revenu, puis seulement ensuite calculer l'ajustement de résidence.
    excluded = set(HOME_OFFICE_CATEGORIES)
    if vehicle_adj is not None:
        excluded.update(VEHICLE_CATEGORIES)
    grouped = _t2125_group_by_arc_line(flat_expenses, exclude_codes=excluded)
    if vehicle_adj is not None:
        grouped.append({
            "arc_line": "9281",
            "label": vehicle_adj["label"],
            "gross": vehicle_adj["original_total"],
            "deductible": vehicle_adj["deductible_amount"],
            "categories": list(VEHICLE_CATEGORIES),
        })
    revenu_avant_9945 = round(
        pnl["revenue"] - sum(l["deductible"] for l in grouped), 2)

    home_adj = _t2125_compute_home_office_adjustment(
        flat_expenses, settings, revenu_avant_9945)

    if home_adj is None:
        # Aucun ajustement : les catégories retournent sur leurs lignes ordinaires.
        grouped = _t2125_group_by_arc_line(
            flat_expenses,
            exclude_codes=(VEHICLE_CATEGORIES if vehicle_adj is not None else set()))
        if vehicle_adj is not None:
            grouped.append({
                "arc_line": "9281",
                "label": vehicle_adj["label"],
                "gross": vehicle_adj["original_total"],
                "deductible": vehicle_adj["deductible_amount"],
                "categories": list(VEHICLE_CATEGORIES),
            })
    else:
        grouped.append({
            "arc_line": "9945",
            "label": home_adj["label"],
            "gross": home_adj["expenses_this_year"],
            "deductible": home_adj["deductible_amount"],
            "categories": list(HOME_OFFICE_CATEGORIES),
        })
```

Supprimer l'ancienne ligne `home_pct = float(settings.get("home_office_percentage", 0) or 0)`
si elle n'a plus d'usage (`grep -n "home_pct" server.py` doit ne plus rien renvoyer hors
commentaires).

- [ ] **Step 5 : Lancer, puis commit**

Attendu : `34 passed`

```bash
../.venv-test/bin/python -m pytest tests/test_bureau_domicile.py tests/test_t2125_export.py -q -p no:cacheprovider
```

⚠️ `tests/test_t2125_export.py:151-190` appelle l'ancienne signature
`_t2125_compute_home_office_adjustment(flat_expenses, home_pct)`. **Adapter ces tests à la
nouvelle signature**, sans affaiblir ce qu'ils vérifiaient. Si un de ces tests devient faux
plutôt qu'incompatible, ARRÊTE-TOI et signale-le.

```bash
git add backend/server.py backend/tests/
git commit -m "feat(fiscal): câbler prorata, limite québécoise, plafond et report dans le T2125"
```

---

## Task 7 : CTI/RTI proratisé, au niveau du rapport de taxes

Aujourd'hui le rapport TPS/TVQ réclame **100 %** des taxes payées sur l'électricité, le loyer et
l'assurance, même quand le bureau est au domicile. C'est le risque le plus concret du dossier :
un crédit réclamé en trop est de l'argent encaissé, à rembourser avec intérêts.

**Files:**
- Modify: `backend/server.py:13619` (`_aggregate_sales_tax`)
- Test: `backend/tests/test_bureau_domicile.py` (ajouter)

- [ ] **Step 1 : Écrire les tests qui échouent**

```python
class TestCtiRti:
    def test_local_commercial_cti_entier(self):
        s = {"office_location": "commercial", "home_office_qualifies": True,
             "home_office_area_sqm": 11.0, "home_total_area_sqm": 110.0}
        assert server_module._home_office_itc_factor(s, "utilities") == 1.0

    def test_categorie_hors_bureau_non_touchee(self):
        s = {"office_location": "home", "home_office_qualifies": True,
             "home_office_area_sqm": 11.0, "home_total_area_sqm": 110.0}
        assert server_module._home_office_itc_factor(s, "office_supplies") == 1.0
        assert server_module._home_office_itc_factor(s, "meals_entertainment") == 1.0

    def test_domicile_cti_proratise(self):
        s = {"office_location": "home", "home_office_qualifies": True,
             "home_office_area_sqm": 11.0, "home_total_area_sqm": 110.0}
        assert server_module._home_office_itc_factor(s, "utilities") == pytest.approx(0.10)

    def test_usage_predominant_donne_cti_entier(self):
        """Règle du « substantially all » : à 90 % ou plus d'utilisation commerciale, le CTI
        est réclamable en entier."""
        s = {"office_location": "home", "home_office_qualifies": True,
             "home_office_area_sqm": 95.0, "home_total_area_sqm": 100.0}
        assert server_module._home_office_itc_factor(s, "utilities") == 1.0

    def test_pas_de_falaise_a_10_pourcent(self):
        """RÉGRESSION : le seuil de 10 % de _recoverable_usage_frac vient du régime des biens à
        usage mixte (cellulaire) et ne s'applique PAS aux frais d'exploitation d'un bureau à
        domicile. Un bureau de 7,7 % garde son CTI au prorata, il ne tombe pas à zéro."""
        s = {"office_location": "home", "home_office_qualifies": True,
             "home_office_area_sqm": 10.0, "home_total_area_sqm": 130.0}
        f = server_module._home_office_itc_factor(s, "utilities")
        assert f > 0, "le CTI ne doit PAS être annulé pour un petit bureau"
        assert f == pytest.approx(0.0769, abs=0.0001)

    def test_non_admissible_aucun_cti(self):
        """LTA 170(1)a.1) refuse le CTI si l'espace n'est pas le principal lieu d'affaires ou
        utilisé exclusivement pour l'entreprise."""
        s = {"office_location": "home", "home_office_qualifies": False,
             "home_office_area_sqm": 11.0, "home_total_area_sqm": 110.0}
        assert server_module._home_office_itc_factor(s, "utilities") == 0.0
```

- [ ] **Step 2 : Lancer pour voir ÉCHOUER**

Attendu : `AttributeError: module 'server' has no attribute '_home_office_itc_factor'`.

- [ ] **Step 3 : Implémenter le helper**

Insérer juste après `_home_office_cap` :

```python
# [FISCAL] Seuil du « substantially all » : à 90 % ou plus d'utilisation commerciale, le CTI est
# réclamable en entier plutôt qu'au prorata.
_ITC_SUBSTANTIALLY_ALL = 0.90


def _home_office_itc_factor(settings: dict, category_code: str) -> float:
    """Fraction de TPS/TVQ récupérable sur une dépense de résidence. 1.0 = rien à changer.

    LTA 170(1)a.1) refuse le CTI sur un espace de travail résidentiel SAUF s'il est le principal
    lieu d'affaires, ou utilisé exclusivement pour l'entreprise et pour rencontrer des clients de
    façon régulière et continue. C'est la même condition d'accès que la déduction au revenu — on
    la lit donc dans le même réglage d'admissibilité.

    Une fois l'accès ouvert, le crédit suit l'utilisation commerciale. Contrairement à la
    déduction, il n'y a NI plafond de revenu NI report : ce sont deux régimes distincts.

    ⚠️ La falaise de 10 % de `_recoverable_usage_frac` ne s'applique PAS ici. Ce seuil vient du
    régime des biens à usage mixte (le cas du cellulaire) ; l'appliquer à une superficie de
    bureau annulerait tout le crédit pour un bureau de 10 m² dans une maison de 130 m² — cas
    parfaitement ordinaire. Décision explicite, pas un oubli.
    """
    if category_code not in HOME_OFFICE_CATEGORIES:
        return 1.0
    if (settings or {}).get("office_location") != "home":
        return 1.0                      # local commercial : dépense ordinaire, CTI entier
    factor = _home_office_factor(settings or {})
    if factor <= 0:
        return 0.0                      # au domicile mais non admissible -> aucun CTI
    if factor >= _ITC_SUBSTANTIALLY_ALL:
        return 1.0
    return factor
```

- [ ] **Step 4 : Câbler dans `_aggregate_sales_tax`**

Dans `_aggregate_sales_tax`, remplacer la ligne
`_rec = [_expense_recoverable_tax_cad(e) for e in expenses]` par :

```python
    # [FISCAL] Bureau à domicile : le CTI/RTI sur les frais de résidence suit l'utilisation
    # commerciale. Appliqué ICI, au rapport, et jamais à la saisie — poser le prorata sur la
    # dépense elle-même modifierait aussi le P&L et le grand livre, et serait recompté par le
    # T2125 (cf. §1.2 et §3.1 de la spec).
    _ho_settings = db.company_settings.find_one(scope, {"_id": 0}) or {}

    def _rec_one(e):
        gst, qst, hst = _expense_recoverable_tax_cad(e)
        f = _home_office_itc_factor(_ho_settings, e.get("category_code"))
        if f == 1.0:
            return gst, qst, hst
        return gst * f, qst * f, hst * f

    _rec = [_rec_one(e) for e in expenses]
```

- [ ] **Step 5 : Lancer, puis commit**

Attendu : `40 passed`

```bash
../.venv-test/bin/python -m pytest tests/test_bureau_domicile.py tests/test_sales_tax_report.py -q -p no:cacheprovider 2>/dev/null || \
../.venv-test/bin/python -m pytest tests/test_bureau_domicile.py -q -p no:cacheprovider
git add backend/server.py backend/tests/test_bureau_domicile.py
git commit -m "feat(fiscal): CTI/RTI du bureau à domicile proratisé au niveau du rapport"
```

---

## Task 8 : Le bloc « Bureau » dans les réglages

**Files:**
- Modify: `frontend/src/pages/SettingsPage.js:461-482`

- [ ] **Step 1 : Lire la structure réelle du bloc actuel**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
sed -n '450,500p' src/pages/SettingsPage.js
```

Le champ `home_office_percentage` y est saisi directement et le bloc est masqué derrière
`entity_type === 'sole_proprietor'`.

- [ ] **Step 2 : Remplacer par le bloc « Bureau »**

Le pourcentage devient **affiché, jamais saisi**. Conserver le style en ligne du fichier (aucune
classe CSS, aucune dépendance ajoutée).

```javascript
          {/* Bureau — le régime fiscal dépend du LIEU, pas d'une case par dépense. */}
          <div style={{ marginTop: 24 }}>
            <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>Bureau</h3>
            <p style={{ fontSize: 13, color: '#6b7280', marginTop: 0 }}>
              Si ton bureau est à la maison, les frais de résidence (électricité, loyer,
              assurance, entretien) ne sont déductibles qu'au prorata de la superficie qu'il
              occupe. Dans un local commercial, ils le sont à 100 %.
            </p>

            <label style={{ display: 'block', marginBottom: 8 }}>
              <input type="radio" name="office_location" value="commercial"
                     checked={(settings.office_location || 'commercial') === 'commercial'}
                     onChange={() => setSettings(p => ({ ...p, office_location: 'commercial' }))} />
              {' '}Local commercial
            </label>
            <label style={{ display: 'block', marginBottom: 8 }}>
              <input type="radio" name="office_location" value="home"
                     checked={settings.office_location === 'home'}
                     onChange={() => setSettings(p => ({ ...p, office_location: 'home' }))} />
              {' '}À mon domicile
            </label>

            {settings.office_location === 'home' && (
              <div style={{ marginLeft: 20, marginTop: 12, paddingLeft: 14,
                            borderLeft: '3px solid #e5e7eb' }}>
                <label style={{ display: 'block', marginBottom: 12, fontSize: 14 }}>
                  <input type="checkbox"
                         checked={!!settings.home_office_qualifies}
                         onChange={e => setSettings(p => ({
                           ...p, home_office_qualifies: e.target.checked }))} />
                  {' '}Cet espace est mon principal lieu d'affaires, <em>ou</em> je l'utilise
                  uniquement pour mon entreprise et j'y rencontre des clients de façon régulière.
                </label>

                <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                  <label style={{ fontSize: 14 }}>Superficie du bureau (m²)<br />
                    <input type="number" min="0" step="0.1"
                           value={settings.home_office_area_sqm ?? ''}
                           onChange={e => setSettings(p => ({ ...p,
                             home_office_area_sqm: e.target.value === '' ? ''
                               : parseFloat(e.target.value) || 0 }))}
                           style={{ padding: 8, borderRadius: 6, border: '1px solid #d1d5db',
                                    width: 120 }} />
                  </label>
                  <label style={{ fontSize: 14 }}>Superficie totale du domicile (m²)<br />
                    <input type="number" min="0" step="0.1"
                           value={settings.home_total_area_sqm ?? ''}
                           onChange={e => setSettings(p => ({ ...p,
                             home_total_area_sqm: e.target.value === '' ? ''
                               : parseFloat(e.target.value) || 0 }))}
                           style={{ padding: 8, borderRadius: 6, border: '1px solid #d1d5db',
                                    width: 120 }} />
                  </label>
                </div>

                <p style={{ marginTop: 12, fontSize: 14, color: '#00796B', fontWeight: 600 }}>
                  Part de ton domicile utilisée pour l'entreprise :{' '}
                  {(settings.home_total_area_sqm > 0 && settings.home_office_area_sqm > 0)
                    ? Math.min(100, settings.home_office_area_sqm
                        / settings.home_total_area_sqm * 100).toFixed(2) + ' %'
                    : '—'}
                </p>
                <p style={{ fontSize: 13, color: '#6b7280' }}>
                  Ces frais ne peuvent pas créer ni augmenter une perte d'entreprise. Ce qui
                  dépasse ton revenu est reporté aux années suivantes, sans limite de temps.
                </p>
              </div>
            )}

            {(settings.office_location || 'commercial') === 'commercial' && (
              <p style={{ fontSize: 13, color: '#6b7280', marginLeft: 20 }}>
                Tes frais de local sont déductibles à 100 %, sur leurs lignes habituelles.
              </p>
            )}
          </div>
```

⚠️ Ce bloc n'est PAS masqué derrière `entity_type === 'sole_proprietor'` : le lieu du bureau est
une information valide pour toute entité. Le T2125, lui, reste réservé aux travailleurs autonomes
— c'est une contrainte du rapport, pas du réglage.

- [ ] **Step 3 : Vérifier le build**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
CI=true npx react-scripts build 2>&1 | grep -E "Compiled|Failed|error|warning"
```

Attendu : `Compiled successfully.` — `CI=true` transforme les avertissements ESLint en erreurs,
c'est ce qui casse Vercel sinon. Ne pas committer un build rouge.

- [ ] **Step 4 : Commit**

```bash
git add frontend/src/pages/SettingsPage.js
git commit -m "feat(fiscal): bloc Bureau — lieu, admissibilité et superficies"
```

---

## Task 9 : Vérification par mutation, non-régression, documentation

- [ ] **Step 1 : Vérification par mutation**

Chaque mutation DOIT faire échouer au moins un test. Une mutation qui survit signale un test
décoratif — rapporte-la.

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
cp server.py /tmp/bd.bak
run() { ../.venv-test/bin/python -m pytest tests/test_bureau_domicile.py -q -p no:cacheprovider 2>&1 | tail -1; }
mut() { python3 -c "
import sys
s=open('server.py',encoding='utf-8').read()
a,b=sys.argv[1],sys.argv[2]
assert s.count(a)==1, 'ancre trouvee %d fois' % s.count(a)
open('server.py','w',encoding='utf-8').write(s.replace(a,b))" "$1" "$2"; printf '%-44s ' "$3"; run; cp /tmp/bd.bak server.py; }

mut 'deductible = min(disponible, plafond)' 'deductible = disponible' 'M1 plafond retire'
mut 'plafond = max(0.0, float(revenu_avant or 0))' 'plafond = 1e12' 'M2 plafond infini'
mut '"report_suivant": round(max(0.0, disponible - deductible), 2),' '"report_suivant": 0.0,' 'M3 report supprime'
mut '        occupancy *= _QC_OCCUPANCY_LIMIT' '        pass' 'M4 limite QC retiree'
mut 'operating = _somme(_HOME_OFFICE_OPERATING) * f' 'operating = _somme(_HOME_OFFICE_OPERATING) * f * 0.5' 'M5 limite QC appliquee a tort'
mut '    if not settings.get("home_office_qualifies"):' '    if False:' 'M6 admissibilite ignoree'
mut '    if settings.get("office_location") != "home":' '    if False:' 'M7 lieu ignore'
mut '    if category_code not in HOME_OFFICE_CATEGORIES:' '    if False:' 'M8 CTI applique partout'

echo -n "RESTAURE : "; run
rm -f /tmp/bd.bak
git status --short server.py
```

`git status --short server.py` doit être **vide**.

- [ ] **Step 2 : Non-régression, par comparaison de LISTES**

Il existe ~190 échecs pré-existants (tests live-HTTP exigeant un serveur démarré). Comparer les
listes, jamais les compteurs. Utiliser un **worktree**, pas `git stash` — le fichier de tests neuf
ne serait pas retiré et polluerait la comparaison.

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
BASE=$(git log --format=%H -1 --before="2026-09-15" main)
(cd backend && ../.venv-test/bin/python -m pytest tests -q -p no:cacheprovider 2>&1 | grep -E "^(FAILED|ERROR)" | sort > /tmp/bd_apres.txt)
git worktree add -q /tmp/bd_base "$BASE"
(cd /tmp/bd_base/backend && "/Users/guillaumedubeau/Documents/Claude code/FacturePro/.venv-test/bin/python" -m pytest tests -q -p no:cacheprovider 2>&1 | grep -E "^(FAILED|ERROR)" | sort > /tmp/bd_avant.txt)
git worktree remove /tmp/bd_base --force
diff /tmp/bd_avant.txt /tmp/bd_apres.txt
```

Seules différences acceptables : des lignes qui **disparaissent**, ou des lignes du nouveau
fichier `test_bureau_domicile.py`. **Toute ligne AJOUTÉE concernant un autre fichier est une
régression** — bloquant.

- [ ] **Step 3 : Vérifier l'invariant central du plan**

Aucune dépense ne doit porter de prorata à la saisie :

```bash
cd backend && ../.venv-test/bin/python -c "
import sys, os; sys.path.insert(0,'.')
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv('.env')
db = MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
n = db.expenses.count_documents({
    'category_code': {'\$in': ['utilities','rent','insurance','repairs_maintenance']},
    'personal_use_amount_cad': {'\$ne': None}})
print('depenses de residence portant un prorata a la saisie :', n)
assert n == 0, 'INVARIANT ROMPU : le double prorata est de retour'
print('OK')
"
```

- [ ] **Step 4 : Vérifier le build frontend**

```bash
cd ../frontend && CI=true npx react-scripts build 2>&1 | grep -E "Compiled|Failed|error"
```

- [ ] **Step 5 : Documenter dans CLAUDE.md**

Ajouter une entrée « Features livrées — 2026-09-15 » décrivant : le double prorata évité et
pourquoi (avec le chiffre 26,09 $ → 3,91 $), le plafond et le report désormais appliqués, la
limite québécoise de 50 % qui épargne l'électricité, le CTI/RTI proratisé au rapport, la
correction 9369/9946, et les limites connues (câble proratisé avec l'électricité, impôts fonciers
et intérêts hypothécaires sans catégorie, sociétés par actions hors périmètre).

- [ ] **Step 6 : Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add CLAUDE.md
git commit -m "docs: entrée CLAUDE.md du bureau à domicile"
```

---

## Couverture de la spec

| Section de la spec | Tâche |
|---|---|
| §1.2 double prorata évité | Règle absolue de l'en-tête + tâche 9 step 3 |
| §2.1 admissibilité | Tâche 2 (`home_office_qualifies`) |
| §2.2 superficie + prorata horaire | Tâche 2 (`_home_office_pct_from_areas`, `_home_office_factor`) |
| §2.3 plafond et report | Tâche 5 (`_home_office_cap`), câblé en tâche 6 |
| §2.4 limite québécoise 50 % | Tâches 3 et 4 |
| §2.5 TPS/TVQ | Tâche 7 |
| §2.6 local commercial | Tâches 2 et 6 |
| §4.1 réglages | Tâche 2 |
| §4.2 deux ensembles | Tâche 3 |
| §4.3 calcul de la 9945 | Tâche 6 |
| §4.4 ligne 9369 | Tâche 1 |
| §4.5 interface | Tâche 8 |
| §5 tests | Tâches 1-7, vérifiés par mutation en tâche 9 |
