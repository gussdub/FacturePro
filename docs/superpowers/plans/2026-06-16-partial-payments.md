# Partial Payments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permettre l'enregistrement de paiements partiels sur les factures (historique embarqué, statut `partial`, helpers backend, PDF en relevé, modal frontend, widget dashboard "Total à recevoir").

**Architecture:** Tableau `payments[]` embarqué dans chaque doc invoice (audit + atomique). Helper `_recompute_invoice_status` appelé après chaque modif pour transitionner sent → partial → paid. Endpoints POST/DELETE pour CRUD des paiements. Enrichissement `_enrich_invoice` ajoute `total_paid_cad` + `outstanding_cad` à la volée. PDF gagne une section "Paiements". Frontend ajoute modal + colonne Solde + carte Dashboard.

**Tech Stack:** FastAPI Python 3.11 + pymongo, React 18 CRA, pytest, ReportLab.

**Spec source:** [docs/superpowers/specs/2026-06-16-partial-payments-design.md](../specs/2026-06-16-partial-payments-design.md)

---

## File Structure

**Created:**
- `backend/tests/test_partial_payments.py` — tests unitaires (~110 lignes)
- `backend/tests/test_partial_payments_integration.py` — tests intégration HTTP (~250 lignes)
- `frontend/src/components/PaymentModal.js` — composant modal réutilisable (~180 lignes)

**Modified:**
- `backend/server.py` — 2 helpers (~30 lignes), 3 nouveaux endpoints (~80 lignes), GET invoices/{id} enrichi (~10 lignes), GET overdue update (~5 lignes), PDF section paiements (~60 lignes)
- `frontend/src/pages/InvoicesPage.js` — colonne Solde + bouton + import + state PaymentModal (~50 lignes)
- `frontend/src/pages/Dashboard.js` — nouveau `<OutstandingCard />` (~50 lignes)
- `CLAUDE.md` — changelog (~10 lignes)

---

## Task 1 — Helpers `_recompute_invoice_status` et `_enrich_invoice`

**Files:**
- Create: `backend/tests/test_partial_payments.py`
- Modify: `backend/server.py` (ajouter après les helpers de feature #5)

- [ ] **Step 1: Tests**

Créer `backend/tests/test_partial_payments.py` :

```python
"""Tests unitaires pour les paiements partiels (feature #6)."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "facturepro_test_unit")
os.environ.setdefault("JWT_SECRET", "test")

from server import _recompute_invoice_status, _enrich_invoice


class TestRecomputeInvoiceStatus:
    def test_no_payments_keeps_sent(self):
        inv = {"total": 100, "payments": [], "status": "sent"}
        assert _recompute_invoice_status(inv) == "sent"

    def test_no_payments_keeps_overdue(self):
        inv = {"total": 100, "payments": [], "status": "overdue"}
        assert _recompute_invoice_status(inv) == "overdue"

    def test_full_payment_returns_paid(self):
        inv = {"total": 100, "payments": [{"amount_cad": 100}], "status": "sent"}
        assert _recompute_invoice_status(inv) == "paid"

    def test_partial_payment_returns_partial(self):
        inv = {"total": 100, "payments": [{"amount_cad": 50}], "status": "sent"}
        assert _recompute_invoice_status(inv) == "partial"

    def test_multiple_payments_summing_to_total(self):
        inv = {"total": 100, "payments": [{"amount_cad": 60}, {"amount_cad": 40}], "status": "partial"}
        assert _recompute_invoice_status(inv) == "paid"

    def test_over_payment_returns_paid(self):
        inv = {"total": 100, "payments": [{"amount_cad": 150}], "status": "sent"}
        assert _recompute_invoice_status(inv) == "paid"

    def test_zero_total_keeps_status(self):
        inv = {"total": 0, "payments": [], "status": "sent"}
        assert _recompute_invoice_status(inv) == "sent"

    def test_missing_payments_field_treated_as_empty(self):
        inv = {"total": 100, "status": "sent"}
        assert _recompute_invoice_status(inv) == "sent"


class TestEnrichInvoice:
    def test_no_payments_outstanding_equals_total(self):
        inv = {"total": 100, "payments": []}
        result = _enrich_invoice(inv)
        assert result["total_paid_cad"] == 0
        assert result["outstanding_cad"] == 100

    def test_with_payments(self):
        inv = {"total": 100, "payments": [{"amount_cad": 30}, {"amount_cad": 20}]}
        result = _enrich_invoice(inv)
        assert result["total_paid_cad"] == 50
        assert result["outstanding_cad"] == 50

    def test_over_payment_clamps_outstanding_to_zero(self):
        inv = {"total": 100, "payments": [{"amount_cad": 150}]}
        result = _enrich_invoice(inv)
        assert result["outstanding_cad"] == 0

    def test_missing_payments_field(self):
        inv = {"total": 100}
        result = _enrich_invoice(inv)
        assert result["total_paid_cad"] == 0
        assert result["outstanding_cad"] == 100

    def test_returns_same_dict(self):
        inv = {"total": 100, "payments": []}
        result = _enrich_invoice(inv)
        # Mutation in-place : le doc original est aussi mis à jour
        assert result is inv
        assert inv["total_paid_cad"] == 0
```

- [ ] **Step 2: Vérifier l'échec**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
pytest tests/test_partial_payments.py -v 2>&1 | tail -10
```

Expected: ImportError.

- [ ] **Step 3: Implémenter dans `server.py`**

Localiser après les helpers de feature #5 (autour de `_merge_expense_groups`, vers la ligne 395+). Ajouter :

```python
# ─── Partial payments helpers (feature #6 du spec partial-payments) ───


def _recompute_invoice_status(invoice):
    """Détermine le statut basé sur le total payé vs total. Ne touche pas draft.

    - total_paid >= total et total > 0 → 'paid'
    - 0 < total_paid < total → 'partial'
    - total_paid == 0 → on conserve le statut actuel (sent ou overdue)
    """
    payments = invoice.get("payments", []) or []
    total_paid = sum(float(p.get("amount_cad", 0) or 0) for p in payments)
    total = float(invoice.get("total", 0) or 0)
    if total_paid >= total and total > 0:
        return "paid"
    if total_paid > 0:
        return "partial"
    return invoice.get("status", "sent")


def _enrich_invoice(invoice):
    """Ajoute total_paid_cad et outstanding_cad au doc invoice. Mutation in-place.
    Retourne le dict pour chaînage."""
    payments = invoice.get("payments", []) or []
    total_paid = round(sum(float(p.get("amount_cad", 0) or 0) for p in payments), 2)
    total = float(invoice.get("total", 0) or 0)
    invoice["total_paid_cad"] = total_paid
    invoice["outstanding_cad"] = round(max(0, total - total_paid), 2)
    return invoice
```

- [ ] **Step 4: Vérifier le succès**

```bash
pytest tests/test_partial_payments.py -v 2>&1 | tail -15
```

Expected: **13 passed** (8 status + 5 enrich).

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_partial_payments.py
git commit -m "feat(payments): helpers _recompute_invoice_status + _enrich_invoice"
```

---

## Task 2 — POST `/api/invoices/{id}/payments`

**Files:**
- Modify: `backend/server.py`
- Create: `backend/tests/test_partial_payments_integration.py`

- [ ] **Step 1: Créer les tests d'intégration**

Créer `backend/tests/test_partial_payments_integration.py` :

```python
"""Tests d'intégration HTTP pour les paiements partiels (feature #6)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("FACTUREPRO_BACKEND_URL", "http://localhost:8000").rstrip("/")
TEST_EMAIL = "gussdub@gmail.com"
TEST_PASSWORD = "testpass123"


@pytest.fixture(scope="module")
def auth():
    resp = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_test_invoice(auth, unit_price=574.88):
    """Helper : crée un client + invoice 'sent' et retourne (invoice_id, client_id)."""
    c = requests.post(f"{BASE_URL}/api/clients", headers=auth,
                       json={"name": f"Payment Test {os.urandom(4).hex()}"}).json()
    inv = requests.post(f"{BASE_URL}/api/invoices", headers=auth, json={
        "client_id": c["id"],
        "items": [{"description": "S", "quantity": 1, "unit_price": unit_price}],
        "province": "QC",
        "issue_date": "2099-04-15",
    }).json()
    requests.put(f"{BASE_URL}/api/invoices/{inv['id']}/status",
                 headers=auth, json={"status": "sent"})
    return inv["id"], c["id"]


class TestPostPayment:
    _cleanup = {"clients": set(), "invoices": set()}
    _auth_headers = None

    def test_partial_payment_sets_status_partial(self, auth):
        TestPostPayment._auth_headers = auth
        inv_id, c_id = _create_test_invoice(auth)
        TestPostPayment._cleanup["invoices"].add(inv_id)
        TestPostPayment._cleanup["clients"].add(c_id)
        resp = requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments",
                              headers=auth, json={
                                  "date": "2026-04-15", "amount_cad": 100,
                                  "method": "cheque", "reference": "1234"
                              })
        assert resp.status_code in (200, 201), resp.text
        body = resp.json()
        assert body["status"] == "partial"
        assert len(body["payments"]) == 1
        assert body["payments"][0]["amount_cad"] == 100
        assert body["total_paid_cad"] == 100
        assert body["outstanding_cad"] == 474.88

    def test_full_payment_sets_status_paid(self, auth):
        TestPostPayment._auth_headers = auth
        inv_id, c_id = _create_test_invoice(auth)
        TestPostPayment._cleanup["invoices"].add(inv_id)
        TestPostPayment._cleanup["clients"].add(c_id)
        resp = requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments",
                              headers=auth, json={
                                  "date": "2026-04-15", "amount_cad": 574.88,
                                  "method": "transfer"
                              })
        body = resp.json()
        assert body["status"] == "paid"
        assert body["outstanding_cad"] == 0

    def test_second_payment_completes_partial(self, auth):
        TestPostPayment._auth_headers = auth
        inv_id, c_id = _create_test_invoice(auth, unit_price=100)
        TestPostPayment._cleanup["invoices"].add(inv_id)
        TestPostPayment._cleanup["clients"].add(c_id)
        # Recompute le total réel avec taxes via GET
        get1 = requests.get(f"{BASE_URL}/api/invoices/{inv_id}", headers=auth).json()
        total = get1["total"]
        # 1er paiement = 30 % du total
        requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments", headers=auth,
                      json={"date": "2026-04-15", "amount_cad": round(total * 0.3, 2),
                            "method": "cheque"})
        # 2e paiement = le reste
        get2 = requests.get(f"{BASE_URL}/api/invoices/{inv_id}", headers=auth).json()
        outstanding = get2["outstanding_cad"]
        resp = requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments", headers=auth,
                              json={"date": "2026-04-30", "amount_cad": outstanding,
                                    "method": "transfer"})
        body = resp.json()
        assert body["status"] == "paid"
        assert body["outstanding_cad"] == 0
        assert len(body["payments"]) == 2

    def test_payment_assigns_id_and_created_at(self, auth):
        TestPostPayment._auth_headers = auth
        inv_id, c_id = _create_test_invoice(auth)
        TestPostPayment._cleanup["invoices"].add(inv_id)
        TestPostPayment._cleanup["clients"].add(c_id)
        resp = requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments", headers=auth,
                              json={"amount_cad": 50, "method": "cash"})
        body = resp.json()
        p = body["payments"][0]
        assert p["id"]  # uuid non vide
        assert p["created_at"]  # iso timestamp

    def test_payment_date_default_today(self, auth):
        TestPostPayment._auth_headers = auth
        inv_id, c_id = _create_test_invoice(auth)
        TestPostPayment._cleanup["invoices"].add(inv_id)
        TestPostPayment._cleanup["clients"].add(c_id)
        resp = requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments", headers=auth,
                              json={"amount_cad": 50, "method": "cash"})
        body = resp.json()
        p = body["payments"][0]
        # date est YYYY-MM-DD non-vide
        assert len(p["date"]) == 10 and p["date"][4] == "-" and p["date"][7] == "-"

    def test_payment_on_unknown_invoice_404(self, auth):
        TestPostPayment._auth_headers = auth
        resp = requests.post(f"{BASE_URL}/api/invoices/does-not-exist/payments",
                              headers=auth, json={"amount_cad": 50, "method": "cash"})
        assert resp.status_code == 404

    @classmethod
    def teardown_class(cls):
        if not cls._auth_headers:
            return
        for iid in cls._cleanup["invoices"]:
            try:
                requests.delete(f"{BASE_URL}/api/invoices/{iid}", headers=cls._auth_headers)
            except Exception:
                pass
        for cid in cls._cleanup["clients"]:
            try:
                requests.delete(f"{BASE_URL}/api/clients/{cid}", headers=cls._auth_headers)
            except Exception:
                pass
        cls._cleanup = {"clients": set(), "invoices": set()}
```

- [ ] **Step 2: Vérifier l'échec (uvicorn doit tourner)**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
lsof -ti:8000 | xargs kill 2>/dev/null
source .venv/bin/activate
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_partial_payments_integration.py::TestPostPayment -v 2>&1 | tail -15
```

Expected: 404 sur l'endpoint.

- [ ] **Step 3: Ajouter l'endpoint dans `server.py`**

Localiser une place après l'endpoint `PUT /api/invoices/{id}/status` (autour de la ligne 810+). Ajouter :

```python
@app.post("/api/invoices/{invoice_id}/payments")
def add_invoice_payment(invoice_id: str, body: dict,
                         current_user: User = Depends(get_current_user_with_access)):
    """Enregistre un paiement partiel ou complet. Recalcule le statut automatiquement."""
    invoice = db.invoices.find_one({"id": invoice_id, "user_id": current_user.id}, {"_id": 0})
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    payment = {
        "id": str(uuid.uuid4()),
        "date": body.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "amount_cad": float(body.get("amount_cad", 0) or 0),
        "method": body.get("method", "other"),
        "reference": body.get("reference", ""),
        "notes": body.get("notes", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    invoice.setdefault("payments", []).append(payment)
    new_status = _recompute_invoice_status(invoice)
    db.invoices.update_one(
        {"id": invoice_id, "user_id": current_user.id},
        {"$push": {"payments": payment}, "$set": {"status": new_status}}
    )
    fresh = db.invoices.find_one({"id": invoice_id}, {"_id": 0})
    return _enrich_invoice(fresh)
```

- [ ] **Step 4: Redémarrer + tester**

```bash
lsof -ti:8000 | xargs kill 2>/dev/null
source .venv/bin/activate
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_partial_payments.py tests/test_partial_payments_integration.py -v 2>&1 | tail -15
```

Expected: **19 passed** (13 unit + 6 POST).

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_partial_payments_integration.py
git commit -m "feat(payments): POST /api/invoices/{id}/payments avec recalcul statut"
```

---

## Task 3 — DELETE `/api/invoices/{id}/payments/{payment_id}`

**Files:**
- Modify: `backend/server.py`
- Modify: `backend/tests/test_partial_payments_integration.py`

- [ ] **Step 1: Ajouter les tests**

Append à `test_partial_payments_integration.py` :

```python
class TestDeletePayment:
    _cleanup = {"clients": set(), "invoices": set()}
    _auth_headers = None

    def test_delete_payment_recomputes_status(self, auth):
        TestDeletePayment._auth_headers = auth
        inv_id, c_id = _create_test_invoice(auth)
        TestDeletePayment._cleanup["invoices"].add(inv_id)
        TestDeletePayment._cleanup["clients"].add(c_id)
        # Crée un paiement partiel
        post = requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments",
                              headers=auth, json={"amount_cad": 100, "method": "cash"})
        payment_id = post.json()["payments"][0]["id"]
        # Vérifie partial
        assert post.json()["status"] == "partial"
        # Supprime
        resp = requests.delete(
            f"{BASE_URL}/api/invoices/{inv_id}/payments/{payment_id}", headers=auth)
        assert resp.status_code == 200
        body = resp.json()
        # Aucun paiement, revient à sent
        assert body["status"] == "sent"
        assert len(body["payments"]) == 0
        assert body["total_paid_cad"] == 0
        assert body["outstanding_cad"] == body["total"]

    def test_delete_one_of_two_payments_keeps_partial(self, auth):
        TestDeletePayment._auth_headers = auth
        inv_id, c_id = _create_test_invoice(auth)
        TestDeletePayment._cleanup["invoices"].add(inv_id)
        TestDeletePayment._cleanup["clients"].add(c_id)
        # 2 paiements partiels
        p1 = requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments",
                            headers=auth, json={"amount_cad": 100, "method": "cash"})
        p2 = requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments",
                            headers=auth, json={"amount_cad": 200, "method": "transfer"})
        # Supprime le premier
        pid = p1.json()["payments"][0]["id"]
        resp = requests.delete(
            f"{BASE_URL}/api/invoices/{inv_id}/payments/{pid}", headers=auth)
        body = resp.json()
        assert body["status"] == "partial"
        assert len(body["payments"]) == 1
        assert body["total_paid_cad"] == 200

    def test_delete_payment_from_paid_invoice_reverts_to_partial(self, auth):
        TestDeletePayment._auth_headers = auth
        inv_id, c_id = _create_test_invoice(auth)
        TestDeletePayment._cleanup["invoices"].add(inv_id)
        TestDeletePayment._cleanup["clients"].add(c_id)
        get = requests.get(f"{BASE_URL}/api/invoices/{inv_id}", headers=auth).json()
        total = get["total"]
        # 2 paiements qui soldent
        requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments",
                      headers=auth, json={"amount_cad": round(total * 0.7, 2), "method": "cheque"})
        p2 = requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments",
                            headers=auth, json={"amount_cad": round(total * 0.3, 2), "method": "transfer"})
        # Vérifie paid
        assert p2.json()["status"] == "paid"
        # Supprime le second
        pid = p2.json()["payments"][-1]["id"]
        resp = requests.delete(
            f"{BASE_URL}/api/invoices/{inv_id}/payments/{pid}", headers=auth)
        body = resp.json()
        assert body["status"] == "partial"

    def test_delete_unknown_payment_returns_invoice_unchanged(self, auth):
        TestDeletePayment._auth_headers = auth
        inv_id, c_id = _create_test_invoice(auth)
        TestDeletePayment._cleanup["invoices"].add(inv_id)
        TestDeletePayment._cleanup["clients"].add(c_id)
        # Supprime un id inconnu (idempotent, ne crash pas)
        resp = requests.delete(
            f"{BASE_URL}/api/invoices/{inv_id}/payments/does-not-exist", headers=auth)
        assert resp.status_code == 200

    def test_delete_on_unknown_invoice_404(self, auth):
        TestDeletePayment._auth_headers = auth
        resp = requests.delete(
            f"{BASE_URL}/api/invoices/no-such/payments/p1", headers=auth)
        assert resp.status_code == 404

    @classmethod
    def teardown_class(cls):
        if not cls._auth_headers:
            return
        for iid in cls._cleanup["invoices"]:
            try:
                requests.delete(f"{BASE_URL}/api/invoices/{iid}", headers=cls._auth_headers)
            except Exception:
                pass
        for cid in cls._cleanup["clients"]:
            try:
                requests.delete(f"{BASE_URL}/api/clients/{cid}", headers=cls._auth_headers)
            except Exception:
                pass
        cls._cleanup = {"clients": set(), "invoices": set()}
```

- [ ] **Step 2: Vérifier l'échec**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
pytest tests/test_partial_payments_integration.py::TestDeletePayment -v 2>&1 | tail -15
```

Expected: 404/405 sur l'endpoint.

- [ ] **Step 3: Ajouter l'endpoint dans `server.py`**

Localiser juste après `POST /api/invoices/{id}/payments` (ajouté en Task 2). Ajouter :

```python
@app.delete("/api/invoices/{invoice_id}/payments/{payment_id}")
def delete_invoice_payment(invoice_id: str, payment_id: str,
                            current_user: User = Depends(get_current_user_with_access)):
    """Supprime un paiement. Recalcule le statut."""
    invoice = db.invoices.find_one({"id": invoice_id, "user_id": current_user.id}, {"_id": 0})
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    payments = [p for p in invoice.get("payments", []) if p.get("id") != payment_id]
    invoice["payments"] = payments
    new_status = _recompute_invoice_status(invoice)
    db.invoices.update_one(
        {"id": invoice_id, "user_id": current_user.id},
        {"$set": {"payments": payments, "status": new_status}}
    )
    fresh = db.invoices.find_one({"id": invoice_id}, {"_id": 0})
    return _enrich_invoice(fresh)
```

- [ ] **Step 4: Redémarrer + tester**

```bash
lsof -ti:8000 | xargs kill 2>/dev/null
source .venv/bin/activate
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_partial_payments.py tests/test_partial_payments_integration.py -v 2>&1 | tail -10
```

Expected: 24 passed (13 unit + 6 POST + 5 DELETE).

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_partial_payments_integration.py
git commit -m "feat(payments): DELETE /api/invoices/{id}/payments/{payment_id}"
```

---

## Task 4 — Enrichir GET `/api/invoices` et `/api/invoices/{id}` + status `partial` dans overdue

**Files:**
- Modify: `backend/server.py`
- Modify: `backend/tests/test_partial_payments_integration.py`

- [ ] **Step 1: Tests**

Append :

```python
class TestGetEnriched:
    _cleanup = {"clients": set(), "invoices": set()}
    _auth_headers = None

    def test_get_invoices_includes_enriched_fields(self, auth):
        TestGetEnriched._auth_headers = auth
        inv_id, c_id = _create_test_invoice(auth)
        TestGetEnriched._cleanup["invoices"].add(inv_id)
        TestGetEnriched._cleanup["clients"].add(c_id)
        requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments",
                      headers=auth, json={"amount_cad": 100, "method": "cash"})
        invoices = requests.get(f"{BASE_URL}/api/invoices", headers=auth).json()
        target = next(i for i in invoices if i["id"] == inv_id)
        assert "total_paid_cad" in target
        assert "outstanding_cad" in target
        assert target["total_paid_cad"] == 100

    def test_get_single_invoice_includes_enriched_fields(self, auth):
        TestGetEnriched._auth_headers = auth
        inv_id, c_id = _create_test_invoice(auth)
        TestGetEnriched._cleanup["invoices"].add(inv_id)
        TestGetEnriched._cleanup["clients"].add(c_id)
        requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments",
                      headers=auth, json={"amount_cad": 200, "method": "cheque"})
        body = requests.get(f"{BASE_URL}/api/invoices/{inv_id}", headers=auth).json()
        assert body["total_paid_cad"] == 200
        assert "outstanding_cad" in body

    @classmethod
    def teardown_class(cls):
        if not cls._auth_headers:
            return
        for iid in cls._cleanup["invoices"]:
            try:
                requests.delete(f"{BASE_URL}/api/invoices/{iid}", headers=cls._auth_headers)
            except Exception:
                pass
        for cid in cls._cleanup["clients"]:
            try:
                requests.delete(f"{BASE_URL}/api/clients/{cid}", headers=cls._auth_headers)
            except Exception:
                pass
        cls._cleanup = {"clients": set(), "invoices": set()}
```

- [ ] **Step 2: Vérifier l'échec**

```bash
pytest tests/test_partial_payments_integration.py::TestGetEnriched -v 2>&1 | tail -10
```

Expected: KeyError sur `total_paid_cad`.

- [ ] **Step 3: Modifier les endpoints dans `server.py`**

Localiser `@app.get("/api/invoices")` (sans `{id}`, retourne la liste). Le code actuel ressemble à :

```python
@app.get("/api/invoices")
def get_invoices(current_user: User = Depends(get_current_user_with_access)):
    invoices = list(db.invoices.find({"user_id": current_user.id}, {"_id": 0}))
    return invoices
```

Modifier en :

```python
@app.get("/api/invoices")
def get_invoices(current_user: User = Depends(get_current_user_with_access)):
    invoices = list(db.invoices.find({"user_id": current_user.id}, {"_id": 0}))
    return [_enrich_invoice(inv) for inv in invoices]
```

Localiser `@app.get("/api/invoices/{invoice_id}")` (ajouté en feature #2). Modifier le return :

```python
@app.get("/api/invoices/{invoice_id}")
def get_invoice(invoice_id: str, current_user: User = Depends(get_current_user_with_access)):
    invoice = db.invoices.find_one({"id": invoice_id, "user_id": current_user.id}, {"_id": 0})
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    return _enrich_invoice(invoice)
```

- [ ] **Step 4: Tester**

```bash
lsof -ti:8000 | xargs kill 2>/dev/null
source .venv/bin/activate
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_partial_payments.py tests/test_partial_payments_integration.py -v 2>&1 | tail -10
```

Expected: 26 passed (24 + 2 enrich).

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_partial_payments_integration.py
git commit -m "feat(payments): GET invoices et /{id} retournent total_paid_cad + outstanding_cad"
```

---

## Task 5 — `GET /api/dashboard/overdue` inclut `partial` + nouveau `GET /api/dashboard/outstanding`

**Files:**
- Modify: `backend/server.py`
- Modify: `backend/tests/test_partial_payments_integration.py`

- [ ] **Step 1: Tests**

Append :

```python
class TestDashboardOutstanding:
    _cleanup = {"clients": set(), "invoices": set()}
    _auth_headers = None

    def test_outstanding_endpoint_returns_total(self, auth):
        TestDashboardOutstanding._auth_headers = auth
        inv_id, c_id = _create_test_invoice(auth)
        TestDashboardOutstanding._cleanup["invoices"].add(inv_id)
        TestDashboardOutstanding._cleanup["clients"].add(c_id)
        before = requests.get(f"{BASE_URL}/api/dashboard/outstanding", headers=auth).json()
        before_total = before["total_outstanding_cad"]
        # Crée un paiement partiel
        requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments",
                      headers=auth, json={"amount_cad": 100, "method": "cash"})
        after = requests.get(f"{BASE_URL}/api/dashboard/outstanding", headers=auth).json()
        # Le total doit avoir baissé de 100 (le solde restant a baissé)
        assert round(before_total - after["total_outstanding_cad"], 2) == 100.00

    def test_outstanding_excludes_paid(self, auth):
        TestDashboardOutstanding._auth_headers = auth
        inv_id, c_id = _create_test_invoice(auth)
        TestDashboardOutstanding._cleanup["invoices"].add(inv_id)
        TestDashboardOutstanding._cleanup["clients"].add(c_id)
        get = requests.get(f"{BASE_URL}/api/invoices/{inv_id}", headers=auth).json()
        before = requests.get(f"{BASE_URL}/api/dashboard/outstanding", headers=auth).json()
        # Solder
        requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments", headers=auth,
                      json={"amount_cad": get["total"], "method": "transfer"})
        after = requests.get(f"{BASE_URL}/api/dashboard/outstanding", headers=auth).json()
        # Total a baissé d'au moins le total de la facture
        assert before["total_outstanding_cad"] - after["total_outstanding_cad"] >= get["total"] - 0.01

    @classmethod
    def teardown_class(cls):
        if not cls._auth_headers:
            return
        for iid in cls._cleanup["invoices"]:
            try:
                requests.delete(f"{BASE_URL}/api/invoices/{iid}", headers=cls._auth_headers)
            except Exception:
                pass
        for cid in cls._cleanup["clients"]:
            try:
                requests.delete(f"{BASE_URL}/api/clients/{cid}", headers=cls._auth_headers)
            except Exception:
                pass
        cls._cleanup = {"clients": set(), "invoices": set()}
```

- [ ] **Step 2: Vérifier l'échec**

```bash
pytest tests/test_partial_payments_integration.py::TestDashboardOutstanding -v 2>&1 | tail -10
```

Expected: 404.

- [ ] **Step 3: Modifier `/api/dashboard/overdue` + ajouter `/api/dashboard/outstanding`**

Localiser `@app.get("/api/dashboard/overdue")` (autour de la ligne 1450). Modifier le filtre Mongo pour inclure `partial` :

```python
invoices = list(db.invoices.find(
    {"user_id": current_user.id, "status": {"$in": ["sent", "partial", "overdue"]}},
    {"_id": 0}
))
```

(L'ancienne version utilisait `{"$nin": ["paid"]}` qui incluait `draft` — on resserre maintenant.)

Enrichir chaque ligne renvoyée avec `outstanding_cad` (réutiliser `_enrich_invoice` ou calculer inline) :

```python
for inv in invoices:
    _enrich_invoice(inv)
```

Ajouter le nouveau endpoint juste après :

```python
@app.get("/api/dashboard/outstanding")
def get_dashboard_outstanding(current_user: User = Depends(get_current_user_with_access)):
    """Total des soldes restants pour les invoices non-finalisées."""
    invoices = list(db.invoices.find({
        "user_id": current_user.id,
        "status": {"$in": ["sent", "partial", "overdue"]},
    }, {"_id": 0}))
    total = 0.0
    for inv in invoices:
        payments = inv.get("payments", []) or []
        paid = sum(float(p.get("amount_cad", 0) or 0) for p in payments)
        total += max(0, float(inv.get("total", 0) or 0) - paid)
    return {"total_outstanding_cad": round(total, 2), "invoice_count": len(invoices)}
```

- [ ] **Step 4: Tester**

```bash
lsof -ti:8000 | xargs kill 2>/dev/null
source .venv/bin/activate
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_partial_payments.py tests/test_partial_payments_integration.py -v 2>&1 | tail -10
```

Expected: 28 passed (26 + 2 dashboard).

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_partial_payments_integration.py
git commit -m "feat(payments): GET /api/dashboard/outstanding + overdue inclut partial"
```

---

## Task 6 — PDF facture : section "Paiements"

**Files:**
- Modify: `backend/server.py` (fonction `generate_document_pdf`)

- [ ] **Step 1: Trouver l'endroit dans `generate_document_pdf`**

```bash
grep -n "footer\|Merci\|generate_document_pdf" backend/server.py | head
```

Repérer la ligne juste avant le footer "Merci…" — c'est là qu'on insère la section Paiements.

- [ ] **Step 2: Ajouter le bloc**

Juste avant le footer `Merci pour votre confiance !`, AJOUTER :

```python
    # Section Paiements (feature #6) — seulement pour invoices avec paiements
    payments = document.get("payments", []) or []
    if doc_type == "invoice" and payments:
        method_labels = {
            "cash": "Comptant", "cheque": "Chèque", "transfer": "Virement",
            "card": "Carte", "etransfer": "Virement Interac",
            "stripe": "Stripe", "other": "Autre",
        }
        elements.append(Spacer(1, 0.25*inch))
        elements.append(Paragraph("<b>Paiements reçus</b>", company_style))
        elements.append(Spacer(1, 6))
        pay_rows = [["Date", "Méthode", "Référence", "Montant"]]
        total_paid_pdf = 0.0
        for p in payments:
            pay_rows.append([
                p.get("date", ""),
                method_labels.get(p.get("method", "other"), p.get("method", "")),
                p.get("reference", "") or "—",
                f"{float(p.get('amount_cad', 0)):.2f} $",
            ])
            total_paid_pdf += float(p.get("amount_cad", 0) or 0)
        outstanding_pdf = max(0, float(document.get("total", 0) or 0) - total_paid_pdf)
        pay_rows.append(["", "", "Total payé :", f"{total_paid_pdf:.2f} $"])
        pay_rows.append(["", "", "Solde restant :", f"{outstanding_pdf:.2f} $"])
        pay_table = Table(pay_rows, colWidths=[1.2*inch, 1.4*inch, 2.4*inch, 1.2*inch])
        pay_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#f8fafb')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#e5e7eb')),
            ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('FONTNAME', (2, -2), (-1, -1), 'Helvetica-Bold'),  # lignes totaux
            ('TEXTCOLOR', (2, -1), (-1, -1), HexColor('#dc2626') if outstanding_pdf > 0 else HexColor('#059669')),
        ]))
        elements.append(pay_table)
```

- [ ] **Step 3: Test manuel + nouveau test**

Tester manuellement : créer une facture, enregistrer un paiement, télécharger le PDF :

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
   -H "Content-Type: application/json" \
   -d '{"email":"gussdub@gmail.com","password":"testpass123"}' \
   | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
# Trouver une facture existante
INVOICE_ID=$(curl -s http://localhost:8000/api/invoices -H "Authorization: Bearer $TOKEN" | python -c "import sys,json;print(json.load(sys.stdin)[0]['id'])")
# Ajouter un paiement
curl -s -X POST http://localhost:8000/api/invoices/$INVOICE_ID/payments \
   -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
   -d '{"amount_cad": 50, "method": "cheque", "reference": "test"}' > /dev/null
# Télécharger PDF
curl -s http://localhost:8000/api/invoices/$INVOICE_ID/pdf \
   -H "Authorization: Bearer $TOKEN" -o /tmp/test-with-payment.pdf
file /tmp/test-with-payment.pdf
```

Expected: `PDF document, version 1.x`.

Ajouter le test d'intégration au fichier `test_partial_payments_integration.py` :

```python
class TestPdfWithPayments:
    _cleanup = {"clients": set(), "invoices": set()}
    _auth_headers = None

    def test_pdf_with_payments_renders(self, auth):
        TestPdfWithPayments._auth_headers = auth
        inv_id, c_id = _create_test_invoice(auth)
        TestPdfWithPayments._cleanup["invoices"].add(inv_id)
        TestPdfWithPayments._cleanup["clients"].add(c_id)
        requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments",
                      headers=auth, json={"amount_cad": 100, "method": "cheque",
                                          "reference": "Test1234"})
        resp = requests.get(f"{BASE_URL}/api/invoices/{inv_id}/pdf", headers=auth)
        assert resp.status_code == 200
        assert resp.content[:4] == b"%PDF"
        assert len(resp.content) > 2000

    @classmethod
    def teardown_class(cls):
        if not cls._auth_headers:
            return
        for iid in cls._cleanup["invoices"]:
            try:
                requests.delete(f"{BASE_URL}/api/invoices/{iid}", headers=cls._auth_headers)
            except Exception:
                pass
        for cid in cls._cleanup["clients"]:
            try:
                requests.delete(f"{BASE_URL}/api/clients/{cid}", headers=cls._auth_headers)
            except Exception:
                pass
        cls._cleanup = {"clients": set(), "invoices": set()}
```

- [ ] **Step 4: Tester l'ensemble**

```bash
pytest tests/test_partial_payments.py tests/test_partial_payments_integration.py -v 2>&1 | tail -10
```

Expected: 29 passed (28 + 1 PDF).

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_partial_payments_integration.py
git commit -m "feat(payments): PDF facture inclut section Paiements quand non-vide"
```

---

## Task 7 — Frontend `<PaymentModal />`

**Files:**
- Create: `frontend/src/components/PaymentModal.js`

- [ ] **Step 1: Créer le composant**

Créer `frontend/src/components/PaymentModal.js` :

```javascript
import React, { useState } from 'react';
import axios from 'axios';
import { BACKEND_URL } from '../config';

const METHODS = [
  { value: 'cash', label: 'Comptant' },
  { value: 'cheque', label: 'Chèque' },
  { value: 'transfer', label: 'Virement' },
  { value: 'card', label: 'Carte' },
  { value: 'etransfer', label: 'Virement Interac' },
  { value: 'stripe', label: 'Stripe' },
  { value: 'other', label: 'Autre' },
];

const todayIso = () => new Date().toISOString().slice(0, 10);
const fmt = v => (v || 0).toLocaleString('fr-CA', { style: 'currency', currency: 'CAD' });

function PaymentModal({ invoice, onClose, onSaved }) {
  const [date, setDate] = useState(todayIso());
  const [amount, setAmount] = useState(String(invoice.outstanding_cad ?? invoice.total ?? 0));
  const [method, setMethod] = useState('cheque');
  const [reference, setReference] = useState('');
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);
  const [local, setLocal] = useState(invoice);

  const refresh = (updatedInvoice) => {
    setLocal(updatedInvoice);
    setAmount(String(updatedInvoice.outstanding_cad ?? 0));
    if (onSaved) onSaved(updatedInvoice);
  };

  const save = async () => {
    const amt = parseFloat(amount);
    if (!amt || amt <= 0) return;
    setBusy(true);
    try {
      const token = localStorage.getItem('access_token');
      const resp = await axios.post(
        `${BACKEND_URL}/api/invoices/${local.id}/payments`,
        { date, amount_cad: amt, method, reference, notes },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      refresh(resp.data);
      setReference('');
      setNotes('');
    } finally {
      setBusy(false);
    }
  };

  const remove = async (paymentId) => {
    if (!window.confirm('Supprimer ce paiement ?')) return;
    setBusy(true);
    try {
      const token = localStorage.getItem('access_token');
      const resp = await axios.delete(
        `${BACKEND_URL}/api/invoices/${local.id}/payments/${paymentId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      refresh(resp.data);
    } finally {
      setBusy(false);
    }
  };

  const overlay = {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
  };
  const modal = {
    background: 'white', borderRadius: 8, padding: 24, maxWidth: 600, width: '90%',
    maxHeight: '90vh', overflow: 'auto', boxShadow: '0 10px 30px rgba(0,0,0,0.2)',
  };
  const label = { display: 'block', fontSize: 12, fontWeight: 500, color: '#374151', marginBottom: 4 };
  const input = {
    width: '100%', padding: '8px 10px', border: '1px solid #d1d5db',
    borderRadius: 6, fontSize: 13, boxSizing: 'border-box',
  };

  return (
    <div style={overlay} onClick={onClose}>
      <div style={modal} onClick={e => e.stopPropagation()}>
        <h3 style={{ marginTop: 0 }}>Paiements — {local.invoice_number}</h3>

        <div style={{ background: '#f9fafb', padding: 12, borderRadius: 6, marginBottom: 16 }}>
          <div>Total facture : <strong>{fmt(local.total)}</strong></div>
          <div>Total payé : <strong style={{ color: '#059669' }}>{fmt(local.total_paid_cad)}</strong></div>
          <div>Solde restant : <strong style={{ color: (local.outstanding_cad ?? local.total) > 0 ? '#dc2626' : '#059669' }}>
            {fmt(local.outstanding_cad ?? local.total)}
          </strong></div>
        </div>

        <h4 style={{ marginBottom: 8 }}>Historique</h4>
        {(local.payments || []).length === 0 ? (
          <p style={{ color: '#6b7280', fontSize: 13 }}>Aucun paiement enregistré.</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 16 }}>
            <tbody>
              {local.payments.map(p => (
                <tr key={p.id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                  <td style={{ padding: 6, fontSize: 13 }}>{p.date}</td>
                  <td style={{ padding: 6, fontSize: 13 }}>
                    {METHODS.find(m => m.value === p.method)?.label || p.method}
                  </td>
                  <td style={{ padding: 6, fontSize: 12, color: '#6b7280' }}>{p.reference || '—'}</td>
                  <td style={{ padding: 6, fontSize: 13, textAlign: 'right' }}>{fmt(p.amount_cad)}</td>
                  <td style={{ padding: 6, textAlign: 'right' }}>
                    <button onClick={() => remove(p.id)} disabled={busy}
                      style={{ background: 'none', border: 0, color: '#dc2626', cursor: 'pointer', fontSize: 16 }}
                      aria-label="Supprimer">×</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {(local.outstanding_cad === undefined || local.outstanding_cad > 0) && (
          <>
            <h4 style={{ marginBottom: 8 }}>Enregistrer un paiement</h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div>
                <label style={label}>Date</label>
                <input type="date" value={date} onChange={e => setDate(e.target.value)} style={input} />
              </div>
              <div>
                <label style={label}>Montant ($)</label>
                <input type="number" step="0.01" min="0" value={amount}
                  onChange={e => setAmount(e.target.value)} style={input} />
              </div>
              <div>
                <label style={label}>Méthode</label>
                <select value={method} onChange={e => setMethod(e.target.value)} style={input}>
                  {METHODS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
                </select>
              </div>
              <div>
                <label style={label}>Référence</label>
                <input type="text" value={reference} onChange={e => setReference(e.target.value)}
                  placeholder="Chèque #1234" style={input} />
              </div>
            </div>
            <div style={{ marginTop: 10 }}>
              <label style={label}>Notes</label>
              <input type="text" value={notes} onChange={e => setNotes(e.target.value)} style={input} />
            </div>
          </>
        )}

        <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          {(local.outstanding_cad === undefined || local.outstanding_cad > 0) && (
            <button onClick={save} disabled={busy}
              style={{ padding: '10px 18px', background: '#00A08C', color: 'white',
                       border: 0, borderRadius: 6, cursor: 'pointer' }}>
              {busy ? '...' : 'Enregistrer'}
            </button>
          )}
          <button onClick={onClose}
            style={{ padding: '10px 18px', background: '#e5e7eb', color: '#1f2937',
                     border: 0, borderRadius: 6, cursor: 'pointer' }}>
            Fermer
          </button>
        </div>
      </div>
    </div>
  );
}

export default PaymentModal;
```

- [ ] **Step 2: Build**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
npx --no-install react-scripts build 2>&1 | tail -10
```

Expected: Compiled successfully.

- [ ] **Step 3: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add frontend/src/components/PaymentModal.js
git commit -m "feat(payments): composant PaymentModal réutilisable"
```

---

## Task 8 — `InvoicesPage.js` : colonne Solde + bouton + intégration modal

**Files:**
- Modify: `frontend/src/pages/InvoicesPage.js`

- [ ] **Step 1: Lire la structure actuelle**

```bash
grep -n "useState\|colonne\|<td\|payments\|Total" frontend/src/pages/InvoicesPage.js | head -30
```

Repérer : (a) où est rendu le tableau des factures, (b) la cellule "Total".

- [ ] **Step 2: Ajouter import + state**

En haut du fichier, après les imports existants :

```javascript
import PaymentModal from '../components/PaymentModal';
```

Dans le composant, ajouter state :

```javascript
const [paymentInvoice, setPaymentInvoice] = useState(null);
```

- [ ] **Step 3: Ajouter la colonne "Solde" + bouton**

Dans l'entête du tableau, après la cellule `<th>Total</th>`, ajouter :

```jsx
<th>Solde</th>
```

Dans chaque ligne (probablement dans un `.map()`), après la cellule du total, ajouter :

```jsx
<td>{(invoice.outstanding_cad ?? invoice.total ?? 0).toLocaleString('fr-CA', { style: 'currency', currency: 'CAD' })}</td>
```

Dans la cellule Actions, ajouter un bouton "Paiement" qui ouvre le modal :

```jsx
<button onClick={() => setPaymentInvoice(invoice)}
  style={{ padding: '4px 10px', background: '#00A08C', color: 'white',
           border: 0, borderRadius: 4, cursor: 'pointer', fontSize: 12,
           marginRight: 4 }}>
  Paiement
</button>
```

- [ ] **Step 4: Monter le modal en bas du composant**

Juste avant le `return` final OU à la fin du JSX (après le tableau), ajouter le modal conditionnel :

```jsx
{paymentInvoice && (
  <PaymentModal
    invoice={paymentInvoice}
    onClose={() => setPaymentInvoice(null)}
    onSaved={(updated) => {
      // Mettre à jour la liste locale avec le doc enrichi
      setInvoices(invoices.map(i => i.id === updated.id ? updated : i));
      setPaymentInvoice(updated);
    }}
  />
)}
```

(Adapter `setInvoices`/`invoices` au nom réel du state des factures.)

- [ ] **Step 5: Build**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
npx --no-install react-scripts build 2>&1 | tail -10
```

Expected: Compiled successfully.

- [ ] **Step 6: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add frontend/src/pages/InvoicesPage.js
git commit -m "feat(payments): InvoicesPage colonne Solde + bouton Paiement + intégration modal"
```

---

## Task 9 — Dashboard : nouveau widget "Total à recevoir"

**Files:**
- Modify: `frontend/src/pages/Dashboard.js`

- [ ] **Step 1: Lire la structure du Dashboard**

```bash
grep -n "useState\|useEffect\|axios\|carte\|stat\|KPI" frontend/src/pages/Dashboard.js | head -20
```

- [ ] **Step 2: Ajouter le state + fetch**

Ajouter à `Dashboard.js` :

```javascript
const [outstanding, setOutstanding] = useState({ total_outstanding_cad: 0, invoice_count: 0 });

useEffect(() => {
  const token = localStorage.getItem('access_token');
  axios.get(`${BACKEND_URL}/api/dashboard/outstanding`, {
    headers: { Authorization: `Bearer ${token}` }
  })
    .then(resp => setOutstanding(resp.data))
    .catch(() => {});
}, []);
```

(Adapter `BACKEND_URL`/imports au pattern existant du fichier.)

- [ ] **Step 3: Ajouter la carte JSX**

Insérer la carte dans la grille de KPIs existante :

```jsx
<div style={{
  background: 'white', padding: 20, borderRadius: 8,
  boxShadow: '0 1px 3px rgba(0,0,0,0.06)', cursor: 'pointer',
}}
onClick={() => navigate && navigate('/invoices')}>
  <div style={{ fontSize: 13, color: '#6b7280', fontWeight: 500 }}>Total à recevoir</div>
  <div style={{ fontSize: 24, fontWeight: 700, color: '#00A08C', marginTop: 6 }}>
    {(outstanding.total_outstanding_cad || 0).toLocaleString('fr-CA', { style: 'currency', currency: 'CAD' })}
  </div>
  <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 4 }}>
    {outstanding.invoice_count} facture{outstanding.invoice_count > 1 ? 's' : ''}
  </div>
</div>
```

Placer cette carte à côté des autres KPIs existants. Si pas de `navigate`, omettre le `onClick` (ne pas casser).

- [ ] **Step 4: Build**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
npx --no-install react-scripts build 2>&1 | tail -10
```

Expected: Compiled successfully.

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add frontend/src/pages/Dashboard.js
git commit -m "feat(payments): Dashboard carte 'Total à recevoir'"
```

---

## Task 10 — E2E + push prod + CLAUDE.md

- [ ] **Step 1: Toute la batterie**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
lsof -ti:8000 | xargs kill 2>/dev/null
source .venv/bin/activate
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_tax_numbers.py tests/test_tax_registrations_integration.py tests/test_expense_categories.py tests/test_expense_categories_integration.py tests/test_tax_report.py tests/test_tax_report_integration.py tests/test_pnl_report.py tests/test_pnl_report_integration.py tests/test_partial_payments.py tests/test_partial_payments_integration.py -v 2>&1 | tail -10
```

Expected: ~166 tests pass.

- [ ] **Step 2: E2E HTTP — flow paiement complet**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
   -H "Content-Type: application/json" \
   -d '{"email":"gussdub@gmail.com","password":"testpass123"}' \
   | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

echo "=== Dashboard outstanding initial ==="
curl -s http://localhost:8000/api/dashboard/outstanding -H "Authorization: Bearer $TOKEN"

echo "=== Trouver une invoice ==="
INVOICE_ID=$(curl -s http://localhost:8000/api/invoices -H "Authorization: Bearer $TOKEN" | python -c "import sys,json;d=json.load(sys.stdin);print(d[0]['id'] if d else '')")
echo "Invoice: $INVOICE_ID"

echo "=== POST paiement partiel ==="
curl -s -X POST http://localhost:8000/api/invoices/$INVOICE_ID/payments \
   -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
   -d '{"amount_cad": 50, "method": "cheque", "reference": "E2E"}' | python -m json.tool | grep -E "status|outstanding|total_paid"

echo "=== PDF avec paiement ==="
curl -s http://localhost:8000/api/invoices/$INVOICE_ID/pdf \
   -H "Authorization: Bearer $TOKEN" -o /tmp/inv-paid.pdf
file /tmp/inv-paid.pdf

# Cleanup : supprimer le paiement test
PID=$(curl -s http://localhost:8000/api/invoices/$INVOICE_ID -H "Authorization: Bearer $TOKEN" | python -c "import sys,json;d=json.load(sys.stdin);print(d['payments'][-1]['id'] if d.get('payments') else '')")
curl -s -X DELETE http://localhost:8000/api/invoices/$INVOICE_ID/payments/$PID -H "Authorization: Bearer $TOKEN" > /dev/null
echo "Cleanup done"
```

Verify : status `partial` après POST, PDF avec magic bytes.

- [ ] **Step 3: Stop local backend**

```bash
lsof -ti:8000 | xargs kill 2>/dev/null
```

- [ ] **Step 4: Update CLAUDE.md**

Append :

```markdown

- **2026-06-16 — Acomptes et paiements partiels (feature #6)**
  - Champ `payments[]` embarqué sur invoices + nouveau statut `partial`
  - 2 endpoints CRUD : `POST /api/invoices/{id}/payments`, `DELETE /api/invoices/{id}/payments/{pid}`
  - GET invoices / `/{id}` enrichis avec `total_paid_cad` + `outstanding_cad`
  - Dashboard overdue inclut maintenant `partial` ; nouvelle carte "Total à recevoir" (`GET /api/dashboard/outstanding`)
  - PDF de facture : section "Paiements reçus" + total payé + solde restant si paiements présents → la facture devient un relevé
  - Frontend : modal `<PaymentModal />` depuis InvoicesPage, colonne "Solde" ajoutée
  - Limitation v1 : paiements en CAD uniquement, pas d'édition (suppr + ré-enregistrer), pas de soft-delete
  - Spec : `docs/superpowers/specs/2026-06-16-partial-payments-design.md`
  - Plan : `docs/superpowers/plans/2026-06-16-partial-payments.md`
```

- [ ] **Step 5: Push prod**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git log origin/main..HEAD --oneline
git add CLAUDE.md
git commit -m "docs: changelog feature #6 (paiements partiels)"
git push origin main 2>&1 | tail -5
```

- [ ] **Step 6: Verify prod**

```bash
sleep 180
curl -s -m 90 https://facturepro-backend-dkvn.onrender.com/api/health
echo
curl -sI -m 30 https://facturepro.ca | head -3
```

Expected: backend healthy, frontend 308.

---

## Récap fichiers touchés

| Fichier | Tasks | Nature |
|---|---|---|
| `backend/server.py` | 1, 2, 3, 4, 5, 6 | Modif (2 helpers + 3 endpoints + 3 endpoints modifiés + PDF) |
| `backend/tests/test_partial_payments.py` | 1 | Nouveau (unit) |
| `backend/tests/test_partial_payments_integration.py` | 2, 3, 4, 5, 6 | Nouveau (intégration) |
| `frontend/src/components/PaymentModal.js` | 7 | Nouveau |
| `frontend/src/pages/InvoicesPage.js` | 8 | Modif (colonne + bouton + intégration modal) |
| `frontend/src/pages/Dashboard.js` | 9 | Modif (carte Total à recevoir) |
| `CLAUDE.md` | 10 | Modif (changelog) |

Commits attendus : **10**.
