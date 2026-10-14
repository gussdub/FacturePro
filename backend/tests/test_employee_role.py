"""Rôle « Employé » : crée des soumissions et des clients, ne modifie que les siens,
n'accède ni aux factures, ni aux dépenses, ni aux rapports, ni au grand livre, ni aux paramètres."""
import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))

import uuid
from datetime import datetime, timezone

import pytest
import server as server_module
from fastapi.testclient import TestClient
from server import (DEFAULT_ROLE_PERMISSIONS, _resolve_permissions, create_token)


@pytest.fixture(scope="module")
def client():
    return TestClient(server_module.app)


@pytest.fixture()
def org():
    """Org avec un owner et un employé. La matrice stockée NE contient PAS « employee »
    (cas des organisations créées avant ce rôle)."""
    db = server_module.db
    org_id = str(uuid.uuid4())
    owner_id, emp_id = f"own-{uuid.uuid4().hex[:8]}", f"emp-{uuid.uuid4().hex[:8]}"
    db.organizations.insert_one({
        "id": org_id, "name": "Employe Test Co", "owner_id": owner_id,
        "subscription_status": "active",
        "role_permissions": {"accountant": DEFAULT_ROLE_PERMISSIONS["accountant"],
                             "viewer": DEFAULT_ROLE_PERMISSIONS["viewer"]},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    for uid, role in ((owner_id, "owner"), (emp_id, "employee")):
        db.users.insert_one({"id": uid, "email": f"{uid}@test.local", "is_active": True,
                             "organization_id": org_id, "role": role})
    h = lambda uid: {"Authorization": f"Bearer {create_token(uid, 0)}"}
    yield {"id": org_id, "owner": h(owner_id), "emp": h(emp_id), "emp_id": emp_id}
    for coll in ("organizations",):
        db[coll].delete_many({"id": org_id})
    for coll in ("users",):
        db[coll].delete_many({"organization_id": org_id})
    for coll in ("clients", "quotes", "invoices"):
        db[coll].delete_many({"organization_id": org_id})


QUOTE = {"items": [{"description": "Inspection", "quantity": 1, "unit_price": 100}],
         "province": "QC"}


class TestEmployeePermissions:
    def test_defaults(self):
        assert set(DEFAULT_ROLE_PERMISSIONS["employee"]) == {
            "quotes:read", "quotes:write", "clients:read", "clients:write", "products:read"}

    def test_employee_defaults_when_absent_from_stored_matrix(self):
        org = {"role_permissions": {"accountant": ["expenses:read"]}}
        assert set(_resolve_permissions(org, "employee")) == set(DEFAULT_ROLE_PERMISSIONS["employee"])

    def test_stored_employee_matrix_wins(self):
        org = {"role_permissions": {"employee": ["quotes:read"]}}
        assert _resolve_permissions(org, "employee") == ["quotes:read"]

    def test_unknown_role_gets_nothing(self):
        assert _resolve_permissions({"role_permissions": {"boss": ["quotes:read"]}}, "boss") == []


class TestEmployeeEndpoints:
    def test_create_quote_and_client(self, client, org):
        r = client.post("/api/clients", json={"name": "Client E"}, headers=org["emp"])
        assert r.status_code == 200, r.text
        r = client.post("/api/quotes", json={**QUOTE, "client_id": r.json()["id"]}, headers=org["emp"])
        assert r.status_code == 200, r.text
        assert client.get("/api/quotes", headers=org["emp"]).status_code == 200
        assert client.get("/api/products", headers=org["emp"]).status_code == 200

    @pytest.mark.parametrize("path", ["/api/invoices", "/api/expenses", "/api/dashboard/stats",
                                      "/api/settings/company", "/api/employees"])
    def test_forbidden_areas(self, client, org, path):
        assert client.get(path, headers=org["emp"]).status_code == 403

    def test_can_edit_own_quote_not_others(self, client, org):
        own = client.post("/api/quotes", json=QUOTE, headers=org["emp"]).json()
        other = client.post("/api/quotes", json=QUOTE, headers=org["owner"]).json()
        assert client.put(f"/api/quotes/{own['id']}", json={"notes": "ok"},
                          headers=org["emp"]).status_code == 200
        assert client.put(f"/api/quotes/{other['id']}", json={"notes": "x"},
                          headers=org["emp"]).status_code == 404
        assert client.put(f"/api/quotes/{other['id']}/status", json={"status": "accepted"},
                          headers=org["emp"]).status_code == 404
        assert client.delete(f"/api/quotes/{other['id']}", headers=org["emp"]).status_code == 404
        # Le PDF d'une soumission d'autrui reste consultable (lecture).
        assert client.get(f"/api/quotes/{other['id']}/pdf", headers=org["emp"]).status_code == 200
        assert client.delete(f"/api/quotes/{own['id']}", headers=org["emp"]).status_code == 200

    def test_cannot_reassign_creator(self, client, org):
        own = client.post("/api/quotes", json=QUOTE, headers=org["owner"]).json()
        client.put(f"/api/quotes/{own['id']}", json={"created_by_user_id": org["emp_id"]},
                   headers=org["owner"])
        assert client.delete(f"/api/quotes/{own['id']}", headers=org["emp"]).status_code == 404

    def test_cannot_convert_to_invoice(self, client, org):
        own = client.post("/api/quotes", json=QUOTE, headers=org["emp"]).json()
        r = client.post(f"/api/quotes/{own['id']}/convert", json={}, headers=org["emp"])
        assert r.status_code == 403
        assert server_module.db.invoices.count_documents({"organization_id": org["id"]}) == 0

    def test_owner_still_converts(self, client, org):
        q = client.post("/api/quotes", json=QUOTE, headers=org["emp"]).json()
        assert client.post(f"/api/quotes/{q['id']}/convert", json={},
                           headers=org["owner"]).status_code == 200

    def test_can_edit_own_client_not_others(self, client, org):
        own = client.post("/api/clients", json={"name": "A"}, headers=org["emp"]).json()
        other = client.post("/api/clients", json={"name": "B"}, headers=org["owner"]).json()
        assert client.put(f"/api/clients/{own['id']}", json={"name": "A2"},
                          headers=org["emp"]).status_code == 200
        assert client.put(f"/api/clients/{other['id']}", json={"name": "x"},
                          headers=org["emp"]).status_code == 404
        assert client.delete(f"/api/clients/{other['id']}", headers=org["emp"]).status_code == 404


class TestTeamManagement:
    def test_invite_employee(self, client, org, monkeypatch):
        monkeypatch.setattr(server_module, "_send_invitation_email", lambda *a, **k: True)
        r = client.post("/api/org/invitations", json={"email": f"{uuid.uuid4().hex[:8]}@test.local",
                                                       "role": "employee"}, headers=org["owner"])
        assert r.status_code == 201, r.text
        server_module.db.invitations.delete_many({"organization_id": org["id"]})

    def test_change_member_role_to_employee(self, client, org):
        r = client.put(f"/api/org/members/{org['emp_id']}/role", json={"role": "employee"},
                       headers=org["owner"])
        assert r.status_code == 200

    def test_org_me_exposes_employee_matrix(self, client, org):
        rp = client.get("/api/org/me", headers=org["owner"]).json()["organization"]["role_permissions"]
        assert set(rp["employee"]) == set(DEFAULT_ROLE_PERMISSIONS["employee"])

    def test_edit_employee_matrix(self, client, org):
        r = client.put("/api/org/role-permissions",
                       json={"role": "employee", "permissions": ["quotes:read", "quotes:write",
                                                                 "clients:read", "clients:write",
                                                                 "products:read", "invoices:read"]},
                       headers=org["owner"])
        assert r.status_code == 200
        assert client.get("/api/invoices", headers=org["emp"]).status_code == 200
