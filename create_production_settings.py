#!/usr/bin/env python3
"""
Créer les paramètres complets pour gussdub.prod@gmail.com
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import uuid

MONGO_URL = "mongodb://localhost:27017/facturepro"
DB_NAME = "facturepro"

async def create_complete_settings():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Find user
    user = await db.users.find_one({"email": "gussdub.prod@gmail.com"})
    if not user:
        print("❌ Utilisateur non trouvé")
        client.close()
        return
    
    print(f"✅ Utilisateur trouvé: {user['id']}")
    
    # Create complete company settings
    settings = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "company_name": "ProFireManager",
        "email": "gussdub.prod@gmail.com",
        "phone": "450-000-0410",
        "address": "351 Rue Jean-louis Boudreau",
        "city": "Granby",
        "postal_code": "J2H0A3",
        "country": "Québec",
        "logo_url": "/uploads/logos/logo_f417c401-be51-4dba-9580-4acd38ebda70_test.png",
        "primary_color": "#3B82F6",
        "secondary_color": "#1F2937",
        "default_due_days": 30,
        "next_invoice_number": 1,
        "next_quote_number": 1,
        "gst_number": "25357693",
        "pst_number": "2232323",
        "hst_number": "",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    # Insert settings
    await db.company_settings.insert_one(settings)
    print("✅ Paramètres complets créés")
    
    # Verify
    saved_settings = await db.company_settings.find_one({"user_id": user["id"]})
    if saved_settings:
        print("✅ Vérification réussie:")
        print(f"   Logo: {saved_settings.get('logo_url')}")
        print(f"   TPS: {saved_settings.get('gst_number')}")
        print(f"   TVQ: {saved_settings.get('pst_number')}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(create_complete_settings())