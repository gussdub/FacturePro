# 🎯 COMMANDES À EXÉCUTER - Migration FacturePro

## ÉTAPE 1 : MongoDB Atlas
1. Créer compte sur https://cloud.mongodb.com/
2. Créer cluster gratuit M0
3. Créer utilisateur : `facturepro-admin` + password sécurisé
4. Network Access : autoriser 0.0.0.0/0
5. Copier connection string

---

## ÉTAPE 2 : GitHub Repository

### Créer nouveau repository
1. GitHub → New Repository
2. Nom : `facturepro-production`
3. Public ou Private selon préférence

### Commands Git (à exécuter)
```bash
cd /app/production
git init
git add .
git commit -m "Initial FacturePro production setup"
git remote add origin https://github.com/VOTRE_USERNAME/facturepro-production.git
git push -u origin main
```

---

## ÉTAPE 3 : Render (Backend)

### Déployer Backend
1. Render.com → New Web Service
2. Connect Repository → Choisir votre repo GitHub
3. Configuration :
   - **Root Directory:** `backend`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn server:app --host 0.0.0.0 --port $PORT`

### Variables d'Environnement Render
```
MONGO_URL=mongodb+srv://facturepro-admin:VOTRE_PASSWORD@cluster.mongodb.net/facturepro
DB_NAME=facturepro
JWT_SECRET=facturepro-jwt-2024-super-secure-key
STRIPE_API_KEY=sk_test_emergent
CORS_ORIGINS=https://facturepro.ca,https://www.facturepro.ca
```

---

## ÉTAPE 4 : Vercel (Frontend)

### Déployer Frontend
1. Vercel.com → New Project
2. Import Git Repository → Même repo
3. Configuration :
   - **Framework:** `Create React App`
   - **Root Directory:** `frontend`
   - **Build Command:** `npm run build`
   - **Output Directory:** `build`

### Variables d'Environnement Vercel
```
REACT_APP_BACKEND_URL=https://VOTRE_APP_NAME.onrender.com
```

### Domaines Personnalisés
1. Project Settings → Domains
2. Ajouter `facturepro.ca`
3. Ajouter `www.facturepro.ca`

---

## ÉTAPE 5 : DNS IONOS

### Enregistrements à ajouter
```
# Frontend (Vercel)
Type: A, Name: @, Value: 76.76.21.21
Type: CNAME, Name: www, Value: cname.vercel-dns.com

# Backend API (Render)  
Type: CNAME, Name: api, Value: VOTRE_APP_NAME.onrender.com
```

---

## RÉSULTAT FINAL
- ✅ **facturepro.ca** → Frontend Vercel
- ✅ **api.facturepro.ca** → Backend Render  
- ✅ **MongoDB Atlas** → Base de données cloud
- ✅ **Compte exempt** : gussdub@gmail.com

**Prêt à commencer ? Dites-moi à quelle étape vous voulez que je vous assiste !**