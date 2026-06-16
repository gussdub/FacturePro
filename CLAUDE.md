# FacturePro

Application de facturation (SaaS) créée à l'origine avec Emergent, maintenant éditable depuis Claude Code.

## Stack

- **Backend** : FastAPI Python 3.11 + MongoDB (pymongo synchrone) + JWT + Stripe + Resend + ReportLab (PDF). Port interne 8001 en prod, 8000 en dev local.
- **Frontend** : React 18 (CRA) + axios + recharts + lucide-react — pas de router lib, navigation manuelle via `window.history`. Port 3000.
- **DB** : MongoDB Atlas, cluster `facturepro-production`, db `facturepro`. Collections : `users`, `user_passwords`, `invoices`, `quotes`, `clients`, `products`, `employees`, `expenses`, `company_settings`, `files`, `payment_transactions`, `trial_notifications`.
- **Object Storage** : Emergent Object Storage (clé `EMERGENT_LLM_KEY`) pour logos/reçus uploadés. Pas d'équivalent local — les uploads peuvent être cassés en dev sans cette clé.
- **Services externes** : Resend (emails), Stripe (abonnement $15/mois CAD), Frankfurter.dev (taux de change, gratuit sans clé).
- **Déploiement** :
  - **Emergent** = preview/dev. URL : `https://billing-app-32.preview.emergentagent.com`. `MONGO_URL` et les autres secrets sont stockés ici.
  - **Render** (prod) = Web Service côté backend. URL : `https://facturepro-api.onrender.com`. Build : `cd backend && pip install -r requirements.txt`. Start : `cd backend && uvicorn server:app --host 0.0.0.0 --port $PORT`. ⚠️ Free tier — dort après 15 min, premier hit prend ~30-60s pour réveiller.
  - **Vercel** = frontend (`https://facturepro.ca`).
  - **Render Postgres `facturepro-database`** : créée mais INUTILISÉE. Vestige, à ignorer ou supprimer.
- **Domaine prod** : facturepro.ca
- **Repo** : https://github.com/gussdub/FacturePro
- ⚠️ **Sync des env vars** : si tu modifies un secret dans Emergent (`MONGO_URL`, `STRIPE_API_KEY`, etc.), tu dois aussi le mettre à jour manuellement dans Render. Aucune synchro automatique.

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

Backend (`backend/.env` — non commité, à demander à Emergent) :

```
MONGO_URL=mongodb+srv://...@facturepro-production...    # depuis Emergent env vars
DB_NAME=facturepro
JWT_SECRET=...                                          # même valeur que prod
STRIPE_API_KEY=sk_test_emergent                         # ou sk_test_/sk_live_ Stripe perso
EMERGENT_LLM_KEY=...                                    # Object Storage (logos/reçus)
RESEND_API_KEY=...
SENDER_EMAIL=noreply@facturepro.ca
CORS_ORIGINS=http://localhost:3000
PORT=8000
```

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

⚠️ `requirements.txt` référence `emergentintegrations` via `--extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/` (utilisé pour Stripe Checkout). Si l'install échoue hors Emergent, isoler l'import à `server.py:3` et remplacer par l'API Stripe directe.

## Workflow Emergent ↔ Claude Code

Les commits sur `main` ressemblent à `auto-commit for <job_id>` — c'est Emergent qui pousse à chaque "Save to GitHub". Donc oui : un save côté Emergent met à jour ce repo.

**Règle d'or pour éviter les conflits** :

1. **Avant** d'éditer depuis Claude Code → `git pull` pour récupérer les modifs Emergent récentes.
2. **Après** une session Claude Code → `git push` pour qu'Emergent reparte de ta base à jour.
3. **Ne jamais** éditer en parallèle des deux côtés sur le même fichier — Emergent ne sait pas merger, ça écrasera tes changements locaux au prochain auto-commit.

Si conflit : résoudre manuellement, jamais `--force` sur `main`.

## Déploiement

- Push sur `main` → Render redéploie le backend automatiquement, Vercel redéploie le frontend.
- Variables d'env de prod : configurées dans les dashboards Render et Vercel (pas dans le repo).
- Voir `DEPLOYMENT_GUIDE.md` pour les détails MongoDB Atlas / Render / Vercel.

## Pour Claude

- Le fichier `server.py` est gros (78 KB) — utiliser `Grep`/`Read` ciblé plutôt que de tout lire.
- Pas de tests automatisés CI ; `backend_test.py` et `backend/tests/` existent mais à vérifier avant de s'en servir comme référence.
- Ne pas modifier `.emergent/emergent.yml`.
- Ignorer les `server_*.py` (sauf `server.py`) et les `App*.js` de backup sauf demande explicite.
