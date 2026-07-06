"""Tests — import de relevé bancaire PDF via Claude (feature #7.1).

Cible la pièce critique pour l'argent : _normalize_bank_rows (signe crédit/débit,
parse_error sur ligne douteuse — jamais un montant faux silencieux) + le flux
endpoint PDF (aperçu → cache → import réutilise la MÊME extraction, 1 seul scan).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import backend.server as server  # noqa: E402
from backend.server import app, db, _normalize_bank_rows  # noqa: E402

client = TestClient(app)

# Un octet-header PDF minimal suffit : la détection se fait sur "%PDF", l'extraction
# réelle est court-circuitée par le mock _TEST_MOCK_BANK_EXTRACTION.
FAKE_PDF = b"%PDF-1.4 fake bank statement bytes"


# ─────────────────────────── UNITAIRE : _normalize_bank_rows ───────────────────────────

def test_credit_is_positive_debit_is_negative():
    raw = {"transactions": [
        {"date": "2026-03-01", "description": "Depot", "amount": 100.0, "direction": "credit"},
        {"date": "2026-03-02", "description": "Retrait", "amount": 40.5, "direction": "debit"},
    ]}
    rows = _normalize_bank_rows(raw)
    assert rows[0]["amount_cad"] == 100.0 and rows[0]["parse_error"] is False
    assert rows[1]["amount_cad"] == -40.5 and rows[1]["parse_error"] is False


def test_negative_amount_magnitude_is_normalized_by_direction():
    # Claude est censé renvoyer une valeur absolue ; si un signe traîne, on prend |amount|
    # et c'est la direction qui décide -> pas de double négation silencieuse.
    raw = {"transactions": [
        {"date": "2026-03-03", "description": "X", "amount": -40.0, "direction": "debit"},
    ]}
    rows = _normalize_bank_rows(raw)
    assert rows[0]["amount_cad"] == -40.0  # debit reste négatif, magnitude 40


def test_bad_date_flags_parse_error():
    raw = {"transactions": [
        {"date": "03/2026", "description": "X", "amount": 10.0, "direction": "credit"},
    ]}
    rows = _normalize_bank_rows(raw)
    assert rows[0]["date"] is None
    assert rows[0]["parse_error"] is True
    assert rows[0]["amount_cad"] is None or rows[0]["parse_error"] is True


def test_unknown_direction_flags_parse_error():
    raw = {"transactions": [
        {"date": "2026-03-01", "description": "X", "amount": 10.0, "direction": "transfer"},
    ]}
    rows = _normalize_bank_rows(raw)
    assert rows[0]["amount_cad"] is None
    assert rows[0]["parse_error"] is True


def test_non_numeric_amount_flags_parse_error():
    raw = {"transactions": [
        {"date": "2026-03-01", "description": "X", "amount": "N/A", "direction": "credit"},
    ]}
    rows = _normalize_bank_rows(raw)
    assert rows[0]["amount_cad"] is None
    assert rows[0]["parse_error"] is True


def test_description_sanitized_and_row_index_sequential():
    raw = {"transactions": [
        {"date": "2026-03-01", "description": "=CMD()", "amount": 1.0, "direction": "credit"},
        {"date": "2026-03-02", "description": "ok", "amount": 2.0, "direction": "credit"},
    ]}
    rows = _normalize_bank_rows(raw)
    assert not rows[0]["description"].startswith("=")  # injection CSV strippée
    assert [r["row_index"] for r in rows] == [0, 1]


def test_empty_or_garbage_extraction_is_safe():
    assert _normalize_bank_rows({}) == []
    assert _normalize_bank_rows({"transactions": None}) == []
    assert _normalize_bank_rows(None) == []
    rows = _normalize_bank_rows({"transactions": ["not-a-dict"]})
    assert rows[0]["parse_error"] is True


# ─────────────────────────── INTÉGRATION : endpoint PDF ───────────────────────────

@pytest.fixture
def auth_headers():
    r = client.post("/api/auth/login", json={"email": "gussdub@gmail.com", "password": "testpass123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def mock_bank_extraction():
    server._TEST_MOCK_BANK_EXTRACTION = {"transactions": [
        {"date": "2026-04-01", "description": "PAIEMENT ABC", "amount": 57.21, "direction": "debit"},
        {"date": "2026-04-02", "description": "DEPOT CLIENT", "amount": 1000.00, "direction": "credit"},
    ]}
    yield
    server._TEST_MOCK_BANK_EXTRACTION = None


@pytest.fixture
def reset_quota():
    """Remet le compteur de scans de l'org seed à 0 le temps du test (le compte seed
    a souvent atteint son quota mensuel), puis restaure la valeur d'origine."""
    u = db.users.find_one({"email": "gussdub@gmail.com"})
    org_id = u.get("organization_id")
    org = db.organizations.find_one({"id": org_id}) or {}
    original = org.get("scan_count_this_month", 0)
    db.organizations.update_one({"id": org_id}, {"$set": {"scan_count_this_month": 0}})
    yield
    db.organizations.update_one({"id": org_id}, {"$set": {"scan_count_this_month": original}})


def test_pdf_dry_run_previews_without_import(auth_headers, mock_bank_extraction, reset_quota):
    r = client.post("/api/bank/imports?dry_run=true", headers=auth_headers,
                    files={"file": ("releve.pdf", FAKE_PDF, "application/pdf")},
                    data={"bank_label": "Test PDF"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "pdf"
    assert body["total_rows"] == 2
    amounts = sorted(row["amount_cad"] for row in body["parsed_rows"])
    assert amounts == [-57.21, 1000.0]


def test_pdf_import_persists_and_dedupes(auth_headers, mock_bank_extraction, reset_quota):
    # Pré-nettoyage (au cas où un run précédent aurait laissé des restes)
    fh = server._compute_file_hash(FAKE_PDF)
    db.bank_imports.delete_many({"file_hash": fh})
    db.bank_pdf_extractions.delete_many({"file_hash": fh})
    imported_id = None
    try:
        # Aperçu d'abord : peuple le cache d'extraction (l'import réutilise strictement ce cache).
        pre = client.post("/api/bank/imports?dry_run=true", headers=auth_headers,
                          files={"file": ("releve.pdf", FAKE_PDF, "application/pdf")},
                          data={"bank_label": "Test PDF"})
        assert pre.status_code == 200, pre.text
        r = client.post("/api/bank/imports", headers=auth_headers,
                        files={"file": ("releve.pdf", FAKE_PDF, "application/pdf")},
                        data={"bank_label": "Test PDF"})
        assert r.status_code in (200, 201), r.text
        data = r.json()
        imported_id = data["import"]["id"]
        assert data["import"]["source"] == "pdf"
        assert len(data["transactions"]) == 2
        # Ré-import du MÊME PDF -> 409 (dédup par hash)
        r2 = client.post("/api/bank/imports", headers=auth_headers,
                         files={"file": ("releve.pdf", FAKE_PDF, "application/pdf")},
                         data={"bank_label": "Test PDF"})
        assert r2.status_code == 409, r2.text
    finally:
        if imported_id:
            db.bank_transactions.delete_many({"import_id": imported_id})
            db.bank_imports.delete_one({"id": imported_id})


def test_pdf_import_without_preview_refuses(auth_headers, mock_bank_extraction, reset_quota):
    # L'import ne doit JAMAIS ré-extraire : sans aperçu (cache vide) -> 409 « relance l'analyse ».
    fh = server._compute_file_hash(FAKE_PDF)
    db.bank_imports.delete_many({"file_hash": fh})
    db.bank_pdf_extractions.delete_many({"file_hash": fh})
    r = client.post("/api/bank/imports", headers=auth_headers,
                    files={"file": ("releve.pdf", FAKE_PDF, "application/pdf")},
                    data={"bank_label": "Test PDF"})
    assert r.status_code == 409, r.text
    detail = r.json()["detail"].lower()
    assert "aper" in detail or "analyse" in detail


def test_pdf_dry_run_returns_all_rows_not_capped(auth_headers, reset_quota):
    # L'aperçu PDF renvoie TOUTES les lignes (pas de troncature à 10) pour permettre la vérif.
    server._TEST_MOCK_BANK_EXTRACTION = {"transactions": [
        {"date": "2026-05-%02d" % (i + 1), "description": f"TX{i}",
         "amount": float(i + 1), "direction": "credit"} for i in range(12)]}
    fh = server._compute_file_hash(FAKE_PDF)
    db.bank_pdf_extractions.delete_many({"file_hash": fh})
    try:
        r = client.post("/api/bank/imports?dry_run=true", headers=auth_headers,
                        files={"file": ("releve.pdf", FAKE_PDF, "application/pdf")},
                        data={"bank_label": "Test PDF"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total_rows"] == 12
        assert len(body["parsed_rows"]) == 12  # non tronqué à 10
    finally:
        server._TEST_MOCK_BANK_EXTRACTION = None
        db.bank_pdf_extractions.delete_many({"file_hash": fh})


def test_sanitize_cell_strips_stacked_prefixes():
    from backend.server import _sanitize_cell
    assert not _sanitize_cell("==2+3").startswith("=")
    assert not _sanitize_cell("\t=cmd").startswith(("=", "\t"))
    assert _sanitize_cell("ok") == "ok"  # inchangé si pas de préfixe dangereux


def test_date_separator_tolerance():
    # Desjardins VISA écrit 2026/06/01 (slashes) même si le format choisi a des tirets.
    from backend.server import _parse_csv_date
    assert _parse_csv_date("2026/06/01", "YYYY-MM-DD") == "2026-06-01"
    assert _parse_csv_date("2026-06-01", "YYYY-MM-DD") == "2026-06-01"
    assert _parse_csv_date("01/06/2026", "DD/MM/YYYY") == "2026-06-01"
    assert _parse_csv_date("01-06-2026", "DD/MM/YYYY") == "2026-06-01"
    assert _parse_csv_date("IONOS 877", "YYYY-MM-DD") is None  # non-date -> None
