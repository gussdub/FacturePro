# Correctif facturation : abonnement mensuel récurrent — plan d'implémentation

> **Pour les agents :** SOUS-SKILL REQUIS — utiliser `superpowers:subagent-driven-development`
> (recommandé) ou `superpowers:executing-plans` pour exécuter ce plan tâche par tâche. Les étapes
> utilisent des cases à cocher (`- [ ]`) pour le suivi.

**Objectif :** remplacer le paiement unique de 15 $ (qui donne un accès permanent) par un véritable
abonnement mensuel Stripe, avec un accès qui **expire de lui-même** et des webhooks qui apprennent
les résiliations.

**Architecture :** l'accès ne repose plus sur un booléen éternel mais sur une date
(`subscription_current_period_end` + 7 jours de grâce) alimentée par Stripe. Trois helpers purs et
testables isolément — lecture de la date de fin, cartographie des statuts, application à une
organisation — puis les endpoints qui les utilisent. La gestion par l'abonné (carte, factures,
résiliation) est déléguée au portail client Stripe hébergé.

**Pile :** FastAPI + pymongo (`backend/server.py`), `stripe` 15.3.0 (API `2026-06-24.dahlia`),
React CRA (`frontend/src/pages/SubscriptionPage.js`), pytest via `../.venv-test/bin/python`.

**Spec :** `docs/superpowers/specs/2026-09-14-abonnement-recurrent-design.md` — la lire avant de
commencer, en particulier le §3.1 (le champ `current_period_end` a déménagé) qui est la raison
d'être de la tâche 2.

---

## Structure des fichiers

| Fichier | Responsabilité | Nature |
|---|---|---|
| `backend/requirements.txt` | épingler `stripe` | modifié (l. 12) |
| `backend/server.py` | 3 helpers + garde + 2 endpoints + webhook | modifié (points d'ancrage ci-dessous) |
| `backend/tests/test_subscription_recurring.py` | toute la couverture de ce plan | **créé** |
| `frontend/src/pages/SubscriptionPage.js` | bouton « Gérer mon abonnement » | modifié (209 lignes) |
| `CLAUDE.md` | entrée de feature + marche à suivre Stripe | modifié |

**Points d'ancrage dans `backend/server.py`** (vérifiés le 2026-09-14) :

- l. 46 — `SUBSCRIPTION_PRICE_CAD = 15.00`
- l. 2278 — `def _check_subscription_active(org, user)` (16 lignes, jusqu'à l. 2293)
- l. 3906 — `EXEMPT_USERS = ["gussdub@gmail.com"]`
- l. 12999 — `@app.post("/api/subscription/create-checkout")`
- l. 13099 — `@app.post("/api/webhook/stripe")`

> ⚠️ `EXEMPT_USERS` (l. 3906) est défini **après** `_check_subscription_active` (l. 2278). C'est
> déjà le cas aujourd'hui et ça fonctionne, parce que la résolution du nom a lieu à l'appel et non
> à la définition. Ne pas « corriger » cet ordre : ce serait un déplacement inutile dans un fichier
> de 14 000 lignes.

**Contrainte de non-régression :** le webhook actuel écrit `subscription_status` **à la fois** sur
`db.organizations` et sur `db.users` (l. ~13150). Le test
`tests/test_organizations_integration.py:213` l'exige explicitement. **Conserver le miroir sur
`db.users`** dans toutes les tâches qui touchent au webhook.

**Commandes de référence :**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
../.venv-test/bin/python -m pytest tests/test_subscription_recurring.py -q -p no:cacheprovider
```

---

## Task 1 : Épingler `stripe` et ajouter la constante de grâce

**Files:**
- Modify: `backend/requirements.txt:12`
- Modify: `backend/server.py:46`

- [ ] **Step 1 : Constater l'état actuel**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
sed -n '12p' requirements.txt
../.venv-test/bin/pip show stripe | head -2
```

Attendu : `stripe` (sans version) puis `Version: 15.3.0`.

- [ ] **Step 2 : Épingler la dépendance**

Remplacer la ligne 12 de `backend/requirements.txt` :

```
stripe>=15.3,<16   # [Facturation] ÉPINGLÉ : ce code dépend de la version d'API Stripe. En
                   # 2026-06-24.dahlia, `current_period_end` vit sur SubscriptionItem et NON sur
                   # Subscription (cf. _subscription_period_end). Une montée majeure non
                   # intentionnelle pourrait redéplacer ce champ et casser la facturation EN
                   # SILENCE. Toute montée de version doit être accompagnée d'un test manuel en
                   # mode test Stripe.
```

- [ ] **Step 3 : Ajouter la constante de grâce**

Juste après la ligne 46 (`SUBSCRIPTION_PRICE_CAD = 15.00`) de `backend/server.py` :

```python
# [Facturation] Jours de grâce après la fin de période payée. Stripe retente ses webhooks pendant
# ~3 jours ; 7 jours couvrent donc largement une panne de livraison sans bloquer un bon payeur.
# L'accès expire TOUT SEUL après ce délai : c'est ce qui empêche un webhook manqué de redonner un
# accès éternel, qui était exactement le défaut d'origine.
_SUBSCRIPTION_GRACE_DAYS = 7
```

- [ ] **Step 4 : Vérifier que le module importe toujours**

```bash
../.venv-test/bin/python -c "import sys; sys.path.insert(0,'.'); import server; print(server._SUBSCRIPTION_GRACE_DAYS)"
```

Attendu : `7`

- [ ] **Step 5 : Commit**

```bash
git add backend/requirements.txt backend/server.py
git commit -m "build(stripe): épingler stripe >=15.3,<16 — la facturation dépend de la version d'API"
```

---

## Task 2 : Helper `_subscription_period_end` — lire la date au bon endroit

C'est la tâche la plus importante du plan. En API `2026-06-24.dahlia`, `current_period_end`
n'existe **plus** sur `Subscription` : il vit sur chaque `SubscriptionItem`. Lire
`sub["current_period_end"]` renverrait `None`, l'organisation serait `active` **sans date**, donc
**refusée par la garde juste après avoir payé**.

**Files:**
- Modify: `backend/server.py` (insérer après le bloc de la tâche 1, vers l. 50)
- Test: `backend/tests/test_subscription_recurring.py` (créer)

- [ ] **Step 1 : Écrire les tests qui échouent**

Créer `backend/tests/test_subscription_recurring.py` :

```python
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
        """RÉGRESSION §3.1 : un objet portant le champ à la RACINE (l'ancienne forme, celle que
        tous les tutoriels montrent) ne doit PAS produire de date. Si ce test passe au vert avec
        une implémentation qui lit la racine, c'est que le piège est revenu."""
        assert server_module._subscription_period_end(
            {"id": "sub_x", "current_period_end": 1789000000, "items": {"data": []}}) is None

    def test_aucun_item_renvoie_none(self):
        assert server_module._subscription_period_end(_sub([])) is None

    def test_objet_malforme_renvoie_none(self):
        for bad in ({}, {"items": None}, {"items": {"data": [{}]}}, {"items": {"data": [{"current_period_end": None}]}}):
            assert server_module._subscription_period_end(bad) is None
```

- [ ] **Step 2 : Lancer les tests pour les voir échouer**

```bash
../.venv-test/bin/python -m pytest tests/test_subscription_recurring.py -q -p no:cacheprovider
```

Attendu : ÉCHEC avec `AttributeError: module 'server' has no attribute '_subscription_period_end'`

- [ ] **Step 3 : Implémenter**

Insérer dans `backend/server.py`, juste après `_SUBSCRIPTION_GRACE_DAYS` :

```python
def _as_utc(dt: datetime) -> datetime:
    """Normalise en UTC un datetime éventuellement naïf (Mongo rend des naïfs)."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _subscription_period_end(sub: dict):
    """Fin de la période payée d'un abonnement Stripe, en ISO 8601 UTC, ou None.

    ⚠️ En API 2026-06-24.dahlia, `current_period_end` N'EST PLUS sur l'objet Subscription : il vit
    sur chaque SubscriptionItem. Vérifié dans la lib installée :
        grep current_period_end stripe/_subscription.py      -> aucun résultat
        grep current_period_end stripe/_subscription_item.py  -> current_period_end: int
    Lire `sub["current_period_end"]` renverrait None, l'org serait `active` SANS date, donc
    REFUSÉE par _check_subscription_active juste après avoir payé. Ne pas « simplifier » ceci.

    On prend le MAXIMUM des items (un abonnement peut en porter plusieurs) et on renvoie None
    plutôt qu'un 0 silencieux si rien n'est lisible — l'appelant décide quoi faire d'un None.
    """
    try:
        items = ((sub or {}).get("items") or {}).get("data") or []
        ends = [it.get("current_period_end") for it in items if isinstance(it, dict)]
        ends = [int(e) for e in ends if isinstance(e, (int, float))]
        if not ends:
            return None
        return datetime.fromtimestamp(max(ends), timezone.utc).isoformat()
    except Exception:
        return None
```

- [ ] **Step 4 : Lancer les tests pour les voir passer**

```bash
../.venv-test/bin/python -m pytest tests/test_subscription_recurring.py -q -p no:cacheprovider
```

Attendu : `5 passed`

- [ ] **Step 5 : Commit**

```bash
git add backend/server.py backend/tests/test_subscription_recurring.py
git commit -m "feat(facturation): _subscription_period_end lit current_period_end sur les ITEMS"
```

---

## Task 3 : Helper `_map_stripe_status` — les 8 statuts, sans trou

**Files:**
- Modify: `backend/server.py` (après `_subscription_period_end`)
- Test: `backend/tests/test_subscription_recurring.py`

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à `backend/tests/test_subscription_recurring.py` :

```python
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
```

- [ ] **Step 2 : Lancer les tests pour les voir échouer**

```bash
../.venv-test/bin/python -m pytest tests/test_subscription_recurring.py -q -p no:cacheprovider -k Status
```

Attendu : ÉCHEC `AttributeError: ... '_map_stripe_status'`

- [ ] **Step 3 : Implémenter**

```python
# [Facturation] Cartographie EXHAUSTIVE des 8 statuts d'abonnement Stripe vers les nôtres. Un
# statut non traité serait un trou silencieux, d'où le test paramétré qui couvre les 8.
#   active / past_due / canceled -> l'accès est accordé jusqu'à la fin de la période PAYÉE + grâce
#   suspended                    -> aucun accès, quelle que soit la date
# `incomplete_expired` est volontairement mappé sur `suspended` et NON sur `canceled` : aucune
# période n'a jamais été payée, il n'y a donc aucun accès à préserver.
_STRIPE_STATUS_MAP = {
    "active": "active",
    "trialing": "active",
    "past_due": "past_due",
    "canceled": "canceled",
    "incomplete": "suspended",
    "incomplete_expired": "suspended",
    "unpaid": "suspended",
    "paused": "suspended",
}
# Statuts après lesquels l'abonnement est MORT : on horodate `terminated_at`, dont la purge de
# rétention (Loi 25) a besoin pour dater la fermeture.
_STRIPE_TERMINAL = {"canceled", "incomplete_expired"}


def _map_stripe_status(stripe_status) -> str:
    """Statut Stripe -> statut interne. Tout ce qui n'est pas explicitement connu est `suspended`
    (fail-closed) : une valeur future de Stripe ne doit pas ouvrir l'accès par défaut."""
    return _STRIPE_STATUS_MAP.get(stripe_status, "suspended")
```

- [ ] **Step 4 : Lancer les tests pour les voir passer**

```bash
../.venv-test/bin/python -m pytest tests/test_subscription_recurring.py -q -p no:cacheprovider
```

Attendu : `15 passed`

- [ ] **Step 5 : Commit**

```bash
git add backend/server.py backend/tests/test_subscription_recurring.py
git commit -m "feat(facturation): cartographie exhaustive des 8 statuts Stripe, fail-closed"
```

---

## Task 4 : La garde d'accès — l'invariant central

**Files:**
- Modify: `backend/server.py:2278-2293` (remplacer `_check_subscription_active`)
- Test: `backend/tests/test_subscription_recurring.py`

- [ ] **Step 1 : Écrire les tests qui échouent**

```python
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
        """INVARIANT §4.3 point 5. Un statut qui ouvre l'accès DOIT porter une date, sinon le bug
        d'accès éternel revient par la porte arrière."""
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
```

- [ ] **Step 2 : Lancer les tests pour les voir échouer**

```bash
../.venv-test/bin/python -m pytest tests/test_subscription_recurring.py -q -p no:cacheprovider -k AccessGate
```

Attendu : plusieurs ÉCHECS — notamment `test_active_sans_date_est_refuse` qui renvoie `None` au
lieu de `402` (c'est précisément le défaut à corriger).

- [ ] **Step 3 : Remplacer la garde**

Remplacer intégralement `backend/server.py:2278-2293` par :

```python
def _check_subscription_active(org: dict, user: dict):
    """Vérifie l'état d'abonnement au niveau org. Lève HTTPException(402) si l'accès a expiré.

    INVARIANT CENTRAL : tout statut qui ACCORDE l'accès doit porter une date de fin. Avant ce
    correctif, `subscription_status="active"` était un booléen ÉTERNEL : un paiement unique
    donnait un accès permanent, et une résiliation Stripe n'était jamais apprise. Ancrer l'accès
    sur une date qui expire d'elle-même est ce qui ferme cette classe de défaut — un webhook
    manqué ne peut plus produire un accès infini.
    """
    if user.get("email") in EXEMPT_USERS:
        return  # en PREMIER et sans condition : ne jamais se verrouiller hors de son produit
    sub_status = org.get("subscription_status", "trial")
    now = datetime.now(timezone.utc)

    if sub_status == "trial":
        trial_end = org.get("trial_ends_at")
        if not trial_end:
            return  # essai sans date : comportement historique conservé
        try:
            if now <= _as_utc(datetime.fromisoformat(trial_end)):
                return
        except Exception:
            return  # date illisible : ne pas bloquer sur la foi d'une donnée corrompue
        raise HTTPException(402, "Subscription expired — please renew")

    if sub_status in ("active", "past_due", "canceled"):
        # past_due : Stripe retente le prélèvement, l'abonné n'est pas fautif.
        # canceled : la période en cours est PAYÉE (CGU art. 10), l'accès court jusqu'au bout.
        end = org.get("subscription_current_period_end")
        if not end:
            raise HTTPException(402, "Subscription expired — please renew")
        try:
            end_dt = _as_utc(datetime.fromisoformat(end))
        except Exception:
            raise HTTPException(402, "Subscription expired — please renew")
        if now <= end_dt + timedelta(days=_SUBSCRIPTION_GRACE_DAYS):
            return
        raise HTTPException(402, "Subscription expired — please renew")

    # `suspended` et tout statut inconnu -> fail-closed.
    raise HTTPException(402, "Subscription expired — please renew")
```

- [ ] **Step 4 : Lancer les tests pour les voir passer, puis vérifier la non-régression**

```bash
../.venv-test/bin/python -m pytest tests/test_subscription_recurring.py -q -p no:cacheprovider
../.venv-test/bin/python -m pytest tests/test_organizations_integration.py tests/test_stripe_subscription.py -q -p no:cacheprovider 2>&1 | tail -5
```

Attendu : `26 passed` sur le nouveau fichier. Sur les deux autres, **la même liste d'échecs
qu'avant le changement** — comparer avec la baseline obtenue par
`git stash push -- backend/server.py`, relance, `git stash pop`.

- [ ] **Step 5 : Commit**

```bash
git add backend/server.py backend/tests/test_subscription_recurring.py
git commit -m "fix(facturation): l'accès expire par une DATE, plus par un booléen éternel"
```

---

## Task 5 : Checkout en `mode="subscription"`

**Files:**
- Modify: `backend/server.py:12999` (corps de `create_subscription_checkout`)
- Test: `backend/tests/test_subscription_recurring.py`

- [ ] **Step 1 : Écrire le test qui échoue**

```python
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
        # §3.3 : les événements customer.subscription.* ne portent pas les métadonnées du
        # checkout — il faut donc les recopier sur l'abonnement.
        assert captured["subscription_data"]["metadata"]["organization_id"]
        assert captured.get("customer_email")
```

- [ ] **Step 2 : Lancer le test pour le voir échouer**

```bash
../.venv-test/bin/python -m pytest tests/test_subscription_recurring.py -q -p no:cacheprovider -k Checkout
```

Attendu : ÉCHEC `AssertionError: doit être un abonnement, pas un paiement unique`
(`captured["mode"] == "payment"`).

- [ ] **Step 3 : Modifier l'appel Stripe**

Dans `create_subscription_checkout`, remplacer le bloc `stripe.checkout.Session.create(...)` par :

```python
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "cad",
                "unit_amount": int(SUBSCRIPTION_PRICE_CAD * 100),
                # [Facturation] `recurring` est ce qui fait de ce prix un ABONNEMENT. Prix défini
                # en ligne plutôt que via un objet Price du tableau de bord : pas d'étape manuelle,
                # pas de dérive de configuration entre les modes test et production.
                "recurring": {"interval": "month"},
                "product_data": {"name": "Abonnement FacturePro"},
            },
            "quantity": 1,
        }],
        mode="subscription",
        customer_email=current_user.email,
        success_url=success_url,
        cancel_url=cancel_url,
        # [Facturation §3.3] Les événements customer.subscription.* ne transportent PAS les
        # métadonnées de la session de checkout : ils portent celles de l'ABONNEMENT. On les
        # recopie donc ici. Filet seulement — le routage principal se fait par
        # stripe_subscription_id / stripe_customer_id stockés en base.
        subscription_data={"metadata": {
            "user_id": current_user.id,
            "organization_id": current_user.organization_id,
        }},
        metadata={
            "user_id": current_user.id,
            "organization_id": current_user.organization_id,
            "email": current_user.email,
            "plan": "facturepro_monthly",
        },
    )
```

- [ ] **Step 4 : Lancer les tests pour les voir passer**

```bash
../.venv-test/bin/python -m pytest tests/test_subscription_recurring.py -q -p no:cacheprovider
```

Attendu : `27 passed`

- [ ] **Step 5 : Commit**

```bash
git add backend/server.py backend/tests/test_subscription_recurring.py
git commit -m "feat(facturation): checkout en mode=subscription, prix récurrent mensuel"
```

---

## Task 6 : Webhooks — apprendre les changements d'abonnement

**Files:**
- Modify: `backend/server.py` (helper avant l. 13099, puis corps de `stripe_webhook`)
- Test: `backend/tests/test_subscription_recurring.py`

- [ ] **Step 1 : Écrire les tests qui échouent**

```python
class TestSubscriptionWebhooks:
    @pytest.fixture
    def org(self):
        oid = str(uuid.uuid4())
        server_module.db.organizations.insert_one({
            "id": oid, "name": "Test WH", "subscription_status": "trial",
            "stripe_customer_id": "cus_wh_test",
        })
        yield oid
        server_module.db.organizations.delete_one({"id": oid})

    @pytest.fixture
    def wh(self, monkeypatch):
        """Monkeypatche construct_event, comme test_organizations_integration.py:213."""
        monkeypatch.setattr(server_module, "STRIPE_API_KEY", "sk_test_dummy")
        monkeypatch.setattr(server_module, "STRIPE_WEBHOOK_SECRET", "whsec_test_dummy")
        client = TestClient(server_module.app)

        def post(payload):
            monkeypatch.setattr(server_module.stripe.Webhook, "construct_event",
                                staticmethod(lambda body, sig, secret: payload))
            return client.post("/api/webhook/stripe", json={})
        return post

    def test_updated_applique_statut_et_date(self, org, wh):
        ts = int((datetime.now(timezone.utc) + timedelta(days=20)).timestamp())
        r = wh({"type": "customer.subscription.updated",
                "data": {"object": _sub([ts], status="past_due", sub_id="sub_a",
                                        customer="cus_wh_test")}})
        assert r.status_code == 200, r.text
        o = server_module.db.organizations.find_one({"id": org})
        assert o["subscription_status"] == "past_due"
        assert o["subscription_current_period_end"].startswith(
            datetime.fromtimestamp(ts, timezone.utc).isoformat()[:10])
        assert o["stripe_subscription_id"] == "sub_a"

    def test_deleted_pose_canceled_et_terminated_at(self, org, wh):
        ts = int((datetime.now(timezone.utc) + timedelta(days=5)).timestamp())
        r = wh({"type": "customer.subscription.deleted",
                "data": {"object": _sub([ts], status="canceled", customer="cus_wh_test")}})
        assert r.status_code == 200
        o = server_module.db.organizations.find_one({"id": org})
        assert o["subscription_status"] == "canceled"
        assert o.get("terminated_at")

    def test_deleted_rejoue_ne_bouge_pas_terminated_at(self, org, wh):
        """Stripe rejoue ses événements. Repousser terminated_at repousserait la purge Loi 25."""
        ts = int((datetime.now(timezone.utc) + timedelta(days=5)).timestamp())
        ev = {"type": "customer.subscription.deleted",
              "data": {"object": _sub([ts], status="canceled", customer="cus_wh_test")}}
        wh(ev)
        premier = server_module.db.organizations.find_one({"id": org})["terminated_at"]
        wh(ev)
        assert server_module.db.organizations.find_one({"id": org})["terminated_at"] == premier

    def test_client_inconnu_renvoie_200_sans_ecrire(self, wh):
        """Un 500 ferait retenter Stripe indéfiniment."""
        r = wh({"type": "customer.subscription.updated",
                "data": {"object": _sub([1789000000], customer="cus_inexistant")}})
        assert r.status_code == 200

    def test_type_inconnu_renvoie_200(self, wh):
        r = wh({"type": "invoice.will_be_due", "data": {"object": {}}})
        assert r.status_code == 200
```

- [ ] **Step 2 : Lancer les tests pour les voir échouer**

```bash
../.venv-test/bin/python -m pytest tests/test_subscription_recurring.py -q -p no:cacheprovider -k Webhooks
```

Attendu : ÉCHEC — l'org reste `trial`, `customer.subscription.updated` n'étant pas traité.

- [ ] **Step 3 : Implémenter le helper, puis brancher les deux événements**

Insérer **avant** `@app.post("/api/webhook/stripe")` (l. 13099) :

```python
def _apply_stripe_subscription(sub: dict) -> bool:
    """Applique un objet d'abonnement Stripe à l'organisation correspondante. Renvoie True si une
    organisation a été trouvée et mise à jour.

    Routage par `stripe_subscription_id` puis `stripe_customer_id` (stockés en base), puis en
    dernier recours par `metadata.organization_id` — parce que les événements
    customer.subscription.* ne portent PAS les métadonnées de la session de checkout (§3.3).
    """
    sub_id = sub.get("id")
    customer_id = sub.get("customer")
    meta_org = (sub.get("metadata") or {}).get("organization_id")
    org = None
    for flt in ({"stripe_subscription_id": sub_id} if sub_id else None,
                {"stripe_customer_id": customer_id} if customer_id else None,
                {"id": meta_org} if meta_org else None):
        if flt:
            org = db.organizations.find_one(flt, {"_id": 0, "id": 1, "terminated_at": 1})
            if org:
                break
    if not org:
        # Pas de 500 : Stripe retenterait indéfiniment un événement qu'on ne saura jamais router.
        print(f"[stripe] abonnement sans organisation connue sub={sub_id} cust={customer_id}")
        return False

    our_status = _map_stripe_status(sub.get("status"))
    upd = {"subscription_status": our_status}
    if sub_id:
        upd["stripe_subscription_id"] = sub_id
    if customer_id:
        upd["stripe_customer_id"] = customer_id
    period_end = _subscription_period_end(sub)
    if period_end:
        # Écrit sans condition : la valeur la plus récemment reçue de Stripe fait autorité, les
        # webhooks pouvant arriver dans le désordre.
        upd["subscription_current_period_end"] = period_end

    set_on_first = {}
    if sub.get("status") in _STRIPE_TERMINAL and not org.get("terminated_at"):
        # MONOTONE : uniquement à la première écriture. Un événement rejoué ne doit pas repousser
        # la date, sinon il repousse d'autant la purge de rétention (Loi 25).
        set_on_first["terminated_at"] = datetime.now(timezone.utc).isoformat()

    db.organizations.update_one({"id": org["id"]}, {"$set": {**upd, **set_on_first}})
    # Miroir sur db.users : exigé par tests/test_organizations_integration.py:213.
    # update_MANY et non update_one : le filtre porte sur l'organisation, qui peut compter
    # plusieurs membres — un update_one n'en toucherait qu'un seul, arbitrairement, et les autres
    # garderaient un statut miroir périmé.
    db.users.update_many({"organization_id": org["id"]},
                         {"$set": {"subscription_status": our_status}})
    return True
```

Puis, dans `stripe_webhook`, après le bloc `if event["type"] == "checkout.session.completed":`,
ajouter :

```python
            elif event["type"] in ("customer.subscription.updated",
                                   "customer.subscription.deleted"):
                _apply_stripe_subscription(event["data"]["object"] or {})
```

Et dans le handler `checkout.session.completed`, remplacer l'affectation en dur
`"subscription_status": "active"` par une lecture de l'abonnement réel :

```python
                    # [Facturation] En mode abonnement, la session porte l'id de l'abonnement. On
                    # le récupère pour obtenir le statut ET la date de fin de période — sans
                    # laquelle la garde refuserait l'accès (invariant de _check_subscription_active).
                    sub_id = session_data.get("subscription")
                    sub_obj = None
                    if sub_id:
                        try:
                            sub_obj = stripe.Subscription.retrieve(sub_id)
                        except Exception as e:
                            print(f"[stripe] retrieve abonnement impossible type={type(e).__name__}")
                    if sub_obj is not None:
                        org_update["subscription_status"] = _map_stripe_status(sub_obj.get("status"))
                        org_update["stripe_subscription_id"] = sub_id
                        pe = _subscription_period_end(sub_obj)
                        if pe:
                            org_update["subscription_current_period_end"] = pe
```

- [ ] **Step 4 : Lancer les tests pour les voir passer**

```bash
../.venv-test/bin/python -m pytest tests/test_subscription_recurring.py -q -p no:cacheprovider
../.venv-test/bin/python -m pytest tests/test_organizations_integration.py -q -p no:cacheprovider -k webhook
```

Attendu : `32 passed` sur le nouveau fichier ; le test de miroir existant reste vert.

- [ ] **Step 5 : Commit**

```bash
git add backend/server.py backend/tests/test_subscription_recurring.py
git commit -m "feat(facturation): webhooks subscription.updated/deleted + terminated_at monotone"
```

---

## Task 7 : Portail client Stripe

**Files:**
- Modify: `backend/server.py` (nouvel endpoint après `create_subscription_checkout`)
- Test: `backend/tests/test_subscription_recurring.py`

- [ ] **Step 1 : Écrire les tests qui échouent**

```python
class TestBillingPortal:
    def _client_headers(self):
        c = TestClient(server_module.app)
        r = c.post("/api/auth/login",
                   json={"email": "gussdub@gmail.com", "password": "testpass123"})
        assert r.status_code == 200, r.text
        return c, {"Authorization": f"Bearer {r.json()['access_token']}"}

    def test_sans_client_stripe_renvoie_409(self, monkeypatch):
        monkeypatch.setattr(server_module, "STRIPE_API_KEY", "sk_test_dummy")
        c, h = self._client_headers()
        org = server_module.db.organizations.find_one({"subscription_status": {"$exists": True}},
                                                     {"_id": 0, "id": 1})
        server_module.db.organizations.update_one({"id": org["id"]},
                                                  {"$unset": {"stripe_customer_id": ""}})
        r = c.post("/api/subscription/portal",
                   json={"return_url": "https://facturepro.ca/subscription"}, headers=h)
        assert r.status_code == 409, r.text

    def test_renvoie_l_url_du_portail(self, monkeypatch):
        monkeypatch.setattr(server_module, "STRIPE_API_KEY", "sk_test_dummy")
        captured = {}

        def fake_create(**kw):
            captured.update(kw)
            return {"url": "https://billing.stripe.test/session"}

        monkeypatch.setattr(server_module.stripe.billing_portal.Session, "create", fake_create)
        c, h = self._client_headers()
        me = c.get("/api/auth/me", headers=h).json()
        server_module.db.organizations.update_one(
            {"id": me["organization_id"]}, {"$set": {"stripe_customer_id": "cus_portal"}})
        try:
            r = c.post("/api/subscription/portal",
                       json={"return_url": "https://facturepro.ca/subscription"}, headers=h)
            assert r.status_code == 200, r.text
            assert r.json()["url"] == "https://billing.stripe.test/session"
            assert captured["customer"] == "cus_portal"
        finally:
            server_module.db.organizations.update_one(
                {"id": me["organization_id"]}, {"$unset": {"stripe_customer_id": ""}})
```

- [ ] **Step 2 : Lancer les tests pour les voir échouer**

```bash
../.venv-test/bin/python -m pytest tests/test_subscription_recurring.py -q -p no:cacheprovider -k Portal
```

Attendu : ÉCHEC `404` — l'endpoint n'existe pas.

- [ ] **Step 3 : Implémenter l'endpoint**

Après `create_subscription_checkout` :

```python
@app.post("/api/subscription/portal")
def create_billing_portal_session(
    body: dict,
    current_user: CurrentUser = Depends(require_permission("billing:manage")),
):
    """Ouvre le portail client Stripe hébergé : l'abonné y change sa carte, télécharge ses
    factures et résilie lui-même. C'est Stripe qui nous renvoie l'état par webhook."""
    if not STRIPE_API_KEY:
        raise HTTPException(500, "Stripe non configure")
    return_url = (body.get("return_url") or "").strip()
    if not return_url:
        raise HTTPException(400, "return_url requis")
    org = db.organizations.find_one({"id": current_user.organization_id},
                                   {"_id": 0, "stripe_customer_id": 1})
    customer_id = (org or {}).get("stripe_customer_id")
    if not customer_id:
        # 409 explicite : l'organisation n'a jamais souscrit, il n'y a pas de client Stripe.
        raise HTTPException(409, "Aucun abonnement Stripe pour cette organisation")
    try:
        session = stripe.billing_portal.Session.create(customer=customer_id,
                                                       return_url=return_url)
    except Exception as e:
        print(f"[stripe] portail impossible type={type(e).__name__}")  # jamais str(e) : fuite de clé
        raise HTTPException(502, "Portail de facturation indisponible")
    url = session["url"] if isinstance(session, dict) else session.url
    return {"url": url}
```

- [ ] **Step 4 : Lancer les tests pour les voir passer**

```bash
../.venv-test/bin/python -m pytest tests/test_subscription_recurring.py -q -p no:cacheprovider
```

Attendu : `34 passed`

- [ ] **Step 5 : Commit**

```bash
git add backend/server.py backend/tests/test_subscription_recurring.py
git commit -m "feat(facturation): endpoint du portail client Stripe"
```

---

## Task 8 : Bouton « Gérer mon abonnement »

**Files:**
- Modify: `frontend/src/pages/SubscriptionPage.js` (handler près de `handleCheckout`, l. 60 ; bouton dans le rendu)

- [ ] **Step 1 : Ajouter l'état et le handler**

Après `const [checkoutLoading, setCheckoutLoading] = useState(false);` (l. 11) :

```javascript
  const [portalLoading, setPortalLoading] = useState(false);
```

Après la fonction `handleCheckout` (vers l. 74) :

```javascript
  // Portail client Stripe : changement de carte, factures et résiliation en libre-service.
  // On n'affiche le bouton que si l'organisation a déjà un client Stripe (sinon l'API renvoie 409).
  const handlePortal = async () => {
    setPortalLoading(true);
    try {
      const res = await axios.post(`${BACKEND_URL}/api/subscription/portal`, {
        return_url: `${window.location.origin}/subscription`,
      });
      window.location.href = res.data.url;
    } catch (e) {
      alert(e.response?.status === 409
        ? "Aucun abonnement actif à gérer pour le moment."
        : "Impossible d'ouvrir le portail de facturation. Réessaie dans un moment.");
      setPortalLoading(false);
    }
  };
```

- [ ] **Step 2 : Ajouter le bouton au rendu**

Dans le bloc affiché quand `isActive` est vrai, ajouter :

```javascript
            <button onClick={handlePortal} disabled={portalLoading}
                    style={{ background: '#00796B', color: '#fff', border: 'none',
                             padding: '12px 24px', borderRadius: 8, fontWeight: 600,
                             cursor: portalLoading ? 'wait' : 'pointer', marginTop: 12 }}>
              {portalLoading ? 'Ouverture…' : 'Gérer mon abonnement'}
            </button>
```

> `#00796B` et non `#00A08C` : blanc sur `#00A08C` ne fait que 3,28:1, insuffisant pour un libellé
> de bouton (seuil WCAG 4,5:1). Même raison que pour les boutons des courriels de marque.

- [ ] **Step 3 : Vérifier le build CI**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
CI=true npx react-scripts build 2>&1 | grep -E "Compiled|Failed|error"
```

Attendu : `Compiled successfully.`
(`CI=true` transforme les avertissements ESLint en erreurs — c'est ce qui casse Vercel sinon.)

- [ ] **Step 4 : Commit**

```bash
git add frontend/src/pages/SubscriptionPage.js
git commit -m "feat(facturation): bouton Gérer mon abonnement vers le portail Stripe"
```

---

## Task 9 : Vérification par mutation, non-régression, documentation

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1 : Vérification par mutation**

Chaque mutation doit faire **échouer au moins un test**. Si une mutation survit, le test
correspondant est décoratif et doit être renforcé.

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
cp server.py /tmp/s.bak
run() { ../.venv-test/bin/python -m pytest tests/test_subscription_recurring.py -q -p no:cacheprovider 2>&1 | tail -1; }

# M1 — lire current_period_end à la RACINE (le piège §3.1)
python3 - <<'EOF'
s=open('server.py',encoding='utf-8').read()
a='        items = ((sub or {}).get("items") or {}).get("data") or []'
b='        items = [sub] if (sub or {}).get("current_period_end") else (((sub or {}).get("items") or {}).get("data") or [])'
assert s.count(a)==1; open('server.py','w',encoding='utf-8').write(s.replace(a,b))
EOF
echo -n "M1 racine            : "; run; cp /tmp/s.bak server.py

# M2 — supprimer l'invariant « active sans date est refusé »
python3 - <<'EOF'
s=open('server.py',encoding='utf-8').read()
a='''        end = org.get("subscription_current_period_end")
        if not end:
            raise HTTPException(402, "Subscription expired — please renew")'''
b='''        end = org.get("subscription_current_period_end")
        if not end:
            return'''
assert s.count(a)==1; open('server.py','w',encoding='utf-8').write(s.replace(a,b))
EOF
echo -n "M2 invariant retire   : "; run; cp /tmp/s.bak server.py

# M3 — supprimer la grâce
python3 - <<'EOF'
s=open('server.py',encoding='utf-8').read()
a='_SUBSCRIPTION_GRACE_DAYS = 7'
b='_SUBSCRIPTION_GRACE_DAYS = 0'
assert s.count(a)==1; open('server.py','w',encoding='utf-8').write(s.replace(a,b))
EOF
echo -n "M3 grace a zero       : "; run; cp /tmp/s.bak server.py

# M4 — rendre terminated_at non monotone
python3 - <<'EOF'
s=open('server.py',encoding='utf-8').read()
a='if sub.get("status") in _STRIPE_TERMINAL and not org.get("terminated_at"):'
b='if sub.get("status") in _STRIPE_TERMINAL:'
assert s.count(a)==1; open('server.py','w',encoding='utf-8').write(s.replace(a,b))
EOF
echo -n "M4 terminated_at libre: "; run; cp /tmp/s.bak server.py

# M5 — statut inconnu ouvre l'accès
python3 - <<'EOF'
s=open('server.py',encoding='utf-8').read()
a='    return _STRIPE_STATUS_MAP.get(stripe_status, "suspended")'
b='    return _STRIPE_STATUS_MAP.get(stripe_status, "active")'
assert s.count(a)==1; open('server.py','w',encoding='utf-8').write(s.replace(a,b))
EOF
echo -n "M5 inconnu -> actif   : "; run; cp /tmp/s.bak server.py

echo -n "RESTAURE (34 passed)  : "; run; rm -f /tmp/s.bak
```

- [ ] **Step 2 : Non-régression sur la suite complète, par comparaison de listes**

Comparer les **listes** d'échecs, pas les compteurs : il existe ~190 échecs live-HTTP préexistants
qui exigent un serveur en écoute.

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
../.venv-test/bin/python -m pytest backend/tests -q -p no:cacheprovider 2>&1 | grep -E "^(FAILED|ERROR)" | sort > /tmp/apres.txt
git stash push -- backend/server.py backend/requirements.txt
(cd backend && ../.venv-test/bin/python -m pytest tests -q -p no:cacheprovider 2>&1 | grep -E "^(FAILED|ERROR)" | sort > /tmp/avant.txt)
git stash pop
diff /tmp/avant.txt /tmp/apres.txt && echo "IDENTIQUE -> 0 régression"
```

Attendu : `IDENTIQUE -> 0 régression`

- [ ] **Step 3 : Documenter dans CLAUDE.md**

Ajouter une entrée en tête de « Features livrées » couvrant : le passage en `mode="subscription"`,
l'invariant de la garde, le piège `current_period_end` sur les items, l'épinglage de `stripe`, la
cartographie des 8 statuts, `terminated_at` (et le fait qu'il **débloque la purge de rétention**),
et la **marche à suivre Stripe** du Step 4 ci-dessous.

Retirer aussi de l'entrée du 2026-09-14 (« Politique de confidentialité et CGU ») le point 1 du
suivi code, désormais livré.

- [ ] **Step 4 : Écrire la marche à suivre Stripe dans CLAUDE.md**

```markdown
⚠️ **À FAIRE DANS LE TABLEAU DE BORD STRIPE** — sans ces trois lignes, l'abonnement paraîtra
fonctionner mais ne se résiliera JAMAIS, en silence :
1. Webhooks → l'endpoint `https://facturepro-backend-dkvn.onrender.com/api/webhook/stripe` doit
   être abonné à **`checkout.session.completed`**, **`customer.subscription.updated`** et
   **`customer.subscription.deleted`**. C'est l'oubli le plus facile et le plus silencieux.
2. Billing → Customer portal : activer le portail et y autoriser l'annulation d'abonnement et la
   mise à jour du moyen de paiement.
3. Test de bout en bout en **mode test** : souscrire avec `4242 4242 4242 4242`, vérifier que
   `subscription_current_period_end` est bien posé en base, puis résilier depuis le portail et
   vérifier que `subscription_status` passe à `canceled` et que `terminated_at` est daté.
```

- [ ] **Step 5 : Commit**

```bash
git add CLAUDE.md
git commit -m "docs(facturation): entrée CLAUDE.md + marche à suivre Stripe"
```

---

## Couverture de la spec

| Exigence de la spec | Tâche |
|---|---|
| §3.1 `current_period_end` sur les items | 2 (+ mutation M1 en 9) |
| §3.2 épinglage de `stripe` | 1 |
| §3.3 métadonnées sur l'abonnement | 5 |
| §3.4 `billing_portal` | 7 |
| §4.1 checkout `mode="subscription"` | 5 |
| §4.2 champs persistés | 6 |
| §4.3 garde + invariant « pas de date, pas d'accès » | 4 (+ M2, M3) |
| §4.4 cartographie des 8 statuts | 3 (+ M5) |
| §4.5 webhooks + `terminated_at` monotone | 6 (+ M4) |
| §4.6 portail client | 7 et 8 |
| §5 gestion d'erreur (200 sur inconnu, pas de `str(e)`) | 6 et 7 |
| §6 tests + vérification par mutation | 2 à 7, puis 9 |
| §8 marche à suivre Stripe hors dépôt | 9 |

**Non couvert, et c'est voulu (§7) :** la purge de rétention Loi 25 — commit séparé, que
`terminated_at` rend enfin possible.
