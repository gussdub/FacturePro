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
