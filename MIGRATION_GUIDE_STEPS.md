# 🚀 Guide Migration FacturePro - Production Ready

## ÉTAPE 1 : MongoDB Atlas (Base de Données)

### 1.1 Créer le cluster
1. Allez sur https://cloud.mongodb.com/
2. Connectez-vous ou créez un compte
3. "Build a Database" → "M0 Free" → "Create Cluster"
4. Nom du cluster : `facturepro-production`
5. Région : `US East (N. Virginia)` ou proche du Canada

### 1.2 Configuration sécurité
1. "Database Access" → "Add New Database User"
   - Username: `facturepro-admin`
   - Password: Générer un mot de passe sécurisé (GARDEZ-LE!)
2. "Network Access" → "Add IP Address" → "0.0.0.0/0" (pour Render)

### 1.3 Obtenir la connection string
1. "Database" → "Connect" → "Connect your application"
2. Copiez la string : `mongodb+srv://facturepro-admin:PASSWORD@cluster.mongodb.net/facturepro`

---

## ÉTAPE 2 : Render (Backend API)

### 2.1 Créer le service
1. Allez sur https://render.com/
2. "New +" → "Web Service"
3. "Build and deploy from a Git repository" → "Public Git Repository"
4. Repository URL : (On va créer un GitHub repo)

### 2.2 Configuration du service
- **Name:** `facturepro-api`
- **Environment:** `Python 3`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn server:app --host 0.0.0.0 --port $PORT`

### 2.3 Variables d'environnement Render
```
MONGO_URL=mongodb+srv://facturepro-admin:VOTRE_PASSWORD@cluster.mongodb.net/facturepro
DB_NAME=facturepro
JWT_SECRET=votre-jwt-secret-super-securise-ici
STRIPE_API_KEY=sk_live_votre_cle_stripe
CORS_ORIGINS=https://facturepro.ca,https://www.facturepro.ca
```

---

## ÉTAPE 3 : Vercel (Frontend)

### 3.1 Configuration
1. Allez sur https://vercel.com/
2. "Add New..." → "Project"
3. Import Git Repository (GitHub)

### 3.2 Variables d'environnement Vercel
```
REACT_APP_BACKEND_URL=https://facturepro-api.onrender.com
```

### 3.3 Domaine personnalisé
1. Project Settings → Domains
2. Ajouter : `facturepro.ca` et `www.facturepro.ca`
3. Vercel donnera des enregistrements DNS

---

## ÉTAPE 4 : Configuration DNS IONOS

### 4.1 Enregistrements à ajouter
```
Type: A
Name: @
Value: 76.76.21.21 (IP Vercel)

Type: CNAME  
Name: www
Value: cname.vercel-dns.com

Type: CNAME
Name: api
Value: facturepro-api.onrender.com
```

---

## ÉTAPE 5 : GitHub Repository

Je vais préparer un repository avec tous les fichiers optimisés.

**Voulez-vous que je commence par créer le repository GitHub avec tous les fichiers prêts pour le déploiement ?**