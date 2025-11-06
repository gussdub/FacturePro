#!/usr/bin/env python3
"""
Ajouter un logo au compte gussdub.prod@gmail.com directement
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone

MONGO_URL = "mongodb://localhost:27017/facturepro"
DB_NAME = "facturepro"

async def add_logo_to_production():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Update company settings with logo
    result = await db.company_settings.update_one(
        {"email": "gussdub.prod@gmail.com"},
        {
            "$set": {
                "logo_url": "/uploads/logos/logo_f417c401-be51-4dba-9580-4acd38ebda70_test.png",
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    if result.modified_count > 0:
        print("✅ Logo ajouté au compte production")
    else:
        print("❌ Échec ajout logo")
    
    # Verify
    settings = await db.company_settings.find_one({"email": "gussdub.prod@gmail.com"})
    if settings:
        print(f"✅ Vérification:")
        print(f"   Email: {settings.get('email')}")
        print(f"   Logo URL: {settings.get('logo_url')}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(add_logo_to_production())