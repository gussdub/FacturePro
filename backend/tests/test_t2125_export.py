import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from server import T2125_LINE_LABELS, EXPENSE_CATEGORIES, T2125_LABEL_TABLE_TAX_YEAR


class TestT2125LineLabels:
    def test_label_table_year_constant_present(self):
        assert T2125_LABEL_TABLE_TAX_YEAR == 2024

    def test_known_line(self):
        assert T2125_LINE_LABELS["8520"] == "Publicité et promotion"
        assert T2125_LINE_LABELS["8523"] == "Repas et représentation"
        assert T2125_LINE_LABELS["9945"] == "Frais d'utilisation de la résidence aux fins de l'entreprise"

    def test_all_expense_categories_arc_lines_covered(self):
        """Toute arc_line non-vide dans EXPENSE_CATEGORIES doit avoir un libellé.
        Test de régression : ajouter une catégorie sans libellé doit faire échouer."""
        missing = []
        for cat in EXPENSE_CATEGORIES:
            arc_line = cat.get("arc_line") or ""
            if arc_line and arc_line not in T2125_LINE_LABELS:
                missing.append((cat["code"], arc_line))
        assert not missing, f"Catégories avec arc_line non couverte : {missing}"

    def test_9270_other_fallback_present(self):
        # Catégorie 'other' (arc_line="") tombe sur 9270 via _t2125_flatten_pnl_expenses
        assert "9270" in T2125_LINE_LABELS
        assert T2125_LINE_LABELS["9270"] == "Autres dépenses"
