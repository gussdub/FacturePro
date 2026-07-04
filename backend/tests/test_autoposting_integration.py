"""Tests d'intégration — Grand livre Phase 2 : auto-posting (feature #12).

Via le client HTTP de test (TestClient in-process) et des orgs JETABLES
(pattern _setup_org/_cleanup de TestLedgerCrossOrgIsolation, T7). Ne salit
JAMAIS l'org de seed (gussdub) : chaque org de test est purgée en finally.

Backend requis : MongoDB local (MONGO_URL/.env). TestClient monte l'app en
process, aucun serveur externe sur :8000 n'est nécessaire.

Tâche 7 — Hook PUT /api/invoices/{id}/status (table de transitions §5.5).
Tâche 8 — Hooks paiements POST/DELETE (§5.2 encaissement / §5.3 contre-passation).
Tâche 9 — Hook DELETE facture (cascade §5.4) + dépenses POST/PUT/DELETE (§5.6/§5.7).
"""
import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))

import uuid
import pytest
from datetime import datetime, timezone, timedelta
import server as server_module
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    return TestClient(server_module.app)


def _setup_org(client, label, autopost_enabled=True):
    """Crée une org JETABLE isolée (owner + login) avec autopost_enabled
    paramétrable. Renvoie (uid, org_id, headers)."""
    uid = f"ap{label}-{uuid.uuid4().hex[:8]}"
    org_id = str(uuid.uuid4())
    server_module.db.organizations.insert_one({
        "id": org_id, "name": f"Org{label} AP", "owner_id": uid,
        "subscription_status": "trial",
        "trial_ends_at": (datetime.now(timezone.utc) + timedelta(days=100)).isoformat(),
        "role_permissions": server_module.DEFAULT_ROLE_PERMISSIONS,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    server_module.db.company_settings.insert_one({
        "id": f"cs-{org_id}", "user_id": uid, "organization_id": org_id,
        "company_name": f"Org{label} AP",
        "autopost_enabled": autopost_enabled,
        "expense_default_credit_account": "1000",
        "province": "QC",
    })
    server_module.db.users.insert_one({
        "id": uid, "email": f"{uid}@org{label}.test", "is_active": True,
        "organization_id": org_id, "role": "owner",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    server_module.db.user_passwords.insert_one({
        "user_id": uid, "hashed_password": server_module.hash_password("orgpass"),
    })
    r = client.post("/api/auth/login",
                    json={"email": f"{uid}@org{label}.test", "password": "orgpass"})
    assert r.status_code == 200, r.text
    return uid, org_id, {"Authorization": f"Bearer {r.json()['access_token']}"}


def _cleanup(uid, org_id):
    server_module.db.users.delete_one({"id": uid})
    server_module.db.user_passwords.delete_one({"user_id": uid})
    server_module.db.organizations.delete_one({"id": org_id})
    server_module.db.company_settings.delete_many({"organization_id": org_id})
    server_module.db.chart_of_accounts.delete_many({"organization_id": org_id})
    server_module.db.journal_entries.delete_many({"organization_id": org_id})
    server_module.db.ledger_counters.delete_many({"organization_id": org_id})
    server_module.db.invoices.delete_many({"organization_id": org_id})
    server_module.db.expenses.delete_many({"organization_id": org_id})


def _create_draft_invoice(client, headers, total=115.0, province="QC"):
    """Crée une facture draft QC (subtotal → gst/tvq calculés backend)."""
    # subtotal 100 QC → gst 5.00, tvq 9.975→9.98, total 114.98 (proche de 115).
    r = client.post("/api/invoices", headers=headers, json={
        "client_id": "",
        "invoice_number": f"INV-{uuid.uuid4().hex[:6]}",
        "issue_date": "2026-06-15",
        "province": province,
        "items": [{"description": "Service", "quantity": 1, "unit_price": 100.0}],
    })
    assert r.status_code == 200, r.text
    return r.json()


def _set_status(client, headers, inv_id, status):
    return client.put(f"/api/invoices/{inv_id}/status", headers=headers,
                      json={"status": status})


def _add_payment(client, headers, inv_id, amount, date="2026-06-20",
                 reference=None):
    body = {"amount_cad": amount, "method": "transfer", "date": date}
    if reference is not None:
        body["reference"] = reference
    return client.post(f"/api/invoices/{inv_id}/payments", headers=headers,
                       json=body)


def _delete_payment(client, headers, inv_id, payment_id):
    return client.delete(f"/api/invoices/{inv_id}/payments/{payment_id}",
                         headers=headers)


def _live_revenue_entries(org_id, inv_id):
    """Écritures auto VIVANTES (non contre-passées) pour source=invoice/inv_id."""
    return list(server_module.db.journal_entries.find({
        "organization_id": org_id, "source_type": "invoice",
        "source_id": inv_id, "entry_type": "auto",
        "reversed_by_entry_id": None,
    }, {"_id": 0}))


def _all_invoice_entries(org_id, inv_id):
    """TOUTES les écritures auto (vivantes + miroirs) source=invoice/inv_id."""
    return list(server_module.db.journal_entries.find({
        "organization_id": org_id, "source_type": "invoice",
        "source_id": inv_id,
    }, {"_id": 0}))


def _live_payment_entries(org_id, payment_id):
    """Écritures auto VIVANTES pour source=invoice_payment/payment_id."""
    return list(server_module.db.journal_entries.find({
        "organization_id": org_id, "source_type": "invoice_payment",
        "source_id": payment_id, "entry_type": "auto",
        "reversed_by_entry_id": None,
    }, {"_id": 0}))


def _all_payment_entries(org_id, payment_id):
    """TOUTES les écritures auto (vivantes + miroirs) source=invoice_payment."""
    return list(server_module.db.journal_entries.find({
        "organization_id": org_id, "source_type": "invoice_payment",
        "source_id": payment_id,
    }, {"_id": 0}))


def _live_expense_entries(org_id, expense_id):
    """Écritures auto VIVANTES pour source=expense/expense_id."""
    return list(server_module.db.journal_entries.find({
        "organization_id": org_id, "source_type": "expense",
        "source_id": expense_id, "entry_type": "auto",
        "reversed_by_entry_id": None,
    }, {"_id": 0}))


def _all_expense_entries(org_id, expense_id):
    """TOUTES les écritures auto (vivantes + miroirs) source=expense/expense_id."""
    return list(server_module.db.journal_entries.find({
        "organization_id": org_id, "source_type": "expense",
        "source_id": expense_id,
    }, {"_id": 0}))


def _create_expense(client, headers, amount=115.0, category_code="office_supplies",
                    gst=5.0, qst=9.98, description="Fournitures",
                    expense_date="2026-06-15"):
    """Crée une dépense CAD via POST /api/expenses."""
    body = {
        "amount": amount, "currency": "CAD",
        "category_code": category_code,
        "gst_paid_cad": gst, "qst_paid_cad": qst,
        "description": description, "expense_date": expense_date,
    }
    return client.post("/api/expenses", headers=headers, json=body)


def _num_by_id(org_id, account_id):
    acc = server_module.db.chart_of_accounts.find_one(
        {"organization_id": org_id, "id": account_id}, {"account_number": 1})
    return acc["account_number"] if acc else None


def _net_by_number(org_id, entries):
    """Somme nette Dr−Cr par n° de compte sur une liste d'écritures."""
    net = {}
    for e in entries:
        for ln in e.get("lines", []):
            num = _num_by_id(org_id, ln["account_id"])
            net.setdefault(num, 0.0)
            net[num] += round(float(ln.get("debit", 0) or 0), 2)
            net[num] -= round(float(ln.get("credit", 0) or 0), 2)
    return {k: round(v, 2) for k, v in net.items()}


def _assert_balanced_entry(org_id, entry):
    dr = round(sum(float(l.get("debit", 0) or 0) for l in entry["lines"]), 2)
    cr = round(sum(float(l.get("credit", 0) or 0) for l in entry["lines"]), 2)
    assert abs(dr - cr) <= 0.005, f"déséquilibre Dr {dr} ≠ Cr {cr}"


class TestInvoiceStatusHook:
    """Tâche 7 — PUT /api/invoices/{id}/status câble l'auto-posting (§5.5)."""

    def test_draft_to_sent_posts_revenue(self, client):
        uid, org_id, h = _setup_org(client, "a")
        try:
            inv = _create_draft_invoice(client, h)
            # draft → aucune écriture
            assert _live_revenue_entries(org_id, inv["id"]) == []
            r = _set_status(client, h, inv["id"], "sent")
            assert r.status_code == 200, r.text
            live = _live_revenue_entries(org_id, inv["id"])
            assert len(live) == 1, "1 écriture de revenu vivante attendue"
            entry = live[0]
            _assert_balanced_entry(org_id, entry)
            # crédite bien le compte de revenu 4000
            nums = {_num_by_id(org_id, ln["account_id"]) for ln in entry["lines"]}
            assert "4000" in nums
            assert "1100" in nums
        finally:
            _cleanup(uid, org_id)

    def test_sent_to_overdue_is_noop(self, client):
        uid, org_id, h = _setup_org(client, "b")
        try:
            inv = _create_draft_invoice(client, h)
            _set_status(client, h, inv["id"], "sent")
            before = _all_invoice_entries(org_id, inv["id"])
            assert len(before) == 1
            r = _set_status(client, h, inv["id"], "overdue")
            assert r.status_code == 200, r.text
            after = _all_invoice_entries(org_id, inv["id"])
            # aucune nouvelle écriture (accrual : le revenu reste comptabilisé)
            assert len(after) == 1, "overdue ne doit créer aucune écriture"
            assert len(_live_revenue_entries(org_id, inv["id"])) == 1
        finally:
            _cleanup(uid, org_id)

    def test_sent_to_draft_reverses_revenue(self, client):
        uid, org_id, h = _setup_org(client, "c")
        try:
            inv = _create_draft_invoice(client, h)
            _set_status(client, h, inv["id"], "sent")
            assert len(_live_revenue_entries(org_id, inv["id"])) == 1
            r = _set_status(client, h, inv["id"], "draft")
            assert r.status_code == 200, r.text
            # plus aucune vivante (contre-passée)
            assert _live_revenue_entries(org_id, inv["id"]) == []
            # net zéro sur 1100 / 4000 (origine + miroir)
            net = _net_by_number(org_id, _all_invoice_entries(org_id, inv["id"]))
            assert net.get("1100", 0.0) == 0.0
            assert net.get("4000", 0.0) == 0.0
        finally:
            _cleanup(uid, org_id)

    def test_draft_sent_draft_sent_single_live(self, client):
        uid, org_id, h = _setup_org(client, "d")
        try:
            inv = _create_draft_invoice(client, h)
            _set_status(client, h, inv["id"], "sent")
            _set_status(client, h, inv["id"], "draft")
            _set_status(client, h, inv["id"], "sent")
            # un seul post vivant à la fin (les anciens contre-passés)
            live = _live_revenue_entries(org_id, inv["id"])
            assert len(live) == 1, f"1 seul vivant attendu, trouvé {len(live)}"
            _assert_balanced_entry(org_id, live[0])
        finally:
            _cleanup(uid, org_id)

    def test_autopost_disabled_posts_nothing(self, client):
        uid, org_id, h = _setup_org(client, "e", autopost_enabled=False)
        try:
            inv = _create_draft_invoice(client, h)
            r = _set_status(client, h, inv["id"], "sent")
            assert r.status_code == 200, r.text
            assert _all_invoice_entries(org_id, inv["id"]) == [], \
                "autopost_enabled=False → aucune écriture"
        finally:
            _cleanup(uid, org_id)

    def test_status_update_still_works_business(self, client):
        # Non-régression métier : le PUT met bien à jour le statut (comportement
        # existant préservé) même avec le hook branché.
        uid, org_id, h = _setup_org(client, "f")
        try:
            inv = _create_draft_invoice(client, h)
            _set_status(client, h, inv["id"], "sent")
            fresh = client.get(f"/api/invoices/{inv['id']}", headers=h).json()
            assert fresh["status"] == "sent"
        finally:
            _cleanup(uid, org_id)

    def test_autopost_failure_does_not_break_put(self, client, monkeypatch):
        # Robustesse (§6.3) : si l'auto-posting lève, le PUT reste 200 et le
        # statut est bien changé (l'op métier ne doit JAMAIS échouer).
        uid, org_id, h = _setup_org(client, "g")
        try:
            inv = _create_draft_invoice(client, h)

            def _boom(*a, **k):
                raise RuntimeError("boom")

            monkeypatch.setattr(server_module, "_autopost_invoice_revenue", _boom)
            r = _set_status(client, h, inv["id"], "sent")
            assert r.status_code == 200, r.text
            fresh = client.get(f"/api/invoices/{inv['id']}", headers=h).json()
            assert fresh["status"] == "sent"
            # un autopost_error générique a été posé (pas de "boom")
            doc = server_module.db.invoices.find_one(
                {"id": inv["id"], "organization_id": org_id}, {"_id": 0})
            assert "autopost_error" in doc
            assert "boom" not in doc["autopost_error"]
        finally:
            _cleanup(uid, org_id)


class TestPaymentHooks:
    """Tâche 8 — POST/DELETE payments câblent l'encaissement (§5.2/§5.3)."""

    def _sent_invoice(self, client, h, org_id):
        """Facture QC passée à `sent` : revenu déjà posté (1 écriture)."""
        inv = _create_draft_invoice(client, h)
        r = _set_status(client, h, inv["id"], "sent")
        assert r.status_code == 200, r.text
        assert len(_live_revenue_entries(org_id, inv["id"])) == 1
        return inv

    def test_post_payment_posts_encaissement(self, client):
        # POST payment → 1 écriture d'encaissement Dr 1000 / Cr 1100 = amount_cad,
        # équilibrée. Le recompute de statut (partial) ne re-poste PAS le revenu.
        uid, org_id, h = _setup_org(client, "h")
        try:
            inv = self._sent_invoice(client, h, org_id)
            r = _add_payment(client, h, inv["id"], 50.0, reference="TX-100")
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["status"] == "partial"
            pid = body["payments"][0]["id"]
            # une seule écriture d'encaissement vivante
            live = _live_payment_entries(org_id, pid)
            assert len(live) == 1, "1 encaissement vivant attendu"
            entry = live[0]
            _assert_balanced_entry(org_id, entry)
            net = _net_by_number(org_id, [entry])
            assert net.get("1000") == 50.0, "Dr 1000 = amount_cad"
            assert net.get("1100") == -50.0, "Cr 1100 = amount_cad"
            assert entry.get("reference") == "TX-100"
            # le recompute de statut ne crée PAS de 2e écriture de revenu
            assert len(_live_revenue_entries(org_id, inv["id"])) == 1, \
                "le recompute partial/paid ne re-poste pas le revenu"
        finally:
            _cleanup(uid, org_id)

    def test_full_payment_two_live_entries(self, client):
        # Facture passée `paid` via paiement complet → exactement 2 écritures
        # vivantes (revenu + encaissement), 1 par source distincte.
        uid, org_id, h = _setup_org(client, "i")
        try:
            inv = self._sent_invoice(client, h, org_id)
            total = round(float(inv["total"]), 2)
            r = _add_payment(client, h, inv["id"], total)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["status"] == "paid"
            pid = body["payments"][0]["id"]
            assert len(_live_revenue_entries(org_id, inv["id"])) == 1
            assert len(_live_payment_entries(org_id, pid)) == 1
            # exactement UNE écriture de revenu vivante encore (jamais re-postée)
            assert len(_live_revenue_entries(org_id, inv["id"])) == 1
        finally:
            _cleanup(uid, org_id)

    def test_delete_payment_reverses_encaissement(self, client):
        # DELETE payment → encaissement contre-passé (net zéro 1000/1100) ;
        # l'écriture de revenu reste vivante.
        uid, org_id, h = _setup_org(client, "j")
        try:
            inv = self._sent_invoice(client, h, org_id)
            r = _add_payment(client, h, inv["id"], 40.0)
            pid = r.json()["payments"][0]["id"]
            assert len(_live_payment_entries(org_id, pid)) == 1
            r2 = _delete_payment(client, h, inv["id"], pid)
            assert r2.status_code == 200, r2.text
            # plus aucun encaissement vivant (contre-passé)
            assert _live_payment_entries(org_id, pid) == []
            # net zéro sur 1000 / 1100 (origine + miroir)
            net = _net_by_number(org_id, _all_payment_entries(org_id, pid))
            assert net.get("1000", 0.0) == 0.0
            assert net.get("1100", 0.0) == 0.0
            # le revenu reste intact et vivant
            assert len(_live_revenue_entries(org_id, inv["id"])) == 1
        finally:
            _cleanup(uid, org_id)

    def test_payment_hook_idempotent(self, client):
        # Idempotence : re-poster le même payment.id → 1 seule écriture vivante.
        uid, org_id, h = _setup_org(client, "k")
        try:
            inv = self._sent_invoice(client, h, org_id)
            r = _add_payment(client, h, inv["id"], 30.0)
            pid = r.json()["payments"][0]["id"]
            assert len(_live_payment_entries(org_id, pid)) == 1
            # appel direct du mapping une 2e fois avec le même payment.id
            payment = {"id": pid, "amount_cad": 30.0, "date": "2026-06-20"}
            server_module._autopost_payment(org_id, uid, inv, payment)
            assert len(_live_payment_entries(org_id, pid)) == 1, \
                "2 appels avec le même payment.id → 1 écriture"
        finally:
            _cleanup(uid, org_id)

    def test_payment_autopost_disabled_posts_nothing(self, client):
        # autopost_enabled=False → POST payment ne crée AUCUNE écriture.
        uid, org_id, h = _setup_org(client, "l", autopost_enabled=False)
        try:
            inv = _create_draft_invoice(client, h)
            _set_status(client, h, inv["id"], "sent")
            r = _add_payment(client, h, inv["id"], 20.0)
            assert r.status_code == 200, r.text
            pid = r.json()["payments"][0]["id"]
            assert _all_payment_entries(org_id, pid) == [], \
                "autopost_enabled=False → aucun encaissement"
        finally:
            _cleanup(uid, org_id)

    def test_payment_post_still_works_business(self, client):
        # Non-régression métier : le POST enregistre bien le paiement et recalcule
        # le statut même avec le hook branché.
        uid, org_id, h = _setup_org(client, "m")
        try:
            inv = self._sent_invoice(client, h, org_id)
            r = _add_payment(client, h, inv["id"], 10.0)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["total_paid_cad"] == 10.0
            assert len(body["payments"]) == 1
        finally:
            _cleanup(uid, org_id)

    def test_payment_autopost_failure_does_not_break_post(self, client, monkeypatch):
        # Robustesse (§6.3) : si l'encaissement lève, le POST reste 200 et le
        # paiement est bien enregistré (l'op métier ne doit JAMAIS échouer).
        uid, org_id, h = _setup_org(client, "n")
        try:
            inv = self._sent_invoice(client, h, org_id)

            def _boom(*a, **k):
                raise RuntimeError("boom")

            monkeypatch.setattr(server_module, "_autopost_payment", _boom)
            r = _add_payment(client, h, inv["id"], 15.0)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["total_paid_cad"] == 15.0
            doc = server_module.db.invoices.find_one(
                {"id": inv["id"], "organization_id": org_id}, {"_id": 0})
            assert "autopost_error" in doc
            assert "boom" not in doc["autopost_error"]
        finally:
            _cleanup(uid, org_id)

    def test_delete_payment_autopost_failure_does_not_break_delete(
            self, client, monkeypatch):
        # Robustesse : si la contre-passation lève, le DELETE reste 200 et le
        # paiement est bien retiré.
        uid, org_id, h = _setup_org(client, "o")
        try:
            inv = self._sent_invoice(client, h, org_id)
            r = _add_payment(client, h, inv["id"], 25.0)
            pid = r.json()["payments"][0]["id"]

            def _boom(*a, **k):
                raise RuntimeError("boom")

            monkeypatch.setattr(server_module, "_unpost_source_entry", _boom)
            r2 = _delete_payment(client, h, inv["id"], pid)
            assert r2.status_code == 200, r2.text
            fresh = client.get(f"/api/invoices/{inv['id']}", headers=h).json()
            assert fresh["total_paid_cad"] == 0.0
            assert len(fresh.get("payments", [])) == 0
        finally:
            _cleanup(uid, org_id)

    def test_zero_amount_payment_no_entry_no_error(self, client):
        # Edge case (§5.2) : un paiement à montant 0 n'a AUCUN encaissement à
        # comptabiliser (événement économique nul). Le hook doit NO-OP proprement :
        # aucune écriture postée ET aucun autopost_error spurious sur la facture
        # (l'ancienne version tentait Dr 1000=0 / Cr 1100=0 → rejet
        # _validate_entry_balance → autopost_error trompeur sur une op valide).
        uid, org_id, h = _setup_org(client, "p")
        try:
            inv = self._sent_invoice(client, h, org_id)
            r = _add_payment(client, h, inv["id"], 0.0)
            assert r.status_code == 200, r.text
            pid = r.json()["payments"][0]["id"]
            # aucune écriture d'encaissement (rien à comptabiliser)
            assert _all_payment_entries(org_id, pid) == [], \
                "un paiement à 0 ne poste aucun encaissement"
            # AUCUN autopost_error : le no-op est légitime, pas un échec
            doc = server_module.db.invoices.find_one(
                {"id": inv["id"], "organization_id": org_id}, {"_id": 0})
            assert "autopost_error" not in doc, \
                "un paiement à 0 ne doit pas poser d'autopost_error"
        finally:
            _cleanup(uid, org_id)

    def test_negative_amount_payment_no_corrupt_entry(self, client):
        # Edge case : un montant négatif ne doit JAMAIS produire d'écriture
        # (une ligne négative empoisonnerait _account_balance). Le hook no-op,
        # aucune écriture corrompue persistée, POST reste 200.
        uid, org_id, h = _setup_org(client, "q")
        try:
            inv = self._sent_invoice(client, h, org_id)
            r = _add_payment(client, h, inv["id"], -10.0)
            assert r.status_code == 200, r.text
            pid = r.json()["payments"][0]["id"]
            assert _all_payment_entries(org_id, pid) == [], \
                "un montant négatif ne poste aucune écriture"
            doc = server_module.db.invoices.find_one(
                {"id": inv["id"], "organization_id": org_id}, {"_id": 0})
            assert "autopost_error" not in doc
        finally:
            _cleanup(uid, org_id)

    def test_direct_autopost_payment_zero_is_noop(self, client):
        # Unité : appel direct de _autopost_payment avec amount_cad=0 → None,
        # aucune écriture (no-op, contrat identique à _post_source_entry).
        uid, org_id, h = _setup_org(client, "r")
        try:
            inv = self._sent_invoice(client, h, org_id)
            payment = {"id": str(uuid.uuid4()), "amount_cad": 0.0,
                       "date": "2026-06-20"}
            res = server_module._autopost_payment(org_id, uid, inv, payment)
            assert res is None, "amount 0 → no-op (None)"
            assert _all_payment_entries(org_id, payment["id"]) == []
        finally:
            _cleanup(uid, org_id)


class TestDeleteInvoiceCascade:
    """Tâche 9 — DELETE /api/invoices/{id} contre-passe le revenu ET tous les
    encaissements liés en cascade (§5.4)."""

    def test_delete_invoice_reverses_revenue_and_all_payments(self, client):
        # Facture sent + 2 paiements → DELETE → revenu ET les 2 encaissements
        # contre-passés ; net zéro global ; aucun vivant restant.
        uid, org_id, h = _setup_org(client, "s")
        try:
            inv = _create_draft_invoice(client, h)
            _set_status(client, h, inv["id"], "sent")
            assert len(_live_revenue_entries(org_id, inv["id"])) == 1
            r1 = _add_payment(client, h, inv["id"], 30.0)
            pid1 = r1.json()["payments"][0]["id"]
            r2 = _add_payment(client, h, inv["id"], 20.0)
            pid2 = r2.json()["payments"][1]["id"]
            assert len(_live_payment_entries(org_id, pid1)) == 1
            assert len(_live_payment_entries(org_id, pid2)) == 1

            r = client.delete(f"/api/invoices/{inv['id']}", headers=h)
            assert r.status_code == 200, r.text

            # plus aucune écriture vivante : ni revenu ni encaissements
            assert _live_revenue_entries(org_id, inv["id"]) == [], \
                "le revenu doit être contre-passé"
            assert _live_payment_entries(org_id, pid1) == []
            assert _live_payment_entries(org_id, pid2) == []
            # net zéro global (origine + miroir) sur chaque source
            inv_net = _net_by_number(org_id, _all_invoice_entries(org_id, inv["id"]))
            assert inv_net.get("1100", 0.0) == 0.0
            assert inv_net.get("4000", 0.0) == 0.0
            for pid in (pid1, pid2):
                pnet = _net_by_number(org_id, _all_payment_entries(org_id, pid))
                assert pnet.get("1000", 0.0) == 0.0
                assert pnet.get("1100", 0.0) == 0.0
        finally:
            _cleanup(uid, org_id)

    def test_delete_invoice_no_payments_reverses_revenue(self, client):
        # Facture sent sans paiement → DELETE → revenu seul contre-passé.
        uid, org_id, h = _setup_org(client, "t")
        try:
            inv = _create_draft_invoice(client, h)
            _set_status(client, h, inv["id"], "sent")
            assert len(_live_revenue_entries(org_id, inv["id"])) == 1
            r = client.delete(f"/api/invoices/{inv['id']}", headers=h)
            assert r.status_code == 200, r.text
            assert _live_revenue_entries(org_id, inv["id"]) == []
            net = _net_by_number(org_id, _all_invoice_entries(org_id, inv["id"]))
            assert net.get("1100", 0.0) == 0.0
            assert net.get("4000", 0.0) == 0.0
        finally:
            _cleanup(uid, org_id)

    def test_delete_invoice_disabled_posts_nothing(self, client):
        # autopost_enabled=False → DELETE facture ne touche à aucune écriture.
        uid, org_id, h = _setup_org(client, "u", autopost_enabled=False)
        try:
            inv = _create_draft_invoice(client, h)
            _set_status(client, h, inv["id"], "sent")
            assert _all_invoice_entries(org_id, inv["id"]) == []
            r = client.delete(f"/api/invoices/{inv['id']}", headers=h)
            assert r.status_code == 200, r.text
            assert _all_invoice_entries(org_id, inv["id"]) == []
        finally:
            _cleanup(uid, org_id)

    def test_delete_invoice_still_works_business(self, client):
        # Non-régression métier : la facture est bien supprimée (404 ensuite).
        uid, org_id, h = _setup_org(client, "v")
        try:
            inv = _create_draft_invoice(client, h)
            _set_status(client, h, inv["id"], "sent")
            r = client.delete(f"/api/invoices/{inv['id']}", headers=h)
            assert r.status_code == 200, r.text
            r2 = client.get(f"/api/invoices/{inv['id']}", headers=h)
            assert r2.status_code == 404
        finally:
            _cleanup(uid, org_id)

    def test_delete_invoice_autopost_failure_does_not_break_delete(
            self, client, monkeypatch):
        # Robustesse (§6.3) : si la cascade de contre-passation lève, le DELETE
        # reste 200 et la facture est bien supprimée.
        uid, org_id, h = _setup_org(client, "w")
        try:
            inv = _create_draft_invoice(client, h)
            _set_status(client, h, inv["id"], "sent")

            def _boom(*a, **k):
                raise RuntimeError("boom")

            monkeypatch.setattr(server_module, "_unpost_source_entry", _boom)
            r = client.delete(f"/api/invoices/{inv['id']}", headers=h)
            assert r.status_code == 200, r.text
            r2 = client.get(f"/api/invoices/{inv['id']}", headers=h)
            assert r2.status_code == 404
        finally:
            _cleanup(uid, org_id)


class TestExpenseHooks:
    """Tâche 9 — POST/PUT/DELETE /api/expenses câblent la charge (§5.6/§5.7)."""

    def test_post_expense_posts_charge(self, client):
        # POST expense → 1 écriture équilibrée : charge nette + taxes 12xx + crédit.
        uid, org_id, h = _setup_org(client, "x")
        try:
            r = _create_expense(client, h, amount=114.98, gst=5.0, qst=9.98)
            assert r.status_code == 200, r.text
            exp = r.json()
            live = _live_expense_entries(org_id, exp["id"])
            assert len(live) == 1, "1 écriture de dépense vivante attendue"
            entry = live[0]
            _assert_balanced_entry(org_id, entry)
            net = _net_by_number(org_id, [entry])
            # charge nette = 114.98 − 5.00 − 9.98 = 100.00 sur 5010 (office_supplies)
            assert net.get("5010") == 100.0, "charge nette par différence"
            assert net.get("1200") == 5.0, "Dr TPS 1200"
            assert net.get("1210") == 9.98, "Dr TVQ 1210"
            assert net.get("1000") == -114.98, "Cr Encaisse = amount_cad total"
        finally:
            _cleanup(uid, org_id)

    def test_post_expense_unmapped_category_falls_back_5900(self, client):
        # Catégorie non mappée → charge sur 5900 (Dépenses diverses).
        uid, org_id, h = _setup_org(client, "y")
        try:
            r = _create_expense(client, h, amount=50.0, category_code="other",
                                gst=0.0, qst=0.0)
            assert r.status_code == 200, r.text
            exp = r.json()
            live = _live_expense_entries(org_id, exp["id"])
            assert len(live) == 1
            _assert_balanced_entry(org_id, live[0])
            net = _net_by_number(org_id, live)
            assert net.get("5900") == 50.0, "fallback 5900"
            assert net.get("1000") == -50.0
        finally:
            _cleanup(uid, org_id)

    def test_put_expense_amount_change_regenerates(self, client):
        # PUT expense avec amount modifié → ancienne contre-passée + nouvelle
        # postée ; 1 seul vivant ; somme (ancien + miroir) = 0 sur les comptes
        # de l'ancienne écriture ; le vivant reflète le nouveau montant.
        uid, org_id, h = _setup_org(client, "z")
        try:
            r = _create_expense(client, h, amount=114.98, gst=5.0, qst=9.98)
            exp = r.json()
            assert len(_live_expense_entries(org_id, exp["id"])) == 1
            # PUT : nouveau montant (sans taxes pour simplifier la lecture nette)
            r2 = client.put(f"/api/expenses/{exp['id']}", headers=h, json={
                "amount": 200.0, "gst_paid_cad": 0.0, "qst_paid_cad": 0.0,
            })
            assert r2.status_code == 200, r2.text
            live = _live_expense_entries(org_id, exp["id"])
            assert len(live) == 1, "1 seul vivant après régénération"
            _assert_balanced_entry(org_id, live[0])
            # le vivant reflète le nouveau montant : charge nette 200 sur 5010
            live_net = _net_by_number(org_id, live)
            assert live_net.get("5010") == 200.0
            assert live_net.get("1000") == -200.0
            # net GLOBAL (toutes les écritures : ancienne + miroir + nouvelle) =
            # exactement la nouvelle écriture (l'ancienne + son miroir s'annulent).
            all_net = _net_by_number(org_id, _all_expense_entries(org_id, exp["id"]))
            assert all_net.get("5010") == 200.0
            assert all_net.get("1000") == -200.0
            # les taxes de l'ancienne écriture (1200/1210) sont net zéro
            assert all_net.get("1200", 0.0) == 0.0
            assert all_net.get("1210", 0.0) == 0.0
        finally:
            _cleanup(uid, org_id)

    def test_delete_expense_reverses(self, client):
        # DELETE expense → contre-passée, net zéro, aucun vivant.
        uid, org_id, h = _setup_org(client, "aa")
        try:
            r = _create_expense(client, h, amount=114.98, gst=5.0, qst=9.98)
            exp = r.json()
            assert len(_live_expense_entries(org_id, exp["id"])) == 1
            r2 = client.delete(f"/api/expenses/{exp['id']}", headers=h)
            assert r2.status_code == 200, r2.text
            assert _live_expense_entries(org_id, exp["id"]) == []
            net = _net_by_number(org_id, _all_expense_entries(org_id, exp["id"]))
            assert net.get("5010", 0.0) == 0.0
            assert net.get("1200", 0.0) == 0.0
            assert net.get("1210", 0.0) == 0.0
            assert net.get("1000", 0.0) == 0.0
        finally:
            _cleanup(uid, org_id)

    def test_expense_credit_account_flag_ap(self, client):
        # expense_default_credit_account="2000" → crédit sur Comptes fournisseurs.
        uid, org_id, h = _setup_org(client, "ab")
        try:
            server_module.db.company_settings.update_one(
                {"organization_id": org_id},
                {"$set": {"expense_default_credit_account": "2000"}})
            r = _create_expense(client, h, amount=50.0, category_code="other",
                                gst=0.0, qst=0.0)
            exp = r.json()
            live = _live_expense_entries(org_id, exp["id"])
            assert len(live) == 1
            net = _net_by_number(org_id, live)
            assert net.get("2000") == -50.0, "crédit sur 2000 (A/P)"
            assert net.get("1000") is None, "aucun crédit Encaisse"
        finally:
            _cleanup(uid, org_id)

    def test_expense_autopost_disabled_posts_nothing(self, client):
        # autopost_enabled=False → aucun des hooks dépense ne crée d'écriture.
        uid, org_id, h = _setup_org(client, "ac", autopost_enabled=False)
        try:
            r = _create_expense(client, h, amount=114.98, gst=5.0, qst=9.98)
            exp = r.json()
            assert _all_expense_entries(org_id, exp["id"]) == [], \
                "POST : autopost_enabled=False → aucune écriture"
            r2 = client.put(f"/api/expenses/{exp['id']}", headers=h,
                            json={"amount": 200.0})
            assert r2.status_code == 200, r2.text
            assert _all_expense_entries(org_id, exp["id"]) == [], \
                "PUT : autopost_enabled=False → aucune écriture"
            r3 = client.delete(f"/api/expenses/{exp['id']}", headers=h)
            assert r3.status_code == 200, r3.text
            assert _all_expense_entries(org_id, exp["id"]) == [], \
                "DELETE : autopost_enabled=False → aucune écriture"
        finally:
            _cleanup(uid, org_id)

    def test_expense_hooks_still_work_business(self, client):
        # Non-régression métier : POST/PUT/DELETE dépense fonctionnent (données
        # métier intactes) même avec les hooks branchés.
        uid, org_id, h = _setup_org(client, "ad")
        try:
            r = _create_expense(client, h, amount=100.0, gst=0.0, qst=0.0)
            assert r.status_code == 200, r.text
            exp = r.json()
            assert exp["amount"] == 100.0
            r2 = client.put(f"/api/expenses/{exp['id']}", headers=h,
                            json={"amount": 150.0})
            assert r2.status_code == 200, r2.text
            assert r2.json()["amount"] == 150.0
            r3 = client.delete(f"/api/expenses/{exp['id']}", headers=h)
            assert r3.status_code == 200, r3.text
            # la dépense est bien physiquement supprimée (pas de GET single, on
            # vérifie via la DB org-scopée).
            assert server_module.db.expenses.find_one(
                {"id": exp["id"], "organization_id": org_id}) is None
        finally:
            _cleanup(uid, org_id)

    def test_expense_post_autopost_failure_does_not_break_post(
            self, client, monkeypatch):
        # Robustesse (§6.3) : si l'auto-post lève, le POST reste 200 et la
        # dépense est bien enregistrée.
        uid, org_id, h = _setup_org(client, "ae")
        try:
            def _boom(*a, **k):
                raise RuntimeError("boom")

            monkeypatch.setattr(server_module, "_autopost_expense", _boom)
            r = _create_expense(client, h, amount=100.0, gst=0.0, qst=0.0)
            assert r.status_code == 200, r.text
            exp = r.json()
            assert exp["amount"] == 100.0
            doc = server_module.db.expenses.find_one(
                {"id": exp["id"], "organization_id": org_id}, {"_id": 0})
            assert "autopost_error" in doc
            assert "boom" not in doc["autopost_error"]
        finally:
            _cleanup(uid, org_id)

    def test_expense_delete_autopost_failure_does_not_break_delete(
            self, client, monkeypatch):
        # Robustesse : si la contre-passation lève au DELETE, la dépense est
        # quand même supprimée (op métier prioritaire).
        uid, org_id, h = _setup_org(client, "af")
        try:
            r = _create_expense(client, h, amount=100.0, gst=0.0, qst=0.0)
            exp = r.json()

            def _boom(*a, **k):
                raise RuntimeError("boom")

            monkeypatch.setattr(server_module, "_unpost_source_entry", _boom)
            r2 = client.delete(f"/api/expenses/{exp['id']}", headers=h)
            assert r2.status_code == 200, r2.text
            assert server_module.db.expenses.find_one(
                {"id": exp["id"], "organization_id": org_id}) is None
        finally:
            _cleanup(uid, org_id)

    def test_expense_idempotent_double_post(self, client):
        # Idempotence : appeler le mapping 2× avec le même expense.id → 1 vivant.
        uid, org_id, h = _setup_org(client, "ag")
        try:
            r = _create_expense(client, h, amount=100.0, gst=0.0, qst=0.0)
            exp = r.json()
            assert len(_live_expense_entries(org_id, exp["id"])) == 1
            server_module._autopost_expense(org_id, uid, exp)
            assert len(_live_expense_entries(org_id, exp["id"])) == 1, \
                "2 appels avec le même expense.id → 1 écriture"
        finally:
            _cleanup(uid, org_id)
