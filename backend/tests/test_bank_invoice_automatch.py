"""Test — l'auto-match des FACTURES tolère les noms partiels dans la description bancaire.

Régression : le matcheur exigeait `client_name in desc_lower` (substring stricte du nom entier).
Une facture d'un client « Ferme Lebleu-Deschamps inc. » ne matchait pas un virement Interac
« /LEBLEU DESCHAM/ » car le nom complet n'est pas une substring de la description. Le fix
étend `_name_match` (feature #7.3, déjà utilisé pour dépenses) aux factures : recoupement par
tokens significatifs (« lebleu » ancre le match).

Tests unitaires purs sur `_score_invoice_candidate` (pas de dépendance DB).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")
os.environ.setdefault("DB_NAME", "facturepro")

from backend.server import _score_invoice_candidate, _parse_iso_date  # noqa: E402


def _inv(total, issue_date, due_date=None):
    return {"total": total, "issue_date": issue_date,
            "due_date": due_date or issue_date, "payments": []}


def test_score_full_client_name_not_substring_gets_name_credit():
    """Nom client entier « ferme lebleu-deschamps inc. » n'est PAS substring de
    « virement interac de /lebleu descham/ » — mais le TOKEN « lebleu » recoupe → score 3.
    C'est exactement le cas qui échouait avant le fix (retournait score 2)."""
    tx_date = _parse_iso_date("2099-04-21")
    inv = _inv(1839.60, "2099-04-20")
    desc = "virement interac de /lebleu descham/"
    client_name = "ferme lebleu-deschamps inc."
    # Sanity : le nom entier n'est vraiment PAS une substring
    assert client_name not in desc
    score, date_diff, _ = _score_invoice_candidate(tx_date, 1839.60, inv, client_name, desc)
    assert score == 3, f"attendu 3 (montant + date + token), obtenu {score}"
    assert date_diff == 1


def test_score_no_common_token_gets_no_name_credit():
    """SÉCURITÉ : aucun token distinctif commun → score 2 (montant + date seuls).
    Empêche les faux matchs sur montant + date fortuits."""
    tx_date = _parse_iso_date("2099-05-11")
    inv = _inv(500.00, "2099-05-10")
    desc = "depot divers anonyme"
    client_name = "boutique unique"
    score, _, _ = _score_invoice_candidate(tx_date, 500.00, inv, client_name, desc)
    assert score == 2, f"attendu 2 (pas de token nom), obtenu {score}"


def test_score_stopword_only_overlap_no_name_credit():
    """SÉCURITÉ : recoupement uniquement sur mots génériques (stopwords : « paiement »,
    « facture », « inc », « services », etc.) → pas de crédit nom. Empêche que « Paiement
    Hydro » matche « Paiement Bell »."""
    tx_date = _parse_iso_date("2099-06-15")
    inv = _inv(100.00, "2099-06-14")
    desc = "paiement facture services inc"
    client_name = "paiement services inc"
    score, _, _ = _score_invoice_candidate(tx_date, 100.00, inv, client_name, desc)
    assert score == 2, f"attendu 2 (stopwords seulement), obtenu {score}"


def test_score_date_out_of_window_no_date_credit():
    """Date de facture > 3 jours de la transaction → pas de crédit date (score 2 max si nom)."""
    tx_date = _parse_iso_date("2099-04-21")
    inv = _inv(1839.60, "2099-04-10")  # 11 jours avant
    desc = "virement interac de /lebleu descham/"
    client_name = "ferme lebleu-deschamps inc."
    score, date_diff, _ = _score_invoice_candidate(tx_date, 1839.60, inv, client_name, desc)
    assert score == 2, f"attendu 2 (nom OK mais date > 3j), obtenu {score}"
    assert date_diff == 11


def test_score_exact_amount_date_and_full_name_substring():
    """Cas historique déjà supporté (avant le fix) : nom entier substring de la description → 3."""
    tx_date = _parse_iso_date("2099-04-21")
    inv = _inv(1839.60, "2099-04-20")
    desc = "paiement de ferme lebleu-deschamps inc. par virement"
    client_name = "ferme lebleu-deschamps inc."
    assert client_name in desc  # substring stricte fonctionne
    score, _, _ = _score_invoice_candidate(tx_date, 1839.60, inv, client_name, desc)
    assert score == 3
