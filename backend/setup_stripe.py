#!/usr/bin/env python3
"""Configure Stripe pour FacturePro — les trois actions du correctif facturation.

    1. Abonner l'endpoint webhook aux TROIS événements nécessaires.
    2. Activer le portail client avec annulation et mise à jour du moyen de paiement.
    3. Vérifier, en mode test seulement, que le code lit correctement un VRAI objet Stripe.

Sans ces réglages, l'abonnement paraît fonctionner mais ne se résilie JAMAIS, en silence :
FacturePro n'apprend une résiliation que par `customer.subscription.deleted`.

USAGE
-----
    # Mode test — sans risque, à faire en premier
    STRIPE_API_KEY=sk_test_51... python3 setup_stripe.py

    # Production — après avoir validé en test
    STRIPE_API_KEY=sk_live_51... python3 setup_stripe.py

Le script est IDEMPOTENT : relancé, il ne crée pas de doublon.

⚠️ Le secret de signature d'un endpoint webhook n'est renvoyé par Stripe qu'à la CRÉATION.
Si l'endpoint existe déjà, le script ne peut pas te le redonner — récupère-le dans le
tableau de bord Stripe, ou supprime l'endpoint pour que le script le recrée.
"""
import os
import sys

try:
    import stripe
except ImportError:
    sys.exit("stripe absent. Lance : pip install -r requirements.txt")

URL_WEBHOOK = "https://facturepro-backend-dkvn.onrender.com/api/webhook/stripe"

# Les trois, et pas moins. `checkout.session.completed` active l'abonnement ;
# `updated` apprend les changements de statut et rafraîchit la date de fin de période ;
# `deleted` apprend la résiliation. Sans le troisième, un abonné résilié garde l'accès.
EVENEMENTS = [
    "checkout.session.completed",
    "customer.subscription.updated",
    "customer.subscription.deleted",
]


def fatal(msg):
    sys.exit(f"\n❌ {msg}")


def cle_et_mode():
    cle = (os.environ.get("STRIPE_API_KEY") or "").strip()
    if not cle:
        fatal("STRIPE_API_KEY absente.\n"
              "   Récupère-la dans Stripe → Developers → API keys.")
    if len(cle) < 40:
        fatal(f"STRIPE_API_KEY invalide ({len(cle)} caractères).\n"
              "   Une vraie clé fait ~107 caractères et commence par sk_test_51 ou sk_live_51.\n"
              "   La valeur de backend/.env est un placeholder laissé par la migration Emergent.")
    if cle.startswith("sk_live_"):
        return cle, "LIVE"
    if cle.startswith("sk_test_"):
        return cle, "TEST"
    fatal("STRIPE_API_KEY ne commence ni par sk_test_ ni par sk_live_.")


def confirmer_live():
    print("\n⚠️  MODE LIVE — ces changements touchent ta facturation RÉELLE.")
    print("   Le portail client deviendra accessible à tes abonnés, et Stripe")
    print("   commencera à livrer des webhooks vers la production.")
    if input("   Taper « oui » pour continuer : ").strip().lower() != "oui":
        sys.exit("   Annulé.")


def action_1_webhook():
    print("\n[1/3] Endpoint webhook")
    existants = [e for e in stripe.WebhookEndpoint.list(limit=100).data
                 if e.url == URL_WEBHOOK]

    if not existants:
        ep = stripe.WebhookEndpoint.create(
            url=URL_WEBHOOK, enabled_events=EVENEMENTS,
            description="FacturePro — abonnement mensuel")
        print(f"   ✅ Créé : {ep.id}")
        print("\n   ┌─────────────────────────────────────────────────────────────────┐")
        print("   │  SECRET DE SIGNATURE — affiché UNE SEULE FOIS par Stripe        │")
        print("   └─────────────────────────────────────────────────────────────────┘")
        print(f"\n   {ep.secret}\n")
        print("   Pose-le sur Render comme STRIPE_WEBHOOK_SECRET, puis redéploie.")
        print("   ⚠️  Sans ce secret, le webhook est refusé : le code est fail-closed,")
        print("      donc AUCUN abonnement ne s'activera.")
        return

    ep = existants[0]
    manquants = [e for e in EVENEMENTS if e not in ep.enabled_events]
    if manquants:
        stripe.WebhookEndpoint.modify(ep.id, enabled_events=EVENEMENTS)
        print(f"   ✅ Mis à jour : {ep.id}")
        print(f"      Événements ajoutés : {', '.join(manquants)}")
    else:
        print(f"   ✅ Déjà conforme : {ep.id}")
    if ep.status != "enabled":
        print(f"   ⚠️  Statut « {ep.status} » — réactive-le dans le tableau de bord.")
    print("   ℹ️  Le secret n'est plus récupérable par l'API. S'il te manque,")
    print("      prends-le dans le tableau de bord ou supprime l'endpoint pour le recréer.")


def action_2_portail():
    print("\n[2/3] Portail client")
    voulu = {
        "customer_update": {"enabled": True, "allowed_updates": ["email", "address"]},
        "invoice_history": {"enabled": True},
        "payment_method_update": {"enabled": True},
        "subscription_cancel": {"enabled": True, "mode": "at_period_end"},
    }
    cfgs = [c for c in stripe.billing_portal.Configuration.list(limit=100).data
            if c.is_default]
    if cfgs:
        cfg = stripe.billing_portal.Configuration.modify(
            cfgs[0].id, features=voulu, active=True)
        print(f"   ✅ Mise à jour : {cfg.id}")
    else:
        cfg = stripe.billing_portal.Configuration.create(
            features=voulu,
            business_profile={"headline": "FacturePro — gestion de ton abonnement"})
        print(f"   ✅ Créée : {cfg.id}")
    f = cfg.features
    print(f"      annulation (fin de période) : {f.subscription_cancel.enabled}")
    print(f"      moyen de paiement           : {f.payment_method_update.enabled}")
    print(f"      historique de factures      : {f.invoice_history.enabled}")
    print("   ℹ️  L'annulation est « à la fin de la période », conforme à l'art. 10 des CGU :")
    print("      « la résiliation prend effet à la fin de la période mensuelle en cours ».")


def action_3_verifier(mode):
    print("\n[3/3] Vérification du code contre un VRAI objet Stripe")
    if mode == "LIVE":
        print("   ⏭️  Sauté en mode LIVE — cette vérification crée un abonnement.")
        print("      Relance le script avec une clé sk_test_ pour l'exécuter.")
        return

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import server
    except Exception as e:
        print(f"   ⚠️  server.py non importable ({type(e).__name__}) — vérification sautée.")
        return

    cust = stripe.Customer.create(
        email="verification-setup@facturepro.test",
        description="Vérification setup_stripe.py — supprimable")
    try:
        sub = stripe.Subscription.create(
            customer=cust.id,
            items=[{"price_data": {
                "currency": "cad", "unit_amount": 1500,
                "recurring": {"interval": "month"},
                "product_data": {"name": "Vérification FacturePro"}}}],
            payment_behavior="default_incomplete",
            expand=["latest_invoice"])

        # LE piège : en API 2026-06-24.dahlia, `current_period_end` n'est plus sur
        # Subscription mais sur SubscriptionItem, et StripeObject n'a plus de .get().
        # Lire l'objet BRUT renvoie None -> org `active` SANS date -> accès refusé
        # juste après avoir payé.
        brut = server._subscription_period_end(sub)
        converti = server._subscription_period_end(server._stripe_obj_to_dict(sub))
        statut = server._map_stripe_status(server._stripe_obj_to_dict(sub).get("status"))

        print(f"   objet Stripe brut        -> {brut}")
        print(f"   après _stripe_obj_to_dict -> {converti}")
        print(f"   statut cartographié       -> {statut}")

        if converti:
            print("   ✅ Le code lit correctement un vrai objet Stripe.")
        else:
            print("   ❌ AUCUNE date lue. L'abonné serait bloqué après avoir payé.")
            print("      Vérifie _subscription_period_end et _stripe_obj_to_dict.")
    finally:
        try:
            stripe.Customer.delete(cust.id)
            print("   🧹 Client de vérification supprimé.")
        except Exception:
            print(f"   ⚠️  Client {cust.id} non supprimé — retire-le à la main.")


def main():
    cle, mode = cle_et_mode()
    stripe.api_key = cle
    print(f"\nFacturePro — configuration Stripe [{mode}]")
    print(f"Endpoint visé : {URL_WEBHOOK}")
    if mode == "LIVE":
        confirmer_live()
    try:
        action_1_webhook()
        action_2_portail()
        action_3_verifier(mode)
    except stripe.AuthenticationError:
        fatal("Clé refusée par Stripe. Vérifie qu'elle est active et du bon compte.")
    except stripe.StripeError as e:
        # Jamais str(e) brut : le message peut contenir la requête, donc la clé.
        fatal(f"Erreur Stripe : {type(e).__name__} — {getattr(e, 'user_message', None) or 'voir le tableau de bord'}")

    print("\n" + "─" * 70)
    print("Il reste UNE chose que ce script ne peut pas faire : le test de paiement.")
    print("Stripe Checkout exige un navigateur.")
    print()
    print("  1. Va sur facturepro.ca → Abonnement → Souscrire")
    print("  2. Carte 4242 4242 4242 4242, date future, CVC au hasard")
    print("  3. Vérifie que l'organisation porte bien subscription_current_period_end")
    print("  4. Ouvre « Gérer mon abonnement » → résilie")
    print("  5. Vérifie que le statut passe à `canceled` et que terminated_at est daté")
    print()
    print("L'étape 3 est la plus importante : une organisation `active` SANS date est")
    print("refusée par la garde d'accès — c'est « j'ai payé et je suis bloqué ».")
    print("─" * 70)


if __name__ == "__main__":
    main()
