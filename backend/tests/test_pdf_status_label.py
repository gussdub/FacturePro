"""Tests — statut imprimé sur le PDF d'une facture / soumission envoyée par courriel.

Défaut corrigé : le PDF joint au courriel était généré AVANT le passage à « sent »,
donc le client recevait « Statut: DRAFT » alors que le PDF retéléchargé affichait
« SENT » — et les deux en anglais. Le statut doit être en français et refléter
l'état APRÈS l'envoi. Un renvoi ne doit pas faire régresser une facture payée.

Base remplacée par mongomock (aucun serveur Mongo requis).
"""
import io
import os
import sys
import uuid as _uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")
os.environ.setdefault("DB_NAME", "facturepro")

import mongomock  # noqa: E402
import pytest  # noqa: E402
from pypdf import PdfReader  # noqa: E402
from backend import server  # noqa: E402

ORG = "ORG-PDF-STATUS"


def _pdf_text(buf_or_bytes) -> str:
    data = buf_or_bytes if isinstance(buf_or_bytes, bytes) else buf_or_bytes.read()
    return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)


@pytest.fixture
def env(monkeypatch):
    fake = mongomock.MongoClient().db
    monkeypatch.setattr(server, "db", fake)
    monkeypatch.setattr(server, "_sync_collection", lambda name: fake[name])
    monkeypatch.setattr(server, "RESEND_API_KEY", "re_test")
    captured = {}

    class _Emails:
        @staticmethod
        def send(params):
            captured.update(params)
            return {"id": "email_test"}
    monkeypatch.setattr(server.resend, "Emails", _Emails)
    fake.clients.insert_one({"id": "cli1", "organization_id": ORG, "name": "Client Test",
                             "email": "client@example.com"})
    user = server.CurrentUser(id="u1", email="owner@example.com", organization_id=ORG,
                              role="owner", permissions=[])
    return fake, user, captured


def _attached_pdf_text(captured) -> str:
    import base64
    return _pdf_text(base64.b64decode(captured["attachments"][0]["content"]))


class TestLabels:
    @pytest.mark.parametrize("status,label", [
        ("draft", "Brouillon"), ("sent", "Envoyée"), ("partial", "Partiellement payée"),
        ("paid", "Payée"), ("overdue", "En retard")])
    def test_invoice_labels_fr(self, status, label):
        assert server._doc_status_label_fr("invoice", status) == label

    def test_quote_labels_fr(self):
        assert server._doc_status_label_fr("quote", "pending") == "En attente"
        assert server._doc_status_label_fr("quote", "accepted") == "Acceptée"

    def test_unknown_status_omitted(self):
        assert server._doc_status_label_fr("invoice", "weird") == ""
        assert server._doc_status_label_fr("invoice", None) == ""

    def test_pdf_never_prints_english_code(self):
        doc = {"invoice_number": "INV-1", "status": "sent", "items": [], "total": 0,
               "client_id": "cli1"}
        text = _pdf_text(server.generate_document_pdf("invoice", doc, {}, {"name": "C"}, []))
        assert "ENVOYÉE" in text
        assert "SENT" not in text


class TestInvoiceEmail:
    def _invoice(self, fake, status):
        inv = {"id": str(_uuid.uuid4()), "organization_id": ORG, "client_id": "cli1",
               "invoice_number": "INV-42", "status": status, "items": [], "total": 0}
        fake.invoices.insert_one(dict(inv))
        return inv

    def test_draft_sent_pdf_says_envoyee(self, env):
        fake, user, captured = env
        inv = self._invoice(fake, "draft")
        server._send_invoice_core(inv, user, {})
        text = _attached_pdf_text(captured)
        assert "ENVOYÉE" in text
        assert "DRAFT" not in text and "BROUILLON" not in text
        assert fake.invoices.find_one({"id": inv["id"]})["status"] == "sent"

    def test_resend_paid_invoice_keeps_paid(self, env):
        fake, user, captured = env
        inv = self._invoice(fake, "paid")
        server._send_invoice_core(inv, user, {})
        assert "PAYÉE" in _attached_pdf_text(captured)
        assert fake.invoices.find_one({"id": inv["id"]})["status"] == "paid"

    def test_resend_partial_invoice_keeps_partial(self, env):
        fake, user, captured = env
        inv = self._invoice(fake, "partial")
        server._send_invoice_core(inv, user, {})
        assert fake.invoices.find_one({"id": inv["id"]})["status"] == "partial"

    def test_downloaded_pdf_matches_sent_pdf(self, env):
        """Le PDF retéléchargé après l'envoi affiche le même statut que celui reçu."""
        fake, user, captured = env
        inv = self._invoice(fake, "draft")
        server._send_invoice_core(inv, user, {})
        stored = fake.invoices.find_one({"id": inv["id"]}, {"_id": 0})
        downloaded = _pdf_text(server.generate_document_pdf("invoice", stored, {}, {"name": "C"}, []))
        assert "ENVOYÉE" in downloaded and "ENVOYÉE" in _attached_pdf_text(captured)


class TestQuoteEmail:
    def test_pending_quote_sent_pdf_says_envoyee(self, env):
        fake, user, captured = env
        q = {"id": str(_uuid.uuid4()), "organization_id": ORG, "client_id": "cli1",
             "quote_number": "SOU-7", "status": "pending", "items": [], "total": 0,
             "created_by_user_id": "u1"}
        fake.quotes.insert_one(dict(q))
        server.send_quote_email(q["id"], {}, user)
        assert "ENVOYÉE" in _attached_pdf_text(captured)
        assert fake.quotes.find_one({"id": q["id"]})["status"] == "sent"

    def test_resend_accepted_quote_keeps_accepted(self, env):
        fake, user, captured = env
        q = {"id": str(_uuid.uuid4()), "organization_id": ORG, "client_id": "cli1",
             "quote_number": "SOU-8", "status": "accepted", "items": [], "total": 0,
             "created_by_user_id": "u1"}
        fake.quotes.insert_one(dict(q))
        server.send_quote_email(q["id"], {}, user)
        assert "ACCEPTÉE" in _attached_pdf_text(captured)
        assert fake.quotes.find_one({"id": q["id"]})["status"] == "accepted"
