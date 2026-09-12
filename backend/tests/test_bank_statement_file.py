"""Tests — conservation et consultation du RELEVÉ ORIGINAL d'un import bancaire.

Objectif : pouvoir rouvrir/télécharger le relevé déposé sans retourner sur le site de la banque.
Le fichier est stocké en binaire inline (db.files, purpose='bank_statement') et servi par
GET /api/bank/imports/{id}/statement (authentifié + scopé org).
"""
import json
import os
import sys
import uuid as _uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")
os.environ.setdefault("DB_NAME", "facturepro")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from backend.server import app, db  # noqa: E402

client = TestClient(app)

MAP_SINGLE = {
    "delimiter": ",", "has_header": True, "date_column": 0, "date_format": "YYYY-MM-DD",
    "description_column": 1, "amount_mode": "single", "amount_column": 2,
    "sign_convention": "positive_is_credit",
}


@pytest.fixture
def auth_headers():
    r = client.post("/api/auth/login",
                    json={"email": "gussdub@gmail.com", "password": "testpass123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _csv_bytes(tag):
    # tag rend le contenu unique → hash unique → pas de 409 doublon entre tests
    return (f"Date,Desc,Montant\n2026-06-01,IONOS-{tag},-9.20\n"
            f"2026-06-02,GITHUB-{tag},-5.74\n").encode("utf-8")


def _import_csv(auth_headers, tag, filename="releve.csv"):
    raw = _csv_bytes(tag)
    r = client.post("/api/bank/imports", headers=auth_headers,
                    files={"file": (filename, raw, "text/csv")},
                    data={"mapping": json.dumps(MAP_SINGLE), "bank_label": "Test Relevé"})
    assert r.status_code in (200, 201), r.text
    return r.json()["import_id"] if "import_id" in r.json() else r.json()["import"]["id"], raw


def _cleanup(import_id):
    imp = db.bank_imports.find_one({"id": import_id}) or {}
    if imp.get("statement_file_id"):
        db.files.delete_one({"id": imp["statement_file_id"]})
    db.bank_transactions.delete_many({"import_id": import_id})
    db.bank_imports.delete_one({"id": import_id})


class TestStatementStoredAndServed:
    def test_original_file_is_stored_and_served_byte_identical(self, auth_headers):
        import_id, raw = _import_csv(auth_headers, _uuid.uuid4().hex[:8])
        try:
            imp = db.bank_imports.find_one({"id": import_id})
            assert imp.get("statement_file_id"), "le relevé original doit être conservé"
            f = db.files.find_one({"id": imp["statement_file_id"]})
            assert f["purpose"] == "bank_statement" and f["is_deleted"] is False
            r = client.get(f"/api/bank/imports/{import_id}/statement", headers=auth_headers)
            assert r.status_code == 200, r.text
            assert r.content == raw            # octet pour octet = l'original
            assert r.headers["content-type"].startswith("text/csv")
            assert "inline" in r.headers.get("content-disposition", "")
            assert "no-store" in r.headers.get("cache-control", "")
        finally:
            _cleanup(import_id)

    def test_download_flag_sets_attachment(self, auth_headers):
        import_id, _ = _import_csv(auth_headers, _uuid.uuid4().hex[:8])
        try:
            r = client.get(f"/api/bank/imports/{import_id}/statement?download=1",
                           headers=auth_headers)
            assert r.status_code == 200
            assert "attachment" in r.headers.get("content-disposition", "")
        finally:
            _cleanup(import_id)

    def test_has_statement_file_exposed(self, auth_headers):
        import_id, _ = _import_csv(auth_headers, _uuid.uuid4().hex[:8])
        try:
            detail = client.get(f"/api/bank/imports/{import_id}", headers=auth_headers).json()
            assert detail["import"]["has_statement_file"] is True
        finally:
            _cleanup(import_id)

    def test_filename_header_is_sanitized(self, auth_headers):
        # Anti-injection d'en-tête Content-Disposition (guillemets / CRLF dans le nom).
        import_id, _ = _import_csv(auth_headers, _uuid.uuid4().hex[:8],
                                   filename='rel"eve\r\nX-Injected: 1.csv')
        try:
            r = client.get(f"/api/bank/imports/{import_id}/statement", headers=auth_headers)
            assert r.status_code == 200
            cd = r.headers.get("content-disposition", "")
            assert "\r" not in cd and "\n" not in cd
            assert "x-injected" not in {k.lower() for k in r.headers.keys()}
        finally:
            _cleanup(import_id)


class TestAbsenceAndIsolation:
    def test_import_without_stored_file_404(self, auth_headers):
        # Import antérieur à la feature : aucun statement_file_id → 404 explicite, pas de 500.
        import_id, _ = _import_csv(auth_headers, _uuid.uuid4().hex[:8])
        try:
            db.bank_imports.update_one({"id": import_id}, {"$unset": {"statement_file_id": ""}})
            r = client.get(f"/api/bank/imports/{import_id}/statement", headers=auth_headers)
            assert r.status_code == 404
            detail = client.get(f"/api/bank/imports/{import_id}", headers=auth_headers).json()
            assert detail["import"]["has_statement_file"] is False
        finally:
            _cleanup(import_id)

    def test_cross_org_import_not_served(self, auth_headers):
        other = f"OTHERORG-{_uuid.uuid4()}"
        fid, iid = str(_uuid.uuid4()), str(_uuid.uuid4())
        db.files.insert_one({"id": fid, "organization_id": other, "data": b"SECRET_RELEVE",
                             "mime_type": "text/csv", "original_filename": "x.csv",
                             "purpose": "bank_statement", "is_deleted": False})
        db.bank_imports.insert_one({"id": iid, "organization_id": other, "bank_label": "Autre",
                                    "statement_file_id": fid, "row_count": 0})
        try:
            r = client.get(f"/api/bank/imports/{iid}/statement", headers=auth_headers)
            assert r.status_code == 404          # jamais le relevé d'une autre organisation
        finally:
            db.files.delete_one({"id": fid})
            db.bank_imports.delete_one({"id": iid})

    def test_delete_import_soft_deletes_statement(self, auth_headers):
        import_id, _ = _import_csv(auth_headers, _uuid.uuid4().hex[:8])
        file_id = db.bank_imports.find_one({"id": import_id})["statement_file_id"]
        try:
            r = client.delete(f"/api/bank/imports/{import_id}", headers=auth_headers)
            assert r.status_code in (200, 204), r.text
            assert db.files.find_one({"id": file_id})["is_deleted"] is True
        finally:
            db.files.delete_one({"id": file_id})
            db.bank_transactions.delete_many({"import_id": import_id})
            db.bank_imports.delete_one({"id": import_id})

    def test_statement_never_served_by_public_files_endpoint(self, auth_headers):
        """Un relevé ne doit JAMAIS sortir par /api/files/{id} (public, sans auth), même si
        l'utilisateur pointe son propre logo_url dessus (liste blanche purpose='logo')."""
        import_id, _ = _import_csv(auth_headers, _uuid.uuid4().hex[:8])
        file_id = db.bank_imports.find_one({"id": import_id})["statement_file_id"]
        owner_uid = db.files.find_one({"id": file_id})["user_id"]
        settings = db.company_settings.find_one({"user_id": owner_uid}) or {}
        prev_logo = settings.get("logo_url")
        try:
            # pire cas : le propriétaire référence SON relevé comme logo (satisfait les 2 autres gardes)
            db.company_settings.update_one({"user_id": owner_uid},
                                           {"$set": {"logo_url": f"/api/files/{file_id}"}})
            r = client.get(f"/api/files/{file_id}")   # AUCUN en-tête d'auth
            assert r.status_code == 404, "un relevé bancaire ne doit jamais être public"
        finally:
            db.company_settings.update_one({"user_id": owner_uid},
                                           {"$set": {"logo_url": prev_logo}})
            _cleanup(import_id)

    def test_statement_not_deletable_via_files_endpoint(self, auth_headers):
        """IMPORTANT (revue) : DELETE /api/files/{id} (expenses:write) ne doit PAS pouvoir détruire
        un relevé — son id fuit via statement_file_id, exposé à bank:read, et c'est irréversible."""
        import_id, _ = _import_csv(auth_headers, _uuid.uuid4().hex[:8])
        file_id = db.bank_imports.find_one({"id": import_id})["statement_file_id"]
        try:
            r = client.delete(f"/api/files/{file_id}", headers=auth_headers)
            assert r.status_code == 404, "un relevé ne doit pas être supprimable par ce chemin"
            assert db.files.find_one({"id": file_id})["is_deleted"] is False
            # toujours servi normalement
            assert client.get(f"/api/bank/imports/{import_id}/statement",
                              headers=auth_headers).status_code == 200
        finally:
            _cleanup(import_id)

    def test_statement_not_served_by_receipts_endpoint(self, auth_headers):
        """Confusion de purpose : même référencé par une dépense, un relevé n'est jamais servi
        par /api/receipts/{id} (qui ne demande que expenses:read)."""
        import_id, _ = _import_csv(auth_headers, _uuid.uuid4().hex[:8])
        file_id = db.bank_imports.find_one({"id": import_id})["statement_file_id"]
        try:
            r = client.get(f"/api/receipts/{file_id}", headers=auth_headers)
            assert r.status_code == 404
        finally:
            _cleanup(import_id)

    def test_statement_not_destroyed_by_expense_receipt_cascade(self, auth_headers):
        """IMPORTANT (revue) : variante sans /api/files — pointer une dépense sur le relevé via
        receipt_file_id (saisi par le client) puis le remettre à null déclenchait la cascade
        soft-delete et détruisait le relevé, sans jamais avoir bank:write."""
        import_id, _ = _import_csv(auth_headers, _uuid.uuid4().hex[:8])
        file_id = db.bank_imports.find_one({"id": import_id})["statement_file_id"]
        org_id = db.bank_imports.find_one({"id": import_id})["organization_id"]
        exp_id = str(_uuid.uuid4())
        db.expenses.insert_one({"id": exp_id, "organization_id": org_id, "amount_cad": 10.0,
                                "expense_date": "2026-06-01", "description": "piege",
                                "receipt_file_id": file_id})
        try:
            client.put(f"/api/expenses/{exp_id}", headers=auth_headers,
                       json={"receipt_file_id": None})
            assert db.files.find_one({"id": file_id})["is_deleted"] is False, \
                "le relevé a été détruit via la cascade de dépense"
            assert client.get(f"/api/bank/imports/{import_id}/statement",
                              headers=auth_headers).status_code == 200
        finally:
            db.expenses.delete_one({"id": exp_id})
            _cleanup(import_id)

    def test_backfill_guard_never_retags_a_statement(self, auth_headers):
        """IMPORTANT (revue) : le backfill de démarrage (re-tag purpose='receipt' des fichiers
        référencés par expense.receipt_url, saisi par le client) ne doit JAMAIS écraser un
        purpose sensible. On rejoue ici EXACTEMENT son filtre d'écriture."""
        import_id, _ = _import_csv(auth_headers, _uuid.uuid4().hex[:8])
        file_id = db.bank_imports.find_one({"id": import_id})["statement_file_id"]
        try:
            res = db.files.update_one(
                {"id": file_id, "purpose": {"$in": [None, "", "logo"]}},
                {"$set": {"purpose": "receipt"}})
            assert res.modified_count == 0, "le relevé a été retagué → lisible via /api/receipts"
            assert db.files.find_one({"id": file_id})["purpose"] == "bank_statement"
        finally:
            _cleanup(import_id)

    def test_dry_run_stores_nothing(self, auth_headers):
        before = db.files.count_documents({"purpose": "bank_statement"})
        r = client.post("/api/bank/imports?dry_run=true", headers=auth_headers,
                        files={"file": ("releve.csv", _csv_bytes("dry"), "text/csv")},
                        data={"mapping": json.dumps(MAP_SINGLE), "bank_label": "Test"})
        assert r.status_code == 200
        assert db.files.count_documents({"purpose": "bank_statement"}) == before
