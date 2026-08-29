"""Tests — portabilité des données / export ZIP (Loi 25 art. 27)."""
import io
import json
import os
import sys
import uuid as _uuid
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")
os.environ.setdefault("DB_NAME", "facturepro")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from backend import server  # noqa: E402
from backend.server import app, db  # noqa: E402

client = TestClient(app)


@pytest.fixture
def owner():
    email = f"exp-{_uuid.uuid4().hex[:8]}@ex.com"
    r = client.post("/api/auth/register",
                    json={"email": email, "password": "exppass12345", "company_name": "Export Test"})
    assert r.status_code == 200, r.text
    uid = r.json()["user"]["id"]
    org_id = (db.users.find_one({"id": uid}) or {}).get("organization_id")
    yield {"id": uid, "email": email, "org_id": org_id,
           "headers": {"Authorization": f"Bearer {r.json()['access_token']}"}}
    for coll in ("users", "clients", "invitations", "files"):
        db[coll].delete_many({"organization_id": org_id})
    db.users.delete_many({"organization_id": org_id})
    db.user_passwords.delete_one({"user_id": uid})
    db.user_mfa.delete_one({"user_id": uid})
    db.organizations.delete_one({"id": org_id})
    db.audit_logs.delete_many({"organization_id": org_id})


def _zip(resp):
    return zipfile.ZipFile(io.BytesIO(resp.content))


class TestAccessAndFormat:
    def test_owner_gets_zip(self, owner):
        r = client.get("/api/org/export", headers=owner["headers"])
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/zip"
        assert "attachment" in r.headers.get("content-disposition", "")
        z = _zip(r)
        names = z.namelist()
        assert "LISEZMOI.txt" in names
        assert "json/clients.json" in names and "csv/clients.csv" in names
        assert "json/organization.json" in names and "json/members.json" in names

    def test_export_with_numeric_and_bool_cells(self, owner):
        # RÉGRESSION (revue adversariale) : des dépenses/factures/produits portent des champs
        # float/bool → _sanitize_cell ne doit PAS planter (.lstrip sur non-str) → l'export doit
        # renvoyer 200 et le CSV doit contenir les valeurs numériques.
        db.invoices.insert_one({
            "id": str(_uuid.uuid4()), "organization_id": owner["org_id"],
            "invoice_number": "INV-NUM-1", "total_cad": 1234.56, "subtotal": 1073.09,
            "gst_amount": 53.65, "recurrence_active": False, "status": "sent"})
        db.products.insert_one({
            "id": str(_uuid.uuid4()), "organization_id": owner["org_id"],
            "name": "Widget", "unit_price": 9.99, "active": True})
        try:
            r = client.get("/api/org/export", headers=owner["headers"])
            assert r.status_code == 200, r.text
            z = _zip(r)
            inv_csv = z.read("csv/invoices.csv").decode("utf-8-sig")
            assert "1234.56" in inv_csv and "False" in inv_csv
            assert "9.99" in z.read("csv/products.csv").decode("utf-8-sig")
        finally:
            db.invoices.delete_many({"organization_id": owner["org_id"]})
            db.products.delete_many({"organization_id": owner["org_id"]})

    def test_export_gated_by_org_mfa(self, owner):
        # RÉGRESSION (revue adversariale) : si l'org impose la MFA et que le propriétaire n'est pas
        # enrôlé, l'export (endpoint le plus riche en données) doit être bloqué comme les autres.
        db.organizations.update_one({"id": owner["org_id"]}, {"$set": {"require_mfa": True}})
        try:
            r = client.get("/api/org/export", headers=owner["headers"])
            assert r.status_code == 403, r.text
        finally:
            db.organizations.update_one({"id": owner["org_id"]}, {"$set": {"require_mfa": False}})

    def test_member_forbidden(self, owner):
        m_email = f"m-{_uuid.uuid4().hex[:8]}@ex.com"
        m_pw, m_uid = "memberpass123", str(_uuid.uuid4())
        db.users.insert_one({"id": m_uid, "email": m_email.lower(), "organization_id": owner["org_id"],
                             "role": "accountant", "is_active": True})
        db.user_passwords.insert_one({"user_id": m_uid, "hashed_password": server.hash_password(m_pw)})
        try:
            tok = client.post("/api/auth/login",
                              json={"email": m_email, "password": m_pw}).json()["access_token"]
            r = client.get("/api/org/export", headers={"Authorization": f"Bearer {tok}"})
            assert r.status_code == 403
        finally:
            db.users.delete_one({"id": m_uid})
            db.user_passwords.delete_one({"user_id": m_uid})
            db.login_attempts.delete_one({"_id": server._login_attempt_key(m_email, "testclient")})


class TestContent:
    def test_client_data_in_json_and_csv(self, owner):
        client.post("/api/clients", headers=owner["headers"], json={"name": "Acme Zêta"})
        z = _zip(client.get("/api/org/export", headers=owner["headers"]))
        clients = json.loads(z.read("json/clients.json"))
        assert any(c.get("name") == "Acme Zêta" for c in clients)
        assert "Acme Z" in z.read("csv/clients.csv").decode("utf-8-sig")

    def test_files_included_with_binary(self, owner):
        fid = str(_uuid.uuid4())
        db.files.insert_one({"id": fid, "organization_id": owner["org_id"],
                             "original_filename": "recu.png", "content_type": "image/png",
                             "purpose": "receipt", "is_deleted": False,
                             "data": b"\x89PNG\r\n\x1a\nRECU_BINAIRE"})
        z = _zip(client.get("/api/org/export", headers=owner["headers"]))
        match = [n for n in z.namelist() if n.startswith(f"fichiers/{fid}_")]
        assert match, "fichier binaire absent du zip"
        assert z.read(match[0]) == b"\x89PNG\r\n\x1a\nRECU_BINAIRE"

    def test_cross_org_isolation(self, owner):
        other_org = f"OTHERORG-{_uuid.uuid4()}"
        db.clients.insert_one({"id": str(_uuid.uuid4()), "organization_id": other_org,
                               "name": "SECRET_AUTRE_ORG"})
        try:
            z = _zip(client.get("/api/org/export", headers=owner["headers"]))
            assert b"SECRET_AUTRE_ORG" not in io.BytesIO(
                b"".join(z.read(n) for n in z.namelist())).getvalue()
        finally:
            db.clients.delete_many({"organization_id": other_org})

    def test_audit_logged(self, owner):
        client.get("/api/org/export", headers=owner["headers"])
        assert db.audit_logs.find_one(
            {"organization_id": owner["org_id"], "action": "data.export"}) is not None


class TestSanitizeCell:
    def test_non_string_values_pass_through(self):
        # Le correctif BLOCKING : _sanitize_cell tolère les non-str (float/bool/int/None).
        assert server._sanitize_cell(1234.56) == 1234.56
        assert server._sanitize_cell(True) is True
        assert server._sanitize_cell(42) == 42
        assert server._sanitize_cell(None) == ""
        # ... sans casser l'anti-injection CSV sur les chaînes.
        assert server._sanitize_cell("=CMD()").startswith("CMD")


class TestNoSecrets:
    def test_secrets_never_in_export(self, owner):
        # CRITIQUE : ni hash de mot de passe, ni secret MFA, ni jeton d'invitation dans le ZIP.
        pw_hash = (db.user_passwords.find_one({"user_id": owner["id"]}) or {}).get("hashed_password", "")
        mfa_secret = "TOTPSECRETXYZ234567"
        db.user_mfa.insert_one({"user_id": owner["id"], "secret": mfa_secret,
                                "enabled": True, "backup_codes": ["BACKUPCODE9999"]})
        inv_token = "INVITETOKEN_" + _uuid.uuid4().hex
        db.invitations.insert_one({"id": str(_uuid.uuid4()), "organization_id": owner["org_id"],
                                   "email": "x@y.com", "role": "viewer", "token": inv_token,
                                   "status": "pending"})
        z = _zip(client.get("/api/org/export", headers=owner["headers"]))
        blob = b"".join(z.read(n) for n in z.namelist())
        assert pw_hash and pw_hash.encode() not in blob          # hash bcrypt absent
        assert mfa_secret.encode() not in blob                    # secret TOTP absent
        assert b"BACKUPCODE9999" not in blob                      # codes de secours absents
        assert inv_token.encode() not in blob                     # jeton d'invitation absent
        # members.json ne contient aucun champ sensible
        members = json.loads(z.read("json/members.json"))
        for m in members:
            assert "hashed_password" not in m and "secret" not in m and "backup_codes" not in m
        # invitations.json sans le champ token
        invs = json.loads(z.read("json/invitations.json"))
        assert all("token" not in i for i in invs)
