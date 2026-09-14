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
