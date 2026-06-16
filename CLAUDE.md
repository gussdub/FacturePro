# FacturePro

Application de facturation (SaaS). Créée à l'origine avec Emergent, **migrée pour fonctionner sans Emergent** le 2026-06-16. Maintenant 100 % éditable et déployable depuis Claude Code.

## Stack

- **Backend** : FastAPI Python 3.11 + MongoDB (pymongo synchrone) + JWT + Stripe (lib officielle) + Resend + ReportLab (PDF).
- **Frontend** : React 18 (CRA) + axios + recharts + lucide-react — pas de router lib, navigation manuelle via `window.history`.
- **DB** : MongoDB Atlas, cluster `facturepro-production`, db `facturepro`. Collections : `users`, `user_passwords`, `invoices`, `quotes`, `clients`, `products`, `employees`, `expenses`, `company_settings`, `files` (binary inline), `payment_transactions`, `trial_notifications`, `quote_tokens`, `password_resets`.
- **Object Storage** : ⚠️ MIGRÉ — les fichiers sont stockés **en binary BSON inline dans `db.files`** (champ `data`). Plus aucune dépendance Emergent storage. Les 8 anciens fichiers qui pointaient vers Emergent storage retournent **HTTP 410** et doivent être re-uploadés.
- **Services externes** : Resend (emails), Stripe (abonnement $15/mois CAD via Checkout, mode payment), Frankfurter.dev (taux de change, gratuit).
- **Déploiement (sans Emergent)** :
  - **Render** : Web Service `facturepro-backend` (compte gussdub), URL `https://facturepro-backend-dkvn.onrender.com`. Build : `cd backend && pip install -r requirements.txt`. Start : `cd backend && uvicorn server:app --host 0.0.0.0 --port $PORT`. ⚠️ Free tier — dort après 15 min, premier hit ~30-60s.
  - **Vercel** : projet `facturepro` (équipe `profiremanagers-projects`), URL temporaire `https://facturepro-psi.vercel.app`, domaine custom `https://facturepro.ca`. Root directory : `frontend`. CRA auto-détecté. Env var : `REACT_APP_BACKEND_URL=https://facturepro-backend-dkvn.onrender.com`.
  - **DNS** : Ionos, A record + TXT validation Vercel. Migration 2026-06-16.
  - **Services obsolètes (à supprimer quand prêt)** : `facturepro-api.onrender.com` (ancien backend Emergent), `facturepro-database` (Postgres Render inutilisée), projet Vercel d'Emergent.
- **Domaine prod** : facturepro.ca
- **Repo** : https://github.com/gussdub/FacturePro
- **Workflow push → prod** : `git push main` → Render redéploie backend, Vercel redéploie frontend. Aucune intervention manuelle.

## Structure (fichiers qui comptent)

```
backend/
  server.py              ← fichier actif (78 KB, 62 endpoints, auth + factures + Stripe)
  requirements.txt       ← deps actives
  server_*.py            ← anciennes versions Emergent (Supabase/postgres/no_mongo…), à ignorer
  fix_password.py        ← utilitaire one-shot
  tests/
frontend/
  src/
    App.js               ← entrée active
    App.js.backup        ← à ignorer
    App_final.js         ← à ignorer
    config.js            ← BACKEND_URL, helpers devise
    context/AuthContext.js
    pages/               ← Dashboard, Clients, Products, Invoices, Quotes, Employees, Expenses, Export, Settings, Subscription, Login
    components/          ← Layout, NotificationsDropdown, CurrencySelector, FactureProLogo, ForgotPasswordModal, QuickActionCard
  package.json
.emergent/emergent.yml   ← métadonnées Emergent — ne pas toucher
```

> Plusieurs `server_*.py` et `App*.js` sont des versions abandonnées laissées par Emergent. Seuls `backend/server.py` et `frontend/src/App.js` sont actifs.

## Variables d'environnement

Backend (`backend/.env` — non commité ; le script `setup_env.sh` à la racine génère le squelette pour dev local) :

```
MONGO_URL=mongodb://localhost:27017               # dev local (copie de prod restaurée)
DB_NAME=facturepro
JWT_SECRET=...                                    # n'importe quoi en dev ; valeur prod = celle des env vars Render
STRIPE_API_KEY=sk_test_...                        # ta propre clé Stripe test/live
STRIPE_WEBHOOK_SECRET=whsec_...                   # depuis Stripe Dashboard → Webhooks
RESEND_API_KEY=re_...
SENDER_EMAIL=noreply@facturepro.ca
CORS_ORIGINS=http://localhost:3000
PORT=8000
```

Plus de `EMERGENT_LLM_KEY` — storage migré vers MongoDB inline.

Frontend (`frontend/.env`) :

```
REACT_APP_BACKEND_URL=http://localhost:8000
```

Compte de seed (créé au démarrage) : `gussdub@gmail.com` / `testpass123`. Exempté de paiement (`EXEMPT_USERS` dans `server.py:166`).

## Lancer en local

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # note: emergentintegrations vient d'un index custom
uvicorn server:app --reload --port 8000

# Frontend
cd frontend
npm install
npm start                                 # → http://localhost:3000
```

`requirements.txt` est désormais sans dépendance Emergent.

## Workflow

Depuis la migration du 2026-06-16, Emergent n'est plus utilisé. Le repo et le déploiement sont gérés à 100 % depuis Claude Code :

1. Éditer en local
2. Tester sur `localhost:3000` / `localhost:8000` (DB locale = copie restaurée de prod)
3. `git add ... && git commit -m "..." && git push origin main`
4. Render redéploie `facturepro-backend` automatiquement (~3 min)
5. Vercel redéploie `facturepro.ca` automatiquement (~2 min)

`DEPLOYMENT_GUIDE.md` à la racine est **obsolète** (parle de l'ancienne setup MongoDB Atlas + Render). Ce CLAUDE.md est la source de vérité.

## Pour Claude

- Le fichier `server.py` est gros (78 KB) — utiliser `Grep`/`Read` ciblé plutôt que de tout lire.
- Pas de tests automatisés CI ; `backend_test.py` et `backend/tests/` existent mais à vérifier avant de s'en servir comme référence.
- Ne pas modifier `.emergent/emergent.yml`.
- Ignorer les `server_*.py` (sauf `server.py`) et les `App*.js` de backup sauf demande explicite.

## Features livrées

- **2026-06-16 — Numéros officiels canadiens sur PDF (feature #2)**
  - 5 champs (BN, TPS, TVQ, TVH, NEQ) côté entreprise (`Settings`) et côté client (`Clients`)
  - Snapshot `tax_registrations` sur création de facture/devis (audit immutability)
  - Migration douce `pst_number` → `qst_number` au démarrage (idempotente)
  - Validation souple, normalisation à la saisie (uppercase, suppression espaces/tirets)
  - PDF refactor : entête épuré, ligne discrète dans la boîte "Facturer à", encadré "Numéros d'enregistrement" en bas
  - Spec : `docs/superpowers/specs/2026-06-16-tax-registrations-design.md`
  - Plan : `docs/superpowers/plans/2026-06-16-tax-registrations.md`

- **2026-06-16 — Catégories de dépenses ARC (feature #3)**
  - 17 catégories canoniques + "Autre" libre, organisées en 5 groupes (T2125/T2 GIFI)
  - Snapshot sur chaque dépense : code, label, ligne ARC, % déductible, montant déductible calculé
  - Règle 50 % sur les repas appliquée automatiquement (`deductible_amount`)
  - Sélecteur d'entité fiscale (sole_proprietor / corporation) dans Settings — pour la future feature #10 (export T2125/T2)
  - Picker UI groupé natif + zone d'aide jaune pour les catégories partiellement déductibles
  - Endpoint public `GET /api/expense-categories`
  - Spec : `docs/superpowers/specs/2026-06-16-expense-categories-design.md`
  - Plan : `docs/superpowers/plans/2026-06-16-expense-categories.md`
