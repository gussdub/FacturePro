"""Abonnement mensuel récurrent — garde d'accès, cartographie des statuts, webhooks.

Ces tests n'appellent JAMAIS le réseau : `stripe.Webhook.construct_event` est monkeypatché,
comme dans tests/test_organizations_integration.py:213.
"""
import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))

import uuid
from datetime import datetime, timezone, timedelta

import pytest
import server as server_module
from fastapi import HTTPException
from fastapi.testclient import TestClient


def _sub(period_ends, status="active", sub_id="sub_test", customer="cus_test"):
    """Construit un objet d'abonnement Stripe de la forme RÉELLE (2026-06-24.dahlia) :
    current_period_end est sur les ITEMS, pas à la racine."""
    return {
        "id": sub_id,
        "customer": customer,
        "status": status,
        "items": {"data": [{"current_period_end": e} for e in period_ends]},
    }


class TestSubscriptionPeriodEnd:
    def test_lit_la_date_sur_les_items(self):
        ts = 1789000000
        got = server_module._subscription_period_end(_sub([ts]))
        assert got == datetime.fromtimestamp(ts, timezone.utc).isoformat()

    def test_prend_le_maximum_de_plusieurs_items(self):
        got = server_module._subscription_period_end(_sub([1700000000, 1789000000, 1750000000]))
        assert got == datetime.fromtimestamp(1789000000, timezone.utc).isoformat()

    def test_ancienne_forme_racine_ignoree(self):
        """RÉGRESSION : un objet portant le champ à la RACINE (l'ancienne forme, celle que
        tous les tutoriels montrent) ne doit PAS produire de date. Si ce test passe au vert avec
        une implémentation qui lit la racine, c'est que le piège est revenu."""
        assert server_module._subscription_period_end(
            {"id": "sub_x", "current_period_end": 1789000000, "items": {"data": []}}) is None

    def test_aucun_item_renvoie_none(self):
        assert server_module._subscription_period_end(_sub([])) is None

    def test_objet_malforme_renvoie_none(self):
        for bad in ({}, {"items": None}, {"items": {"data": [{}]}}, {"items": {"data": [{"current_period_end": None}]}}):
            assert server_module._subscription_period_end(bad) is None


class TestStatusMapping:
    @pytest.mark.parametrize("stripe_status,attendu", [
        ("active", "active"),
        ("trialing", "active"),
        ("past_due", "past_due"),
        ("canceled", "canceled"),
        ("incomplete_expired", "suspended"),
        ("incomplete", "suspended"),
        ("unpaid", "suspended"),
        ("paused", "suspended"),
    ])
    def test_les_huit_statuts_stripe(self, stripe_status, attendu):
        assert server_module._map_stripe_status(stripe_status) == attendu

    def test_statut_inconnu_ferme_l_acces(self):
        """Une valeur future de Stripe, ou une donnée corrompue, ne doit JAMAIS ouvrir l'accès."""
        for s in ("une_nouveaute_stripe_2027", "", None, 42):
            assert server_module._map_stripe_status(s) == "suspended"

    def test_statuts_terminaux(self):
        """Seuls ces deux-là doivent poser terminated_at (la purge de rétention s'en servira)."""
        assert server_module._STRIPE_TERMINAL == {"canceled", "incomplete_expired"}


class TestAccessGate:
    @staticmethod
    def _call(org, user):
        """Renvoie None si l'accès est accordé, le code HTTP s'il est refusé."""
        try:
            server_module._check_subscription_active(org, user)
            return None
        except HTTPException as e:
            return e.status_code

    def _org(self, **kw):
        base = {"subscription_status": "active"}
        base.update(kw)
        return base

    def _end_in(self, days):
        return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

    def test_acces_autorise_6_jours_apres_la_fin(self):
        """Grâce de 7 j : un webhook manqué ne doit pas bloquer un bon payeur."""
        org = self._org(subscription_current_period_end=self._end_in(-6))
        assert self._call(org, {"email": "a@b.test"}) is None

    def test_acces_refuse_8_jours_apres_la_fin(self):
        """Et l'accès se ferme TOUT SEUL : c'est ce qui corrige le défaut d'origine."""
        org = self._org(subscription_current_period_end=self._end_in(-8))
        assert self._call(org, {"email": "a@b.test"}) == 402

    def test_active_sans_date_est_refuse(self):
        """INVARIANT. Un statut qui ouvre l'accès DOIT porter une date, sinon le bug d'accès
        éternel revient par la porte arrière."""
        assert self._call(self._org(), {"email": "a@b.test"}) == 402

    def test_past_due_garde_l_acces_pendant_la_periode_payee(self):
        org = self._org(subscription_status="past_due",
                        subscription_current_period_end=self._end_in(3))
        assert self._call(org, {"email": "a@b.test"}) is None

    def test_canceled_garde_l_acces_jusqua_la_fin_payee(self):
        """CGU art. 10 : « la résiliation prend effet à la fin de la période en cours »."""
        org = self._org(subscription_status="canceled",
                        subscription_current_period_end=self._end_in(3))
        assert self._call(org, {"email": "a@b.test"}) is None

    def test_suspended_refuse_meme_avec_une_date_valide(self):
        org = self._org(subscription_status="suspended",
                        subscription_current_period_end=self._end_in(30))
        assert self._call(org, {"email": "a@b.test"}) == 402

    def test_statut_inconnu_refuse(self):
        org = self._org(subscription_status="chose_inconnue",
                        subscription_current_period_end=self._end_in(30))
        assert self._call(org, {"email": "a@b.test"}) == 402

    def test_compte_exempte_jamais_bloque(self):
        """Le propriétaire ne doit JAMAIS pouvoir se verrouiller hors de son propre produit."""
        org = self._org(subscription_status="suspended",
                        subscription_current_period_end=self._end_in(-999))
        assert self._call(org, {"email": server_module.EXEMPT_USERS[0]}) is None

    def test_essai_non_echu_autorise(self):
        org = {"subscription_status": "trial", "trial_ends_at": self._end_in(5)}
        assert self._call(org, {"email": "a@b.test"}) is None

    def test_essai_echu_refuse(self):
        org = {"subscription_status": "trial", "trial_ends_at": self._end_in(-1)}
        assert self._call(org, {"email": "a@b.test"}) == 402

    def test_date_naive_de_mongo_ne_leve_pas(self):
        """Mongo rend des datetimes naïfs : comparer naïf et aware lève un TypeError."""
        naive = (datetime.now(timezone.utc) + timedelta(days=3)).replace(tzinfo=None).isoformat()
        org = self._org(subscription_current_period_end=naive)
        assert self._call(org, {"email": "a@b.test"}) is None

    def test_trial_sans_date_autorise(self):
        """Comportement historique délibérément conservé : un essai sans date n'est pas bloqué.
        Documenté par un test pour qu'une inversion future soit visible."""
        assert self._call({"subscription_status": "trial"}, {"email": "a@b.test"}) is None

    def test_trial_date_illisible_autorise(self):
        """On ne bloque pas un utilisateur sur la foi d'une donnée corrompue."""
        assert self._call({"subscription_status": "trial", "trial_ends_at": "pas-une-date"},
                          {"email": "a@b.test"}) is None

    def test_trial_date_naive_comparee_sans_erreur(self):
        naive = (datetime.now(timezone.utc) + timedelta(days=5)).replace(tzinfo=None).isoformat()
        assert self._call({"subscription_status": "trial", "trial_ends_at": naive},
                          {"email": "a@b.test"}) is None

    def test_objet_datetime_de_mongo_sur_les_deux_branches(self):
        """RÉGRESSION : pymongo peut rendre un objet datetime au lieu d'une chaîne ISO.
        Avant le correctif, un essai ÉCHU obtenait l'accès (fromisoformat lève -> except -> return)
        et un abonné PAYANT était refusé (fromisoformat lève -> 402). Les deux sont faux."""
        echu = datetime.now(timezone.utc) - timedelta(days=300)
        valide = datetime.now(timezone.utc) + timedelta(days=20)
        assert self._call({"subscription_status": "trial", "trial_ends_at": echu},
                          {"email": "a@b.test"}) == 402, "un essai échu doit être refusé"
        assert self._call({"subscription_status": "active",
                           "subscription_current_period_end": valide},
                          {"email": "a@b.test"}) is None, "un abonné payant doit garder l'accès"


class TestCheckoutSubscription:
    def test_session_creee_en_mode_abonnement(self, monkeypatch):
        captured = {}

        def fake_create(**kw):
            captured.update(kw)
            class S:
                id = "cs_test_123"
                url = "https://checkout.stripe.test/cs_test_123"
            return S()

        monkeypatch.setattr(server_module.stripe.checkout.Session, "create", fake_create)
        monkeypatch.setattr(server_module, "STRIPE_API_KEY", "sk_test_dummy")
        monkeypatch.setattr(server_module.db.payment_transactions, "insert_one", lambda d: None)

        client = TestClient(server_module.app)
        login = client.post("/api/auth/login",
                            json={"email": "gussdub@gmail.com", "password": "testpass123"})
        assert login.status_code == 200, login.text
        h = {"Authorization": f"Bearer {login.json()['access_token']}"}
        r = client.post("/api/subscription/create-checkout",
                        json={"origin_url": "https://facturepro.ca"}, headers=h)
        assert r.status_code == 200, r.text

        assert captured["mode"] == "subscription", "doit être un abonnement, pas un paiement unique"
        price = captured["line_items"][0]["price_data"]
        assert price["recurring"] == {"interval": "month"}
        assert price["unit_amount"] == int(server_module.SUBSCRIPTION_PRICE_CAD * 100)
        # Les événements customer.subscription.* ne portent pas les métadonnées du checkout —
        # il faut donc les recopier sur l'abonnement lui-même.
        assert captured["subscription_data"]["metadata"]["organization_id"]
        assert captured.get("customer_email")
