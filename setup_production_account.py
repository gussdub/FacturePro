#!/usr/bin/env python3
"""
Créer le compte gussdub@gmail.com sur l'environnement production de facturepro.ca
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
import uuid

# MongoDB connection
MONGO_URL = "mongodb://localhost:27017/facturepro"
DB_NAME = "facturepro"

def get_password_hash(password):
    salt = secrets.token_hex(32)
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return salt + password_hash.hex()

async def create_production_account():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    print("🔧 Configuration compte production pour facturepro.ca...")
    
    # Check if account exists
    existing_user = await db.users.find_one({"email": "gussdub@gmail.com"})
    
    if existing_user:
        # Update existing account with correct settings
        await db.users.update_one(
            {"email": "gussdub@gmail.com"},
            {
                "$set": {
                    "hashed_password": get_password_hash('testpass123'),
                    "is_active": True,
                    "subscription_status": "trial",
                    "trial_end_date": datetime.now(timezone.utc) + timedelta(days=3650)  # 10 ans
                }
            }
        )
        print("✅ Compte existant mis à jour")
        user_id = existing_user["id"]
    else:
        # Create new account
        user_id = str(uuid.uuid4())
        new_user = {
            "id": user_id,
            "email": "gussdub@gmail.com",
            "hashed_password": get_password_hash('testpass123'),
            "company_name": "ProFireManager",
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "subscription_status": "trial",
            "trial_end_date": datetime.now(timezone.utc) + timedelta(days=3650),
            "subscription_id": None,
            "current_period_end": None,
            "last_payment_date": None
        }
        
        await db.users.insert_one(new_user)
        print("✅ Nouveau compte créé")
    
    # Ensure company settings exist
    existing_settings = await db.company_settings.find_one({"user_id": user_id})
    if not existing_settings:
        company_settings = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "company_name": "ProFireManager",
            "email": "gussdub@gmail.com",
            "default_due_days": 30,
            "next_invoice_number": 1,
            "next_quote_number": 1,
            "gst_number": "25357693",
            "pst_number": "2232323",
            "primary_color": "#3B82F6",
            "secondary_color": "#1F2937",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        await db.company_settings.insert_one(company_settings)
        print("✅ Paramètres entreprise créés")
    else:
        # Update with tax numbers
        await db.company_settings.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "gst_number": "25357693",
                    "pst_number": "2232323",
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        print("✅ Paramètres entreprise mis à jour")
    
    client.close()
    
    print("\n🎉 COMPTE PRODUCTION CONFIGURÉ !")
    print("=" * 50)
    print("   URL: https://facturepro.ca")
    print("   Email: gussdub@gmail.com") 
    print("   Mot de passe: testpass123")
    print("   Statut: EXEMPT (accès gratuit permanent)")
    print("   Numéros de taxes: Configurés")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(create_production_account())