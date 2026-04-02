# Guide de Deploiement FacturePro - Render + MongoDB Atlas

## IMPORTANT : Pourquoi MongoDB Atlas au lieu de Supabase ?
L'ancien code utilisait Supabase (PostgreSQL) via httpx, mais cela causait des erreurs 500.
Le nouveau code utilise **pymongo** (synchrone), qui fonctionne parfaitement sur Render.
Vous avez besoin d'une base MongoDB Atlas (gratuite).

---

## Etape 1 : Creer une base MongoDB Atlas (GRATUIT)

1. Allez sur https://www.mongodb.com/atlas
2. Creez un compte gratuit
3. Creez un cluster gratuit (M0 Free Tier)
4. Dans "Database Access", creez un utilisateur avec mot de passe
5. Dans "Network Access", ajoutez `0.0.0.0/0` (Allow Access from Anywhere)
6. Cliquez "Connect" > "Connect your application" > Copiez l'URL de connexion
   - Format: `mongodb+srv://USERNAME:PASSWORD@cluster0.xxxxx.mongodb.net/facturepro?retryWrites=true&w=majority`

---

## Etape 2 : Configurer Render

### Variables d'environnement (Settings > Environment):
```
MONGO_URL=mongodb+srv://USERNAME:PASSWORD@cluster0.xxxxx.mongodb.net/facturepro?retryWrites=true&w=majority
DB_NAME=facturepro
JWT_SECRET=votre-secret-jwt-super-long-et-aleatoire
CORS_ORIGINS=https://facturepro.ca,https://www.facturepro.ca,https://facturepro.vercel.app
PORT=8000
```

### Build Command:
```
pip install -r requirements.txt
```

### Start Command:
```
uvicorn server:app --host 0.0.0.0 --port $PORT
```

---

## Etape 3 : Configurer Vercel (Frontend)

### Variables d'environnement:
```
REACT_APP_BACKEND_URL=https://facturepro-api.onrender.com
```

---

## Etape 4 : Deployer

1. Poussez le code sur GitHub
2. Render va auto-deployer le backend
3. Vercel va auto-deployer le frontend
4. Au premier demarrage, le backend va automatiquement creer le compte gussdub@gmail.com

---

## Fichiers de backend necessaires:
- `server.py` (le fichier principal)
- `requirements.txt` (les dependances)
- `.env` n'est PAS necessaire sur Render (utilisez les variables d'environnement Render)

## Le compte gussdub@gmail.com:
- Est cree automatiquement au demarrage du serveur (seed)
- Mot de passe: testpass123
- A la gratuite permanente (EXEMPT_USERS dans server.py)
