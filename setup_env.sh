#!/bin/bash
# Crée les fichiers .env pour le dev local
# Usage: bash setup_env.sh
set -e
cd "$(dirname "$0")"

cat > backend/.env << 'EOF'
# DB locale (copie de prod, restaurée le 2026-06-16)
MONGO_URL=mongodb://localhost:27017
DB_NAME=facturepro

# JWT - copie la vraie valeur depuis Emergent si tu veux tester
# avec tes tokens de prod, sinon n'importe quelle chaîne fait l'affaire
JWT_SECRET=dev-only-change-me-or-copy-from-emergent

# Stripe TEST
STRIPE_API_KEY=sk_test_emergent

# Emergent Object Storage - uploads logos/reçus cassés sans la vraie clé
EMERGENT_LLM_KEY=

# Resend - emails désactivés sans clé (pas grave en dev)
RESEND_API_KEY=
SENDER_EMAIL=noreply@facturepro.ca

# CORS pour le frontend local
CORS_ORIGINS=http://localhost:3000

PORT=8000
EOF

cat > frontend/.env << 'EOF'
REACT_APP_BACKEND_URL=http://localhost:8000
EOF

echo "Created backend/.env"
echo "Created frontend/.env"
ls -la backend/.env frontend/.env
