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
        #
        # ⚠️ NE PAS faire `monkeypatch.setattr(server_module.db.company_settings, "find_one", ...)` :
        # `Database.__getattr__` de pymongo construit un NOUVEL objet `Collection` à chaque accès
        # d'attribut (`db.company_settings is db.company_settings` -> False, vérifié). Le patch
        # porterait sur un objet jetable ; `_build_t2125_report` interrogerait une autre instance
        # et retomberait sur la VRAIE base locale (copie de prod) — ici en lecture seule (pas de
        # risque d'écriture), mais le test échouerait pour la mauvaise raison (settings introuvables
        # pour "organization_id": "x") au lieu de tester le calcul. Trappe déjà documentée dans ce
        # repo : tests/test_subscription_recurring.py:31-49. On patche donc la méthode sur la
        # CLASSE, filtrée par nom de collection, et on délègue pour toute autre collection.
        _fake_settings = {
            "entity_type": "sole_proprietor", "province": "QC",
            "office_location": "home", "home_office_qualifies": True,
            "home_office_percentage": 20.0,
            "home_office_area_sqm": 20.0, "home_total_area_sqm": 100.0,
        }
        _vrai_find_one = pymongo.collection.Collection.find_one

        def _find_one(self, *a, **k):
            if self.name == "company_settings":
                return _fake_settings
            return _vrai_find_one(self, *a, **k)

        monkeypatch.setattr(pymongo.collection.Collection, "find_one", _find_one)
        r = server_module._build_t2125_report({"organization_id": "x"}, 2025, "accrual")
        assert r["net_income_before_home_office"] == 49000.0, (
            "la 9369 doit EXCLURE les frais de domicile")
        assert r["net_income_before_home_office_line"] == "9369"
        assert r["net_income_line"] == "9946", "le revenu net FINAL est la 9946, pas la 9369"
        assert r["net_income"] < r["net_income_before_home_office"]


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
