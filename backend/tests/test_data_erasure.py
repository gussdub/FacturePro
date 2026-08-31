"""Tests — effacement / anonymisation (Loi 25 art. 28.1), clients & employés."""
import os
import sys
import uuid as _uuid

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
    email = f"eff-{_uuid.uuid4().hex[:8]}@ex.com"
    r = client.post("/api/auth/register",
                    json={"email": email, "password": "effpass12345", "company_name": "Erase Test"})
    assert r.status_code == 200, r.text
    uid = r.json()["user"]["id"]
    org_id = (db.users.find_one({"id": uid}) or {}).get("organization_id")
    yield {"id": uid, "email": email, "org_id": org_id,
           "headers": {"Authorization": f"Bearer {r.json()['access_token']}"}}
    for coll in ("clients", "invoices", "quotes", "employees", "expenses",
                 "mileage_trips", "quote_tokens", "audit_logs"):
        db[coll].delete_many({"organization_id": org_id})
    db.users.delete_many({"organization_id": org_id})
    db.user_passwords.delete_one({"user_id": uid})
    db.organizations.delete_one({"id": org_id})


def _mk_client(org_id, name="Pêcherie Manicouagan"):
    cid = str(_uuid.uuid4())
    db.clients.insert_one({
        "id": cid, "organization_id": org_id, "name": name,
        "email": "contact@pecherie.qc.ca", "phone": "418-555-0100",
        "address": "12 rue du Quai", "city": "Baie-Comeau", "postal_code": "G4Z 1A1",
        "gst_number": "123456789RT0001", "qst_number": "1234567890TQ0001"})
    return cid


def _mk_invoice(org_id, client_id):
    iid = str(_uuid.uuid4())
    db.invoices.insert_one({
        "id": iid, "organization_id": org_id, "client_id": client_id,
        "invoice_number": "INV-EFF-1", "status": "sent", "total_cad": 500.0,
        "tax_registrations": {"company": {"gst": "999999999RT0001"},
                              "client": {"bn": "111", "gst": "123456789RT0001",
                                         "qst": "1234567890TQ0001", "hst": "", "neq": ""}}})
    return iid


class TestClientErasure:
    def test_client_with_invoice_is_anonymized_master_but_name_kept_on_invoice(self, owner):
        cid = _mk_client(owner["org_id"])
        iid = _mk_invoice(owner["org_id"], cid)
        r = client.post(f"/api/clients/{cid}/erase", headers=owner["headers"],
                        json={"confirm_name": "Pêcherie Manicouagan"})
        assert r.status_code == 200, r.text
        assert r.json()["outcome"] == "anonymized"
        assert r.json()["invoices_retained"] == 1
        # Maître anonymisé : nom pseudonymisé + RP effacées
        cl = db.clients.find_one({"id": cid}, {"_id": 0})
        assert cl["name"].startswith("Client anonymisé #")
        assert cl["anonymized"] is True and cl.get("anonymized_at")
        assert cl["email"] == "" and cl["phone"] == ""
        assert cl["gst_number"] == "" and cl["qst_number"] == ""
        # Facture émise : identité FIGÉE (nom conservé)
        inv = db.invoices.find_one({"id": iid}, {"_id": 0})
        assert inv["client_snapshot"]["name"] == "Pêcherie Manicouagan"
        assert inv["client_snapshot"]["city"] == "Baie-Comeau"
        # BLOCKING (revue) : les numéros de taxes du CLIENT sont effacés du snapshot de la facture,
        # ceux de l'ENTREPRISE (fournisseur, requis) sont conservés.
        assert inv["tax_registrations"]["client"]["gst"] == ""
        assert inv["tax_registrations"]["client"]["qst"] == ""
        assert inv["tax_registrations"]["client"]["bn"] == ""
        assert inv["tax_registrations"]["company"]["gst"] == "999999999RT0001"
        # Le rendu PDF/courriel utilise le snapshot → nom original conservé
        info = server._doc_client_info(inv, {"organization_id": owner["org_id"]})
        assert info["name"] == "Pêcherie Manicouagan"
        assert info.get("email", "") == ""  # contact effacé, pas figé

    def test_client_without_docs_is_hard_deleted(self, owner):
        cid = _mk_client(owner["org_id"], name="Client Sans Facture")
        r = client.post(f"/api/clients/{cid}/erase", headers=owner["headers"],
                        json={"confirm_name": "Client Sans Facture"})
        assert r.status_code == 200, r.text
        assert r.json()["outcome"] == "deleted"
        assert db.clients.find_one({"id": cid}) is None

    def test_wrong_confirmation_rejected(self, owner):
        cid = _mk_client(owner["org_id"])
        r = client.post(f"/api/clients/{cid}/erase", headers=owner["headers"],
                        json={"confirm_name": "mauvais nom"})
        assert r.status_code == 400
        assert db.clients.find_one({"id": cid, "anonymized": True}) is None

    def test_empty_confirmation_rejected_even_for_empty_named_client(self, owner):
        # MINOR (revue) : un client au nom vide ne doit pas être effaçable avec une confirmation vide.
        cid = str(_uuid.uuid4())
        db.clients.insert_one({"id": cid, "organization_id": owner["org_id"], "name": ""})
        r = client.post(f"/api/clients/{cid}/erase", headers=owner["headers"],
                        json={"confirm_name": ""})
        assert r.status_code == 400
        assert db.clients.find_one({"id": cid}) is not None

    def test_quote_conversion_after_erase_keeps_name_without_tax_leak(self, owner):
        # IMPORTANT (revue) : convertir un devis d'un client anonymisé ne doit PAS ressusciter
        # ses numéros de taxes ; le nom figé est conservé sur la facture convertie.
        cid = _mk_client(owner["org_id"], name="Acme Inc")
        qid = str(_uuid.uuid4())
        db.quotes.insert_one({
            "id": qid, "organization_id": owner["org_id"], "client_id": cid,
            "quote_number": "Q-EFF-1", "status": "pending",
            "items": [{"description": "Service", "quantity": 1, "unit_price": 100.0}],
            "subtotal": 100.0, "total": 100.0, "total_cad": 100.0, "currency": "CAD",
            "tax_registrations": {"company": {"gst": "999RT"},
                                  "client": {"bn": "", "gst": "123RT", "qst": "456TQ",
                                             "hst": "", "neq": ""}}})
        er = client.post(f"/api/clients/{cid}/erase", headers=owner["headers"],
                         json={"confirm_name": "Acme Inc"})
        assert er.status_code == 200 and er.json()["outcome"] == "anonymized"
        # Le devis a ses numéros client effacés à la source + identité figée
        q = db.quotes.find_one({"id": qid}, {"_id": 0})
        assert q["tax_registrations"]["client"]["gst"] == ""
        assert q["client_snapshot"]["name"] == "Acme Inc"
        # Conversion → facture neuve : pas de fuite de taxes, nom conservé
        conv = client.post(f"/api/quotes/{qid}/convert", headers=owner["headers"], json={})
        assert conv.status_code == 200, conv.text
        new_inv = conv.json()
        assert new_inv["tax_registrations"]["client"]["gst"] == ""
        assert new_inv["tax_registrations"]["company"]["gst"] == "999RT"
        assert new_inv.get("client_snapshot", {}).get("name") == "Acme Inc"

    def test_idempotent_on_already_anonymized(self, owner):
        cid = _mk_client(owner["org_id"])
        _mk_invoice(owner["org_id"], cid)
        client.post(f"/api/clients/{cid}/erase", headers=owner["headers"],
                    json={"confirm_name": "Pêcherie Manicouagan"})
        r2 = client.post(f"/api/clients/{cid}/erase", headers=owner["headers"],
                         json={"confirm_name": "peu importe"})
        assert r2.status_code == 200 and r2.json()["outcome"] == "already_anonymized"

    def test_member_forbidden(self, owner):
        cid = _mk_client(owner["org_id"])
        m_email = f"m-{_uuid.uuid4().hex[:8]}@ex.com"
        m_pw, m_uid = "memberpass123", str(_uuid.uuid4())
        db.users.insert_one({"id": m_uid, "email": m_email.lower(), "organization_id": owner["org_id"],
                             "role": "accountant", "is_active": True})
        db.user_passwords.insert_one({"user_id": m_uid, "hashed_password": server.hash_password(m_pw)})
        try:
            tok = client.post("/api/auth/login",
                              json={"email": m_email, "password": m_pw}).json()["access_token"]
            r = client.post(f"/api/clients/{cid}/erase",
                            headers={"Authorization": f"Bearer {tok}"},
                            json={"confirm_name": "Pêcherie Manicouagan"})
            assert r.status_code == 403
        finally:
            db.users.delete_one({"id": m_uid})
            db.user_passwords.delete_one({"user_id": m_uid})
            db.login_attempts.delete_one({"_id": server._login_attempt_key(m_email, "testclient")})

    def test_erasure_is_audited(self, owner):
        cid = _mk_client(owner["org_id"])
        client.post(f"/api/clients/{cid}/erase", headers=owner["headers"],
                    json={"confirm_name": "Pêcherie Manicouagan"})
        log = db.audit_logs.find_one({"organization_id": owner["org_id"], "action": "data.erasure"})
        assert log is not None and log.get("target_id") == cid


class TestEmployeeErasure:
    def test_employee_with_expense_is_anonymized(self, owner):
        eid = str(_uuid.uuid4())
        db.employees.insert_one({"id": eid, "organization_id": owner["org_id"], "name": "Jean Tremblay",
                                 "email": "jean@ex.com", "phone": "418-555-1", "is_active": True})
        db.expenses.insert_one({"id": str(_uuid.uuid4()), "organization_id": owner["org_id"],
                                "employee_id": eid, "amount_cad": 42.0, "expense_date": "2026-01-15"})
        r = client.post(f"/api/employees/{eid}/erase", headers=owner["headers"],
                        json={"confirm_name": "Jean Tremblay"})
        assert r.status_code == 200, r.text
        assert r.json()["outcome"] == "anonymized" and r.json()["expenses_retained"] == 1
        emp = db.employees.find_one({"id": eid}, {"_id": 0})
        assert emp["name"].startswith("Employé anonymisé #")
        assert emp["email"] == "" and emp["anonymized"] is True and emp["is_active"] is False
        # attribution fiscale conservée
        assert db.expenses.find_one({"employee_id": eid}) is not None

    def test_employee_without_docs_is_hard_deleted(self, owner):
        eid = str(_uuid.uuid4())
        db.employees.insert_one({"id": eid, "organization_id": owner["org_id"],
                                 "name": "Sans Trace", "is_active": True})
        r = client.post(f"/api/employees/{eid}/erase", headers=owner["headers"],
                        json={"confirm_name": "Sans Trace"})
        assert r.status_code == 200 and r.json()["outcome"] == "deleted"
        assert db.employees.find_one({"id": eid}) is None

    def test_wrong_confirmation_rejected(self, owner):
        eid = str(_uuid.uuid4())
        db.employees.insert_one({"id": eid, "organization_id": owner["org_id"],
                                 "name": "Marie Côté", "is_active": True})
        r = client.post(f"/api/employees/{eid}/erase", headers=owner["headers"],
                        json={"confirm_name": "Marie C"})
        assert r.status_code == 400
        assert db.employees.find_one({"id": eid, "anonymized": True}) is None
