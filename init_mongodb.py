#!/usr/bin/env python3
"""
Script d'initialisation MongoDB Atlas pour FacturePro
Crée le compte gussdub@gmail.com avec exemption
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import bcrypt
from datetime import datetime, timezone, timedelta
import uuid

# MongoDB Atlas connection
MONGO_URL = "mongodb+srv://facturepro-admin:bBi8r8uoPG1dlLNO@facturepro-production.8gnogmj.mongodb.net/?appName=facturepro-production"
DB_NAME = "facturepro"

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

async def initialize_database():
    print("🔧 Connexion à MongoDB Atlas...")
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    try:
        # Test connection
        await db.command("ping")
        print("✅ Connexion MongoDB Atlas réussie!")
        
        # Check if gussdub account exists
        existing_user = await db.users.find_one({"email": "gussdub@gmail.com"})
        
        if existing_user:
            print("✅ Compte gussdub@gmail.com déjà existant")
            user_id = existing_user["id"]
        else:
            print("🔧 Création du compte gussdub@gmail.com...")
            
            # Create gussdub account with exemption
            user_id = str(uuid.uuid4())
            trial_end = datetime.now(timezone.utc) + timedelta(days=3650)  # 10 years
            
            new_user = {
                "id": user_id,
                "email": "gussdub@gmail.com",
                "company_name": "ProFireManager",
                "is_active": True,
                "subscription_status": "trial",
                "trial_end_date": trial_end,
                "created_at": datetime.now(timezone.utc)
            }
            
            await db.users.insert_one(new_user)
            print("✅ Utilisateur créé")
        
        # Create/update password
        password_doc = await db.user_passwords.find_one({"user_id": user_id})
        hashed_pwd = hash_password("testpass123")
        
        if password_doc:
            await db.user_passwords.update_one(
                {"user_id": user_id},
                {"$set": {"hashed_password": hashed_pwd}}
            )
        else:
            await db.user_passwords.insert_one({
                "user_id": user_id,
                "hashed_password": hashed_pwd
            })
        print("✅ Mot de passe configuré")
        
        # Create default company settings
        settings_doc = await db.company_settings.find_one({"user_id": user_id})
        
        if not settings_doc:
            settings = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "company_name": "ProFireManager",
                "email": "gussdub@gmail.com",
                "phone": "450-000-0410",
                "address": "351 Rue Jean-louis Boudreau",
                "city": "Granby",
                "postal_code": "J2H0A3",
                "country": "Québec",
                "logo_url": "",
                "primary_color": "#3B82F6",
                "secondary_color": "#1F2937",
                "default_due_days": 30,
                "next_invoice_number": 1,
                "next_quote_number": 1,
                "gst_number": "123456789",
                "pst_number": "1234567890",
                "hst_number": "",
                "created_at": datetime.now(timezone.utc)
            }
            
            await db.company_settings.insert_one(settings)
            print("✅ Paramètres entreprise créés")
        
        # Create sample client
        sample_client = await db.clients.find_one({"user_id": user_id, "name": "Client Test"})
        if not sample_client:
            client = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "name": "Client Test",
                "email": "client@test.com",
                "phone": "514-123-4567",
                "address": "123 Rue Test",
                "city": "Montréal",
                "postal_code": "H1A 1A1",
                "country": "Canada",
                "created_at": datetime.now(timezone.utc)
            }
            await db.clients.insert_one(client)
            print("✅ Client test créé")
        
        # Create sample product
        sample_product = await db.products.find_one({"user_id": user_id, "name": "Consultation"})
        if not sample_product:
            product = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "name": "Consultation",
                "description": "Consultation professionnelle",
                "unit_price": 100.0,
                "unit": "heure",
                "category": "Services",
                "is_active": True,
                "created_at": datetime.now(timezone.utc)
            }
            await db.products.insert_one(product)
            print("✅ Produit test créé")
        
        print(f"\n🎉 BASE DE DONNÉES INITIALISÉE !")
        print(f"📧 Email: gussdub@gmail.com")
        print(f"🔑 Password: testpass123")
        print(f"🏢 Entreprise: ProFireManager")
        print(f"💾 Données permanentes dans MongoDB Atlas")
        print(f"🆓 Exemption: Accès gratuit permanent")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    asyncio.run(initialize_database())