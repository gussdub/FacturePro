"""Tests du préréglage Desjardins AccèsD Affaires + robustesse d'encodage du parseur bancaire.

Le préréglage PRÉ-REMPLIT le mapping ; l'aperçu (dry-run) reste la validation côté client.
Ces tests prouvent que le mapping d'un préréglage parse correctement un relevé au format
AccèsD Affaires (Date, Description, Retraits, Dépôts, Solde) : retraits → montant négatif,
dépôts → montant positif, dates FR (JJ/MM/AAAA) / EN (MM/JJ/AAAA) → ISO.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server import (
    _parse_csv_rows,
    _decode_bank_csv,
    BANK_CSV_PRESETS,
)


def _preset(key):
    return next(p for p in BANK_CSV_PRESETS if p["key"] == key)


class TestPresetShape:
    def test_two_desjardins_presets_present(self):
        keys = {p["key"] for p in BANK_CSV_PRESETS}
        assert "desjardins_accesd_affaires_fr" in keys
        assert "desjardins_accesd_affaires_en" in keys

    def test_each_preset_wellformed(self):
        allowed_date_formats = {"YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY"}
        for p in BANK_CSV_PRESETS:
            assert p["key"] and p["label"]
            m = p["mapping"]
            # Desjardins = colonnes Retrait/Dépôt séparées
            assert m["amount_mode"] == "debit_credit"
            assert isinstance(m["debit_column"], int)
            assert isinstance(m["credit_column"], int)
            assert m["debit_column"] != m["credit_column"]
            assert isinstance(m["date_column"], int)
            assert isinstance(m["description_column"], int)
            assert m["date_format"] in allowed_date_formats
            assert m["has_header"] is True

    def test_fr_uses_ddmmyyyy_en_uses_mmddyyyy(self):
        assert _preset("desjardins_accesd_affaires_fr")["mapping"]["date_format"] == "DD/MM/YYYY"
        assert _preset("desjardins_accesd_affaires_en")["mapping"]["date_format"] == "MM/DD/YYYY"


class TestDesjardinsFrPreset:
    mapping = _preset("desjardins_accesd_affaires_fr")["mapping"]

    def test_period_decimals_unquoted(self):
        # Variante robuste : virgule délimiteur, points décimaux (pas de guillemets requis)
        csv = (
            "Date,Description,Retraits,Dépôts,Solde\n"
            "14/03/2026,Paiement Hydro,127.84,,1234.56\n"
            "15/03/2026,Depot client ABC,,500.00,1734.56\n"
        ).encode("utf-8")
        rows = _parse_csv_rows(csv, self.mapping)
        assert len(rows) == 2
        # retrait → négatif
        assert rows[0]["date"] == "2026-03-14"
        assert rows[0]["amount_cad"] == -127.84
        assert rows[0]["parse_error"] is False
        # dépôt → positif
        assert rows[1]["date"] == "2026-03-15"
        assert rows[1]["amount_cad"] == 500.00
        assert rows[1]["parse_error"] is False

    def test_comma_decimals_quoted(self):
        # Variante FR RFC-correcte : décimales à virgule, donc champs numériques entre guillemets
        csv = (
            'Date,Description,Retraits,Dépôts,Solde\n'
            '"14/03/2026","Paiement Hydro-Québec","127,84","","1 234,56"\n'
            '"15/03/2026","Dépôt client","","1 500,00","2 734,56"\n'
        ).encode("utf-8")
        rows = _parse_csv_rows(csv, self.mapping)
        assert len(rows) == 2
        assert rows[0]["amount_cad"] == -127.84
        assert rows[1]["amount_cad"] == 1500.00
        assert all(not r["parse_error"] for r in rows)

    def test_accents_preserved_in_description(self):
        csv = (
            "Date,Description,Retraits,Dépôts,Solde\n"
            "14/03/2026,Café Montréal — dépôt,,12.50,100.00\n"
        ).encode("utf-8")
        rows = _parse_csv_rows(csv, self.mapping)
        assert "Café Montréal" in rows[0]["description"]
        assert "�" not in rows[0]["description"]


class TestDesjardinsEnPreset:
    mapping = _preset("desjardins_accesd_affaires_en")["mapping"]

    def test_mmddyyyy_and_period_decimals(self):
        csv = (
            "Date,Description,Withdrawals,Deposits,Balance\n"
            "03/14/2026,Hydro payment,127.84,,1234.56\n"
            "03/15/2026,Client deposit,,500.00,1734.56\n"
        ).encode("utf-8")
        rows = _parse_csv_rows(csv, self.mapping)
        assert rows[0]["date"] == "2026-03-14"   # MM/DD/YYYY interprété correctement
        assert rows[0]["amount_cad"] == -127.84
        assert rows[1]["date"] == "2026-03-15"
        assert rows[1]["amount_cad"] == 500.00


class TestParserFailsLoudlyNotSilently:
    """Sécurité financière : le parseur doit MARQUER parse_error (rouge dans l'aperçu) plutôt
    que produire un montant FAUX silencieux. Cas trouvés par la revue adversariale."""
    mapping = _preset("desjardins_accesd_affaires_fr")["mapping"]

    def test_comma_decimals_unquoted_flagged(self):
        # LE cas dangereux : virgule décimale SANS guillemets + délimiteur virgule.
        # "127,84" est scindé -> ligne mal alignée -> parse_error (pas -43.00 silencieux).
        csv = (
            "Date,Description,Retraits,Depots,Solde\n"
            "14/03/2026,Paiement Hydro,127,84,,1234,56\n"
        ).encode("utf-8")
        rows = _parse_csv_rows(csv, self.mapping)
        assert rows[0]["parse_error"] is True
        assert rows[0]["amount_cad"] != -43.00   # surtout : PAS le montant faux plausible

    def test_dollar_sign_amount_flagged(self):
        csv = (
            "Date,Description,Retraits,Depots,Solde\n"
            "15/03/2026,Retrait,$25.00,,925.00\n"
        ).encode("utf-8")
        rows = _parse_csv_rows(csv, self.mapping)
        assert rows[0]["parse_error"] is True   # retrait non perdu en 0 silencieux

    def test_parentheses_amount_flagged(self):
        csv = (
            "Date,Description,Retraits,Depots,Solde\n"
            "15/03/2026,Retrait,(50.00),,900.00\n"
        ).encode("utf-8")
        rows = _parse_csv_rows(csv, self.mapping)
        assert rows[0]["parse_error"] is True

    def test_negative_in_magnitude_column_flagged(self):
        # -30 en colonne Dépôts : le abs() aurait donné +30 (inversion). On marque erreur.
        csv = (
            "Date,Description,Retraits,Depots,Solde\n"
            "17/03/2026,Contre-passation,,-30.00,895.00\n"
        ).encode("utf-8")
        rows = _parse_csv_rows(csv, self.mapping)
        assert rows[0]["parse_error"] is True

    def test_both_debit_and_credit_filled_flagged(self):
        # Une transaction est soit retrait soit dépôt, jamais les deux -> ligne suspecte.
        csv = (
            "Date,Description,Retraits,Depots,Solde\n"
            "18/03/2026,Ligne douteuse,10.00,20.00,900.00\n"
        ).encode("utf-8")
        rows = _parse_csv_rows(csv, self.mapping)
        assert rows[0]["parse_error"] is True

    def test_column_count_mismatch_flagged(self):
        # En-tête 5 colonnes, ligne de données 6 colonnes -> mal alignée.
        csv = (
            "Date,Description,Retraits,Depots,Solde\n"
            "19/03/2026,Desc,10.00,,900.00,extra\n"
        ).encode("utf-8")
        rows = _parse_csv_rows(csv, self.mapping)
        assert rows[0]["parse_error"] is True

    def test_valid_rows_still_pass(self):
        # Non-régression : une ligne bien formée reste sans erreur, montant correct.
        csv = (
            "Date,Description,Retraits,Depots,Solde\n"
            "20/03/2026,Depot,,500.00,1400.00\n"
            "21/03/2026,Retrait,75.50,,1324.50\n"
        ).encode("utf-8")
        rows = _parse_csv_rows(csv, self.mapping)
        assert [r["parse_error"] for r in rows] == [False, False]
        assert rows[0]["amount_cad"] == 500.00
        assert rows[1]["amount_cad"] == -75.50


class TestDecodeBankCsv:
    def test_plain_utf8(self):
        assert _decode_bank_csv("Café,Montréal\n".encode("utf-8")) == "Café,Montréal\n"

    def test_utf8_bom_stripped(self):
        # BOM UTF-8 en tête (fréquent sur les exports Windows) — doit être retiré
        raw = "﻿Date,Desc\n".encode("utf-8")
        out = _decode_bank_csv(raw)
        assert out == "Date,Desc\n"
        assert not out.startswith("﻿")

    def test_latin1_accents_not_corrupted(self):
        # Ancien code (decode utf-8 errors=replace) aurait produit U+FFFD ; ici on décode l'accent
        raw = "Café\n".encode("latin-1")  # b"Caf\xe9\n" — invalide en UTF-8
        out = _decode_bank_csv(raw)
        assert "é" in out
        assert "�" not in out

    def test_never_raises(self):
        # latin-1 (dernier recours) décode n'importe quel octet sans lever d'exception
        raw = bytes(range(256))
        assert isinstance(_decode_bank_csv(raw), str)
