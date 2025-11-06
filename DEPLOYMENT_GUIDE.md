# FacturePro - Déploiement Production

## Architecture
- **Frontend:** Vercel (facturepro.ca)
- **Backend:** Render (api.facturepro.ca)
- **Database:** MongoDB Atlas
- **Files:** Cloudinary/AWS S3

## Variables d'Environnement

### Backend (Render)
```
MONGO_URL=mongodb+srv://username:password@cluster.mongodb.net/facturepro
DB_NAME=facturepro
JWT_SECRET=your-secure-jwt-secret-here
STRIPE_API_KEY=sk_live_your_stripe_key
CORS_ORIGINS=https://facturepro.ca,https://www.facturepro.ca
FRONTEND_URL=https://facturepro.ca
```

### Frontend (Vercel)
```
REACT_APP_BACKEND_URL=https://api.facturepro.ca
```

## Déploiement

1. **MongoDB Atlas :** Créer cluster + obtenir connection string
2. **Render :** Déployer backend avec variables d'environnement
3. **Vercel :** Déployer frontend avec domaine personnalisé
4. **DNS IONOS :** Pointer facturepro.ca vers Vercel, api.facturepro.ca vers Render

## Compte Exempt
Email: gussdub@gmail.com (même exemption dans nouveau code)