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
    server_module.db.autopost_orphans.delete_many({"organization_id": org_id})


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


def _orphans(org_id):
    return list(server_module.db.autopost_orphans.find(
        {"organization_id": org_id}, {"_id": 0}))


class TestFixT9CascadeAtomicity:
    """Fix T9 #1 — cascade delete_invoice atomique par source + trou journalisé."""

    def test_cascade_reverses_all_sources_when_one_payment_fails(
            self, client, monkeypatch):
        # Une facture sent + 2 paiements. On force l'échec de la contre-passation
        # du 2e paiement UNIQUEMENT. Attendu : le revenu ET le 1er paiement sont
        # bien contre-passés (la cascade ne s'arrête PAS au 1er échec), et le
        # trou (2e paiement) est journalisé dans autopost_orphans AVANT le delete.
        uid, org_id, h = _setup_org(client, "fx1")
        try:
            inv = _create_draft_invoice(client, h)
            _set_status(client, h, inv["id"], "sent")
            r1 = _add_payment(client, h, inv["id"], 30.0)
            pid1 = r1.json()["payments"][0]["id"]
            r2 = _add_payment(client, h, inv["id"], 20.0)
            pid2 = r2.json()["payments"][1]["id"]
            assert len(_live_revenue_entries(org_id, inv["id"])) == 1
            assert len(_live_payment_entries(org_id, pid1)) == 1
            assert len(_live_payment_entries(org_id, pid2)) == 1

            real_unpost = server_module._unpost_source_entry

            def _selective(organization_id, user_id, source_type, source_id,
                           *a, **k):
                if source_type == "invoice_payment" and source_id == pid2:
                    raise RuntimeError("boom-p2")
                return real_unpost(organization_id, user_id, source_type,
                                   source_id, *a, **k)

            monkeypatch.setattr(server_module, "_unpost_source_entry", _selective)
            r = client.delete(f"/api/invoices/{inv['id']}", headers=h)
            assert r.status_code == 200, r.text

            # Cascade NON interrompue : revenu + paiement 1 contre-passés malgré
            # l'échec du paiement 2 (plus de cascade partielle silencieuse).
            assert _live_revenue_entries(org_id, inv["id"]) == [], \
                "le revenu doit être contre-passé même si un paiement échoue"
            assert _live_payment_entries(org_id, pid1) == [], \
                "le 1er paiement doit être contre-passé malgré l'échec du 2e"
            # Le paiement 2 reste vivant (sa contre-passation a échoué) = le trou.
            assert len(_live_payment_entries(org_id, pid2)) == 1

            # Trou JOURNALISÉ durablement avant le delete physique.
            orphans = _orphans(org_id)
            assert len(orphans) == 1, "un orphan doit tracer le trou de cascade"
            o = orphans[0]
            assert o["source_type"] == "invoice"
            assert o["source_id"] == inv["id"]
            assert o["context"] == "delete_invoice_cascade"
            failed_ids = {f["source_id"] for f in o["failed_sources"]}
            assert failed_ids == {pid2}, "seul le paiement 2 est en échec"
            # La facture est bien physiquement supprimée (op métier prioritaire).
            r2b = client.get(f"/api/invoices/{inv['id']}", headers=h)
            assert r2b.status_code == 404
        finally:
            _cleanup(uid, org_id)

    def test_cascade_success_records_no_orphan(self, client):
        # Cascade nominale (tout réussit) → aucun orphan journalisé.
        uid, org_id, h = _setup_org(client, "fx2")
        try:
            inv = _create_draft_invoice(client, h)
            _set_status(client, h, inv["id"], "sent")
            _add_payment(client, h, inv["id"], 30.0)
            r = client.delete(f"/api/invoices/{inv['id']}", headers=h)
            assert r.status_code == 200, r.text
            assert _orphans(org_id) == [], \
                "cascade réussie → aucun orphan"
        finally:
            _cleanup(uid, org_id)


class TestFixT9ExpenseRegenNoHole:
    """Fix T9 #2 — PUT expense : si le repost échoue, pas de trou (restauration)."""

    def test_put_expense_repost_failure_restores_previous_entry(
            self, client, monkeypatch):
        # Une dépense postée (114.98). Au PUT, le repost (_autopost_expense) lève.
        # Sans le fix, l'unpost aurait réussi mais le repost échoué → AUCUNE
        # écriture vivante (charge disparue du GL). Avec le fix : l'écriture
        # PRÉCÉDENTE est restaurée → 1 vivant reflétant l'ANCIEN montant, et
        # autopost_error est posé (trou visible), le PUT reste 200.
        uid, org_id, h = _setup_org(client, "fx3")
        try:
            r = _create_expense(client, h, amount=114.98, gst=5.0, qst=9.98)
            exp = r.json()
            live_before = _live_expense_entries(org_id, exp["id"])
            assert len(live_before) == 1
            before_net = _net_by_number(org_id, live_before)
            assert before_net.get("5010") == 100.0

            def _boom(*a, **k):
                raise RuntimeError("boom-repost")

            monkeypatch.setattr(server_module, "_autopost_expense", _boom)
            r2 = client.put(f"/api/expenses/{exp['id']}", headers=h, json={
                "amount": 200.0, "gst_paid_cad": 0.0, "qst_paid_cad": 0.0,
            })
            assert r2.status_code == 200, r2.text

            # Anti-trou : une écriture vivante EXISTE encore (restaurée), pas de
            # disparition de la charge du grand livre.
            live_after = _live_expense_entries(org_id, exp["id"])
            assert len(live_after) == 1, \
                "l'écriture précédente doit être restaurée (pas de trou)"
            _assert_balanced_entry(org_id, live_after[0])
            after_net = _net_by_number(org_id, live_after)
            # Le vivant restauré reflète l'ANCIEN montant (114.98 TTC → charge 100).
            assert after_net.get("5010") == 100.0, \
                "le vivant restauré reflète l'ancien montant (véridique)"
            assert after_net.get("1000") == -114.98

            # Trou visible : autopost_error posé sur la dépense.
            doc = server_module.db.expenses.find_one(
                {"id": exp["id"], "organization_id": org_id}, {"_id": 0})
            assert "autopost_error" in doc
            assert "boom" not in doc["autopost_error"]
            # L'op métier a bien mis à jour le montant de la dépense.
            assert doc["amount"] == 200.0
        finally:
            _cleanup(uid, org_id)

    def test_put_expense_repost_success_still_regenerates(self, client):
        # Non-régression du fix : quand le repost RÉUSSIT, la régénération se
        # comporte comme avant (1 seul vivant reflétant le NOUVEAU montant).
        uid, org_id, h = _setup_org(client, "fx4")
        try:
            r = _create_expense(client, h, amount=114.98, gst=5.0, qst=9.98)
            exp = r.json()
            r2 = client.put(f"/api/expenses/{exp['id']}", headers=h, json={
                "amount": 200.0, "gst_paid_cad": 0.0, "qst_paid_cad": 0.0,
            })
            assert r2.status_code == 200, r2.text
            live = _live_expense_entries(org_id, exp["id"])
            assert len(live) == 1
            net = _net_by_number(org_id, live)
            assert net.get("5010") == 200.0, "le vivant reflète le nouveau montant"
            assert net.get("1000") == -200.0
            doc = server_module.db.expenses.find_one(
                {"id": exp["id"], "organization_id": org_id}, {"_id": 0})
            assert "autopost_error" not in doc
        finally:
            _cleanup(uid, org_id)


class TestFixT9LegacyDocMarking:
    """Fix T9 #3 — autopost_error posé/effacé même sur docs LEGACY sans org_id."""

    def test_autopost_error_marked_on_legacy_expense(self, client, monkeypatch):
        # Une dépense LEGACY (sans champ organization_id, matchée par le fallback
        # user_id de _org_scope). Sans le fix, _safe_autopost marquerait avec un
        # filtre STRICT {id, organization_id} qui NE matche PAS → no-op silencieux.
        # Avec le fix (legacy_user_id), l'autopost_error EST posé.
        uid, org_id, h = _setup_org(client, "fx5")
        try:
            # Insère une dépense legacy directement en DB : PAS d'organization_id,
            # seulement user_id (état pré-migration multi-tenant).
            legacy_id = str(uuid.uuid4())
            server_module.db.expenses.insert_one({
                "id": legacy_id, "user_id": uid,  # PAS d'organization_id
                "amount": 100.0, "currency": "CAD",
                "exchange_rate_to_cad": 1.0, "amount_cad": 100.0,
                "category_code": "office_supplies",
                "gst_paid_cad": 0.0, "qst_paid_cad": 0.0, "hst_paid_cad": 0.0,
                "expense_date": "2026-06-15", "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            # Sanity : le doc est bien matché par _org_scope (endpoint business).
            r_get = client.get("/api/expenses", headers=h)
            assert r_get.status_code == 200
            assert any(e["id"] == legacy_id for e in r_get.json())

            def _boom(*a, **k):
                raise RuntimeError("boom")

            monkeypatch.setattr(server_module, "_autopost_expense", _boom)
            # PUT sur le doc legacy → l'op métier réussit ; le repost échoue → le
            # fix doit poser autopost_error sur ce doc SANS organization_id.
            r = client.put(f"/api/expenses/{legacy_id}", headers=h,
                           json={"amount": 120.0})
            assert r.status_code == 200, r.text
            doc = server_module.db.expenses.find_one({"id": legacy_id}, {"_id": 0})
            assert "organization_id" not in doc, "doc reste legacy (non muté)"
            assert "autopost_error" in doc, \
                "fix T9 #3 : autopost_error posé même sur doc legacy sans org_id"
            assert "boom" not in doc["autopost_error"]
        finally:
            server_module.db.expenses.delete_many({"user_id": uid})
            _cleanup(uid, org_id)

    def test_legacy_marking_does_not_touch_other_org(self, client):
        # Isolation : le marquage legacy (fallback user_id) ne doit JAMAIS toucher
        # un doc d'une AUTRE org partageant le même id. On appelle _safe_autopost
        # directement avec un fn qui lève, pour un id partagé entre 2 docs.
        uidA, orgA, hA = _setup_org(client, "fx6a")
        uidB, orgB, hB = _setup_org(client, "fx6b")
        try:
            shared_id = str(uuid.uuid4())
            # Doc org B (avec organization_id = orgB) — NE doit PAS être touché.
            server_module.db.expenses.insert_one({
                "id": shared_id, "organization_id": orgB, "user_id": uidB,
                "amount": 1.0, "amount_cad": 1.0,
            })
            # Doc legacy de l'user A (sans organization_id) — CELUI-CI doit être
            # marqué. Même id (collision théorique) pour tester l'isolation.
            server_module.db.expenses.insert_one({
                "id": shared_id + "-legacyA", "user_id": uidA,
                "amount": 1.0, "amount_cad": 1.0,
            })

            def _boom():
                raise RuntimeError("boom")

            # Marque le doc legacy A par son id + legacy_user_id=uidA.
            server_module._safe_autopost(
                _boom, "expenses", shared_id + "-legacyA",
                {"organization_id": orgA}, legacy_user_id=uidA)

            legacyA = server_module.db.expenses.find_one(
                {"id": shared_id + "-legacyA"}, {"_id": 0})
            assert "autopost_error" in legacyA, "le doc legacy de A est marqué"
            # Le doc de l'org B (id partagé racine, org différente) reste INTACT.
            docB = server_module.db.expenses.find_one(
                {"id": shared_id, "organization_id": orgB}, {"_id": 0})
            assert "autopost_error" not in docB, \
                "aucune fuite cross-org : le doc org B n'est pas touché"
        finally:
            server_module.db.expenses.delete_many({"user_id": uidA})
            server_module.db.expenses.delete_many({"user_id": uidB})
            _cleanup(uidA, orgA)
            _cleanup(uidB, orgB)


# ─── Tâche 10 — Verrou endpoints manuels (entry_type=="auto" → 400) ───

_AUTO_LOCK_MSG = "Écriture générée automatiquement — modifiez le document source"


def _account_id_by_number(client, headers, number):
    """Renvoie l'id du compte au n° donné (seed lazy du plan au 1er accès)."""
    r = client.get("/api/ledger/accounts", headers=headers)
    assert r.status_code == 200, r.text
    for acc in r.json():
        if acc["account_number"] == number:
            return acc["id"]
    raise AssertionError(f"compte {number} introuvable")


def _posted_auto_entry(client, org_id, headers):
    """Pose une écriture auto (entry_type='auto', posted) via le hook facture
    draft→sent, et renvoie (inv_id, auto_entry)."""
    inv = _create_draft_invoice(client, headers)
    r = _set_status(client, headers, inv["id"], "sent")
    assert r.status_code == 200, r.text
    live = _live_revenue_entries(org_id, inv["id"])
    assert len(live) == 1, "1 écriture de revenu auto attendue"
    entry = live[0]
    assert entry["entry_type"] == "auto"
    assert entry["status"] == "posted"
    return inv["id"], entry


class TestManualEndpointsLockAutoEntries:
    """Tâche 10 — les 4 endpoints manuels refusent (400) toute mutation d'une
    écriture entry_type='auto' (décision #4). Message exact ; le document source
    reste le seul point de mutation."""

    def test_put_on_auto_entry_returns_400(self, client):
        uid, org_id, h = _setup_org(client, "t10put")
        try:
            _, entry = _posted_auto_entry(client, org_id, h)
            r = client.put(f"/api/ledger/entries/{entry['id']}", headers=h,
                           json={"description": "hack"})
            assert r.status_code == 400, r.text
            assert r.json()["detail"] == _AUTO_LOCK_MSG
            # L'écriture n'a PAS été mutée.
            fresh = server_module.db.journal_entries.find_one(
                {"id": entry["id"], "organization_id": org_id}, {"_id": 0})
            assert fresh["description"] != "hack"
        finally:
            _cleanup(uid, org_id)

    def test_post_on_auto_entry_returns_400(self, client):
        uid, org_id, h = _setup_org(client, "t10post")
        try:
            _, entry = _posted_auto_entry(client, org_id, h)
            r = client.post(f"/api/ledger/entries/{entry['id']}/post", headers=h)
            assert r.status_code == 400, r.text
            assert r.json()["detail"] == _AUTO_LOCK_MSG
        finally:
            _cleanup(uid, org_id)

    def test_reverse_on_auto_entry_returns_400(self, client):
        uid, org_id, h = _setup_org(client, "t10rev")
        try:
            _, entry = _posted_auto_entry(client, org_id, h)
            r = client.post(f"/api/ledger/entries/{entry['id']}/reverse",
                            headers=h, json={})
            assert r.status_code == 400, r.text
            assert r.json()["detail"] == _AUTO_LOCK_MSG
            # Aucune contre-passation manuelle n'a été créée : l'auto reste vivant.
            live = _live_revenue_entries(org_id, entry["source_id"])
            assert len(live) == 1
            assert live[0].get("reversed_by_entry_id") is None
        finally:
            _cleanup(uid, org_id)

    def test_delete_on_auto_entry_returns_400(self, client):
        uid, org_id, h = _setup_org(client, "t10del")
        try:
            _, entry = _posted_auto_entry(client, org_id, h)
            r = client.delete(f"/api/ledger/entries/{entry['id']}", headers=h)
            assert r.status_code == 400, r.text
            assert r.json()["detail"] == _AUTO_LOCK_MSG
            # L'écriture existe toujours.
            assert server_module.db.journal_entries.find_one(
                {"id": entry["id"], "organization_id": org_id}) is not None
        finally:
            _cleanup(uid, org_id)

    def test_auto_guard_fires_before_posted_check(self, client):
        # L'auto est aussi 'posted' : sans le verrou auto, PUT/DELETE renverraient
        # le message 'Écriture figée' (check status). Le verrou auto doit primer →
        # message AUTO, pas le message figée. Discrimine l'ordre des gardes.
        uid, org_id, h = _setup_org(client, "t10order")
        try:
            _, entry = _posted_auto_entry(client, org_id, h)
            r_put = client.put(f"/api/ledger/entries/{entry['id']}", headers=h,
                               json={"description": "x"})
            assert r_put.status_code == 400
            assert r_put.json()["detail"] == _AUTO_LOCK_MSG
            r_del = client.delete(f"/api/ledger/entries/{entry['id']}", headers=h)
            assert r_del.status_code == 400
            assert r_del.json()["detail"] == _AUTO_LOCK_MSG
        finally:
            _cleanup(uid, org_id)

    # ── Non-régression Phase 1 : les écritures 'manual' restent pleinement gérables ──

    def test_manual_draft_put_and_delete_still_work(self, client):
        uid, org_id, h = _setup_org(client, "t10man1")
        try:
            cash = _account_id_by_number(client, h, "1000")
            capital = _account_id_by_number(client, h, "3100")
            r = client.post("/api/ledger/entries", headers=h, json={
                "entry_date": "2026-06-15", "description": "Manuel test",
                "status": "draft",
                "lines": [
                    {"account_id": cash, "debit": 50.0, "credit": 0.0},
                    {"account_id": capital, "debit": 0.0, "credit": 50.0},
                ],
            })
            assert r.status_code == 201, r.text
            eid = r.json()["id"]
            assert r.json()["entry_type"] == "manual"
            # PUT (brouillon éditable — comportement Phase 1 inchangé).
            r_put = client.put(f"/api/ledger/entries/{eid}", headers=h,
                               json={"description": "Manuel édité"})
            assert r_put.status_code == 200, r_put.text
            assert r_put.json()["description"] == "Manuel édité"
            # DELETE (brouillon supprimable).
            r_del = client.delete(f"/api/ledger/entries/{eid}", headers=h)
            assert r_del.status_code == 204, r_del.text
            assert server_module.db.journal_entries.find_one(
                {"id": eid, "organization_id": org_id}) is None
        finally:
            _cleanup(uid, org_id)

    def test_manual_post_and_reverse_still_work(self, client):
        uid, org_id, h = _setup_org(client, "t10man2")
        try:
            cash = _account_id_by_number(client, h, "1000")
            capital = _account_id_by_number(client, h, "3100")
            r = client.post("/api/ledger/entries", headers=h, json={
                "entry_date": "2026-06-15", "description": "Manuel à poster",
                "status": "draft",
                "lines": [
                    {"account_id": cash, "debit": 75.0, "credit": 0.0},
                    {"account_id": capital, "debit": 0.0, "credit": 75.0},
                ],
            })
            assert r.status_code == 201, r.text
            eid = r.json()["id"]
            # POST (brouillon manuel → posté ; comportement Phase 1 inchangé).
            r_post = client.post(f"/api/ledger/entries/{eid}/post", headers=h)
            assert r_post.status_code == 200, r_post.text
            assert r_post.json()["status"] == "posted"
            # REVERSE (contre-passation manuelle Phase 1 toujours possible).
            r_rev = client.post(f"/api/ledger/entries/{eid}/reverse", headers=h,
                                json={})
            assert r_rev.status_code == 201, r_rev.text
            mirror = r_rev.json()
            assert mirror["reverses_entry_id"] == eid
            # Origine reste posted + liée au miroir (invariant Phase 1).
            origin = server_module.db.journal_entries.find_one(
                {"id": eid, "organization_id": org_id}, {"_id": 0})
            assert origin["status"] == "posted"
            assert origin["reversed_by_entry_id"] == mirror["id"]
        finally:
            _cleanup(uid, org_id)

    def test_internal_autopost_reversal_still_works(self, client):
        # Non-régression critique : le verrou HTTP ne doit PAS bloquer la
        # contre-passation INTERNE de l'auto-posting (_unpost_source_entry via
        # _reverse_entry_internal). sent→draft doit contre-passer le revenu auto.
        uid, org_id, h = _setup_org(client, "t10int")
        try:
            inv_id, entry = _posted_auto_entry(client, org_id, h)
            # sent → draft : hook interne contre-passe l'écriture auto.
            r = _set_status(client, h, inv_id, "draft")
            assert r.status_code == 200, r.text
            # Plus d'écriture vivante (contre-passée en interne).
            assert _live_revenue_entries(org_id, inv_id) == []
            # Un miroir POSTED existe ; net zéro (invariant §5.2).
            alle = _all_invoice_entries(org_id, inv_id)
            assert len(alle) == 2, "origine + miroir"
            net = _net_by_number(org_id, alle)
            assert all(abs(v) <= 0.005 for v in net.values()), \
                f"net non nul après contre-passation interne: {net}"
        finally:
            _cleanup(uid, org_id)

    # ── FIX T10 : le verrou couvre AUSSI le miroir interne (entry_type='reversal'
    #    mais porteur de source_type/source_id). Sans quoi contre-passer le miroir
    #    ré-instaure un revenu fantôme sur une facture 'draft' (FAUX en compta). ──

    def _internal_reversal_mirror(self, client, org_id, h):
        """Crée l'auto-posting d'une facture (draft→sent) PUIS le miroir interne
        (sent→draft). Renvoie (inv_id, mirror_entry) : le miroir porte
        entry_type='reversal', source_type='invoice', source_id=inv_id."""
        inv_id, _origin = _posted_auto_entry(client, org_id, h)
        r = _set_status(client, h, inv_id, "draft")
        assert r.status_code == 200, r.text
        alle = _all_invoice_entries(org_id, inv_id)
        mirrors = [e for e in alle if e["entry_type"] == "reversal"]
        assert len(mirrors) == 1, "1 miroir interne attendu"
        mirror = mirrors[0]
        assert mirror["source_type"] == "invoice"
        assert mirror["source_id"] == inv_id
        assert mirror["status"] == "posted"
        return inv_id, mirror

    def test_reverse_on_internal_mirror_returns_400(self, client):
        # Vecteur [COMPTA] : contre-passer manuellement le miroir interne (type
        # 'reversal', porteur de source_id) ré-instaurerait le revenu fantôme sur
        # une facture 'draft'. Le verrou durci (source_id is not None) doit le
        # refuser (400) et laisser le net à zéro.
        uid, org_id, h = _setup_org(client, "t10mirrev")
        try:
            inv_id, mirror = self._internal_reversal_mirror(client, org_id, h)
            r = client.post(f"/api/ledger/entries/{mirror['id']}/reverse",
                            headers=h, json={})
            assert r.status_code == 400, r.text
            assert r.json()["detail"] == _AUTO_LOCK_MSG
            # Aucun 2e miroir : toujours 2 écritures (origine + 1 miroir), net nul.
            alle = _all_invoice_entries(org_id, inv_id)
            assert len(alle) == 2, "pas de 2e miroir créé"
            net = _net_by_number(org_id, alle)
            assert all(abs(v) <= 0.005 for v in net.values()), \
                f"revenu fantôme ré-instauré sur facture draft: {net}"
            # Le miroir n'a PAS gagné de reversed_by_entry_id.
            fresh = server_module.db.journal_entries.find_one(
                {"id": mirror["id"], "organization_id": org_id}, {"_id": 0})
            assert fresh.get("reversed_by_entry_id") is None
        finally:
            _cleanup(uid, org_id)

    def test_put_post_delete_on_internal_mirror_return_400(self, client):
        # Les 3 autres endpoints manuels doivent aussi refuser le miroir interne
        # porteur de source_id (write machine liée à un doc source).
        uid, org_id, h = _setup_org(client, "t10mirmut")
        try:
            _inv_id, mirror = self._internal_reversal_mirror(client, org_id, h)
            mid = mirror["id"]
            r_put = client.put(f"/api/ledger/entries/{mid}", headers=h,
                               json={"description": "hack"})
            assert r_put.status_code == 400, r_put.text
            assert r_put.json()["detail"] == _AUTO_LOCK_MSG
            r_post = client.post(f"/api/ledger/entries/{mid}/post", headers=h)
            assert r_post.status_code == 400, r_post.text
            assert r_post.json()["detail"] == _AUTO_LOCK_MSG
            r_del = client.delete(f"/api/ledger/entries/{mid}", headers=h)
            assert r_del.status_code == 400, r_del.text
            assert r_del.json()["detail"] == _AUTO_LOCK_MSG
            # Miroir intact.
            assert server_module.db.journal_entries.find_one(
                {"id": mid, "organization_id": org_id}) is not None
        finally:
            _cleanup(uid, org_id)

    def test_manual_reversal_of_manual_entry_not_blocked_by_fix(self, client):
        # Non-régression du FIX : la contre-passation MANUELLE d'une écriture
        # manuelle postée (source_type/source_id = None) doit rester 201. Le
        # verrou durci ne matche que 'auto' OU source_id non nul — un manuel n'a
        # NI l'un NI l'autre. Puis le miroir manuel produit (source=None) reste
        # lui-même contre-passable (chaîne de corrections manuelles Phase 1).
        uid, org_id, h = _setup_org(client, "t10manrev")
        try:
            cash = _account_id_by_number(client, h, "1000")
            capital = _account_id_by_number(client, h, "3100")
            r = client.post("/api/ledger/entries", headers=h, json={
                "entry_date": "2026-06-15", "description": "Manuel à contre-passer",
                "status": "draft",
                "lines": [
                    {"account_id": cash, "debit": 60.0, "credit": 0.0},
                    {"account_id": capital, "debit": 0.0, "credit": 60.0},
                ],
            })
            assert r.status_code == 201, r.text
            eid = r.json()["id"]
            assert r.json()["entry_type"] == "manual"
            assert r.json()["source_id"] is None
            r_post = client.post(f"/api/ledger/entries/{eid}/post", headers=h)
            assert r_post.status_code == 200, r_post.text
            # Reverse manuel → 201 (PAS bloqué par le verrou durci).
            r_rev = client.post(f"/api/ledger/entries/{eid}/reverse", headers=h,
                                json={})
            assert r_rev.status_code == 201, r_rev.text
            mirror = r_rev.json()
            assert mirror["reverses_entry_id"] == eid
            assert mirror["source_type"] is None
            assert mirror["source_id"] is None
            # Le miroir manuel (source=None) est lui-même contre-passable.
            r_rev2 = client.post(
                f"/api/ledger/entries/{mirror['id']}/reverse", headers=h, json={})
            assert r_rev2.status_code == 201, r_rev2.text
        finally:
            _cleanup(uid, org_id)


# ─── Tâche 11 — Endpoints /api/ledger/autopost/status + repair (§8.1) ───


class TestAutopostStatusRepair:
    """Tâche 11 — diagnostic de couverture (status) + réparation rejouable
    (repair). Shape exact §8.1 ; coverage filtré par org ; repair idempotent."""

    def test_status_shape_and_settings(self, client):
        # Le status reflète le flag et le compte de crédit par défaut de l'org,
        # avec le shape complet (spec §8.1).
        uid, org_id, h = _setup_org(client, "t11shape")
        try:
            r = client.get("/api/ledger/autopost/status", headers=h)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["enabled"] is True
            assert body["expense_default_credit_account"] == "1000"
            assert body["pending_errors"] == 0
            cov = body["coverage"]
            assert set(cov.keys()) == {
                "invoices_posted", "invoices_total_postable",
                "expenses_posted", "expenses_total",
            }
            assert cov == {
                "invoices_posted": 0, "invoices_total_postable": 0,
                "expenses_posted": 0, "expenses_total": 0,
            }
        finally:
            _cleanup(uid, org_id)

    def test_status_coverage_one_of_two_invoices_posted(self, client):
        # 2 factures postables (status != draft) ; une seule postée → 1/2.
        uid, org_id, h = _setup_org(client, "t11cov")
        try:
            inv1 = _create_draft_invoice(client, h)
            inv2 = _create_draft_invoice(client, h)
            # inv1 postée (draft→sent poste le revenu), inv2 forcée en 'sent'
            # SANS écriture (autopost désactivé le temps du 2e passage).
            r1 = _set_status(client, h, inv1["id"], "sent")
            assert r1.status_code == 200, r1.text
            # inv2 : passer en sent sans poster → on désactive le flag le temps
            # de la transition, puis on le rétablit.
            server_module.db.company_settings.update_one(
                {"organization_id": org_id},
                {"$set": {"autopost_enabled": False}})
            r2 = _set_status(client, h, inv2["id"], "sent")
            assert r2.status_code == 200, r2.text
            server_module.db.company_settings.update_one(
                {"organization_id": org_id},
                {"$set": {"autopost_enabled": True}})

            r = client.get("/api/ledger/autopost/status", headers=h)
            assert r.status_code == 200, r.text
            cov = r.json()["coverage"]
            assert cov["invoices_total_postable"] == 2, \
                "2 factures non-draft = postables"
            assert cov["invoices_posted"] == 1, "seule inv1 a une écriture vivante"
        finally:
            _cleanup(uid, org_id)

    def test_draft_invoice_not_counted_postable(self, client):
        # Une facture restée draft n'est PAS postable (accrual : pas de revenu).
        uid, org_id, h = _setup_org(client, "t11draft")
        try:
            _create_draft_invoice(client, h)  # reste draft
            r = client.get("/api/ledger/autopost/status", headers=h)
            cov = r.json()["coverage"]
            assert cov["invoices_total_postable"] == 0
            assert cov["invoices_posted"] == 0
        finally:
            _cleanup(uid, org_id)

    def test_status_expenses_coverage(self, client):
        # 2 dépenses créées (autopost ON) → 2 postées / 2 total.
        uid, org_id, h = _setup_org(client, "t11exp")
        try:
            _create_expense(client, h, amount=100.0, gst=0.0, qst=0.0)
            _create_expense(client, h, amount=50.0, gst=0.0, qst=0.0)
            r = client.get("/api/ledger/autopost/status", headers=h)
            cov = r.json()["coverage"]
            assert cov["expenses_total"] == 2
            assert cov["expenses_posted"] == 2
        finally:
            _cleanup(uid, org_id)

    def test_repair_replays_failed_expense(self, client):
        # Simule un échec de post sur une dépense (autopost_error posé sans
        # écriture vivante), puis repair → rejoue, efface l'erreur, 1 réparé.
        uid, org_id, h = _setup_org(client, "t11rep")
        try:
            # Crée la dépense avec l'auto-post monkeypatché pour échouer, ce qui
            # pose un autopost_error SANS écriture vivante.
            mp = pytest.MonkeyPatch()
            try:
                def _boom(*a, **k):
                    raise RuntimeError("compte 5xxx introuvable")
                mp.setattr(server_module, "_autopost_expense", _boom)
                r = _create_expense(client, h, amount=100.0, gst=0.0, qst=0.0)
                assert r.status_code == 200, r.text
                exp = r.json()
            finally:
                mp.undo()

            # autopost_error posé, aucune écriture vivante.
            doc = server_module.db.expenses.find_one(
                {"id": exp["id"], "organization_id": org_id}, {"_id": 0})
            assert "autopost_error" in doc
            assert _live_expense_entries(org_id, exp["id"]) == []

            # status → pending_errors == 1.
            r_st = client.get("/api/ledger/autopost/status", headers=h)
            assert r_st.json()["pending_errors"] == 1

            # repair → rejoue (le mapping réel fonctionne maintenant).
            r_rep = client.post("/api/ledger/autopost/repair", headers=h)
            assert r_rep.status_code == 200, r_rep.text
            body = r_rep.json()
            assert body["repaired"] == 1
            assert body["still_failing"] == []

            # écriture vivante recréée, autopost_error effacé.
            assert len(_live_expense_entries(org_id, exp["id"])) == 1
            fresh = server_module.db.expenses.find_one(
                {"id": exp["id"], "organization_id": org_id}, {"_id": 0})
            assert "autopost_error" not in fresh

            # status → pending_errors == 0.
            r_st2 = client.get("/api/ledger/autopost/status", headers=h)
            assert r_st2.json()["pending_errors"] == 0
        finally:
            _cleanup(uid, org_id)

    def test_repair_reports_still_failing(self, client):
        # Si le post échoue TOUJOURS au repair (compte réellement introuvable),
        # le doc reste dans still_failing et garde son autopost_error.
        uid, org_id, h = _setup_org(client, "t11stillfail")
        try:
            mp = pytest.MonkeyPatch()
            try:
                def _boom(*a, **k):
                    raise RuntimeError("boom")
                mp.setattr(server_module, "_autopost_expense", _boom)
                r = _create_expense(client, h, amount=100.0, gst=0.0, qst=0.0)
                exp = r.json()
                # repair pendant que le mapping échoue encore.
                r_rep = client.post("/api/ledger/autopost/repair", headers=h)
                assert r_rep.status_code == 200, r_rep.text
                body = r_rep.json()
                assert body["repaired"] == 0
                assert exp["id"] in body["still_failing"]
            finally:
                mp.undo()
            # l'erreur persiste (rien de vivant).
            doc = server_module.db.expenses.find_one(
                {"id": exp["id"], "organization_id": org_id}, {"_id": 0})
            assert "autopost_error" in doc
        finally:
            _cleanup(uid, org_id)

    def test_repair_replays_failed_invoice(self, client):
        # Repair couvre aussi les factures (invoice→_autopost_invoice_revenue).
        uid, org_id, h = _setup_org(client, "t11repinv")
        try:
            inv = _create_draft_invoice(client, h)
            mp = pytest.MonkeyPatch()
            try:
                def _boom(*a, **k):
                    raise RuntimeError("4000 introuvable")
                mp.setattr(server_module, "_autopost_invoice_revenue", _boom)
                r = _set_status(client, h, inv["id"], "sent")
                assert r.status_code == 200, r.text
            finally:
                mp.undo()
            doc = server_module.db.invoices.find_one(
                {"id": inv["id"], "organization_id": org_id}, {"_id": 0})
            assert "autopost_error" in doc
            assert _live_revenue_entries(org_id, inv["id"]) == []

            r_rep = client.post("/api/ledger/autopost/repair", headers=h)
            assert r_rep.status_code == 200, r_rep.text
            assert r_rep.json()["repaired"] == 1
            assert len(_live_revenue_entries(org_id, inv["id"])) == 1
            fresh = server_module.db.invoices.find_one(
                {"id": inv["id"], "organization_id": org_id}, {"_id": 0})
            assert "autopost_error" not in fresh
        finally:
            _cleanup(uid, org_id)

    def test_repair_idempotent_no_errors(self, client):
        # repair sans aucune erreur en attente → repaired 0, still_failing vide.
        uid, org_id, h = _setup_org(client, "t11noerr")
        try:
            r = client.post("/api/ledger/autopost/repair", headers=h)
            assert r.status_code == 200, r.text
            assert r.json() == {"repaired": 0, "still_failing": []}
        finally:
            _cleanup(uid, org_id)

    def test_repair_noop_when_autopost_disabled(self, client):
        # [COMPTA] (fix reviewer #1) Si l'org a désactivé l'auto-posting APRÈS
        # avoir accumulé un autopost_error, /repair est un no-op (aligné sur la
        # sémantique opt-in des hooks métier, décision #10) : il ne re-poste PAS,
        # renvoie {repaired:0, still_failing:[]}, et l'autopost_error persiste.
        uid, org_id, h = _setup_org(client, "t11disabled")
        try:
            # 1) autopost ON : crée une dépense dont le mapping échoue → pose un
            #    autopost_error sans écriture vivante.
            mp = pytest.MonkeyPatch()
            try:
                def _boom(*a, **k):
                    raise RuntimeError("compte 5xxx introuvable")
                mp.setattr(server_module, "_autopost_expense", _boom)
                r = _create_expense(client, h, amount=100.0, gst=0.0, qst=0.0)
                assert r.status_code == 200, r.text
                exp = r.json()
            finally:
                mp.undo()
            assert "autopost_error" in server_module.db.expenses.find_one(
                {"id": exp["id"], "organization_id": org_id}, {"_id": 0})
            assert _live_expense_entries(org_id, exp["id"]) == []

            # 2) l'org désactive l'auto-posting.
            server_module.db.company_settings.update_one(
                {"organization_id": org_id},
                {"$set": {"autopost_enabled": False}})

            # 3) repair → no-op : rien réparé, rien re-posté, erreur intacte.
            r_rep = client.post("/api/ledger/autopost/repair", headers=h)
            assert r_rep.status_code == 200, r_rep.text
            assert r_rep.json() == {"repaired": 0, "still_failing": []}
            # AUCUNE écriture vivante recréée (flag OFF ⇒ pas de re-post).
            assert _live_expense_entries(org_id, exp["id"]) == []
            # l'autopost_error persiste (le trou reste diagnosticable via /status).
            assert "autopost_error" in server_module.db.expenses.find_one(
                {"id": exp["id"], "organization_id": org_id}, {"_id": 0})

            # 4) réactiver le flag → /repair rejoue et comble le trou.
            server_module.db.company_settings.update_one(
                {"organization_id": org_id},
                {"$set": {"autopost_enabled": True}})
            r_rep2 = client.post("/api/ledger/autopost/repair", headers=h)
            assert r_rep2.status_code == 200, r_rep2.text
            assert r_rep2.json()["repaired"] == 1
            assert len(_live_expense_entries(org_id, exp["id"])) == 1
        finally:
            _cleanup(uid, org_id)

    def test_coverage_isolated_by_org(self, client):
        # Org B ne figure JAMAIS dans le coverage de A (isolation stricte).
        uidA, orgA, hA = _setup_org(client, "t11isoa")
        uidB, orgB, hB = _setup_org(client, "t11isob")
        try:
            # Org A : 1 facture postée + 1 dépense.
            invA = _create_draft_invoice(client, hA)
            _set_status(client, hA, invA["id"], "sent")
            _create_expense(client, hA, amount=100.0, gst=0.0, qst=0.0)
            # Org B : 3 factures postées + 2 dépenses (bruit).
            for _ in range(3):
                inv = _create_draft_invoice(client, hB)
                _set_status(client, hB, inv["id"], "sent")
            _create_expense(client, hB, amount=10.0, gst=0.0, qst=0.0)
            _create_expense(client, hB, amount=20.0, gst=0.0, qst=0.0)

            covA = client.get(
                "/api/ledger/autopost/status", headers=hA).json()["coverage"]
            assert covA["invoices_total_postable"] == 1, \
                "coverage de A ne compte QUE ses propres factures"
            assert covA["invoices_posted"] == 1
            assert covA["expenses_total"] == 1
            assert covA["expenses_posted"] == 1
        finally:
            _cleanup(uidA, orgA)
            _cleanup(uidB, orgB)

    def test_repair_isolated_by_org(self, client):
        # Le repair de A ne rejoue JAMAIS un doc en erreur d'une autre org.
        uidA, orgA, hA = _setup_org(client, "t11ripa")
        uidB, orgB, hB = _setup_org(client, "t11ripb")
        try:
            # Org B a une dépense en erreur (autopost_error posé sans écriture).
            mp = pytest.MonkeyPatch()
            try:
                def _boom(*a, **k):
                    raise RuntimeError("boom")
                mp.setattr(server_module, "_autopost_expense", _boom)
                rB = _create_expense(client, hB, amount=100.0, gst=0.0, qst=0.0)
                expB = rB.json()
            finally:
                mp.undo()
            # Repair côté A → ne touche PAS la dépense de B.
            r_rep = client.post("/api/ledger/autopost/repair", headers=hA)
            assert r_rep.status_code == 200, r_rep.text
            assert r_rep.json()["repaired"] == 0
            assert expB["id"] not in r_rep.json()["still_failing"]
            # La dépense de B garde son erreur (non touchée par le repair de A).
            docB = server_module.db.expenses.find_one(
                {"id": expB["id"], "organization_id": orgB}, {"_id": 0})
            assert "autopost_error" in docB
        finally:
            _cleanup(uidA, orgA)
            _cleanup(uidB, orgB)

    def test_status_requires_read_permission(self, client):
        # Le status exige accounting:read (RouteGuard Phase 1).
        uid, org_id, h = _setup_org(client, "t11perm")
        try:
            # retire accounting:read au rôle viewer et bascule l'user en viewer.
            server_module.db.users.update_one(
                {"id": uid}, {"$set": {"role": "viewer"}})
            server_module.db.organizations.update_one(
                {"id": org_id},
                {"$set": {"role_permissions.viewer": []}})
            r = client.get("/api/ledger/autopost/status", headers=h)
            assert r.status_code == 403, r.text
        finally:
            _cleanup(uid, org_id)

    def test_repair_requires_write_permission(self, client):
        # Le repair exige accounting:write.
        uid, org_id, h = _setup_org(client, "t11permw")
        try:
            server_module.db.users.update_one(
                {"id": uid}, {"$set": {"role": "viewer"}})
            server_module.db.organizations.update_one(
                {"id": org_id},
                {"$set": {"role_permissions.viewer": ["accounting:read"]}})
            r = client.post("/api/ledger/autopost/repair", headers=h)
            assert r.status_code == 403, r.text
        finally:
            _cleanup(uid, org_id)
