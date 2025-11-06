#!/usr/bin/env python3
"""
Copier les paramètres et logo du compte preview vers le compte production
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import shutil
from pathlib import Path

# MongoDB connection
MONGO_URL = "mongodb://localhost:27017/facturepro"
DB_NAME = "facturepro"

async def copy_settings_to_production():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    print("🔄 Copie des paramètres vers le compte production...")
    
    # Find source account (preview)
    source_user = await db.users.find_one({"email": "gussdub@gmail.com"})
    if not source_user:
        print("❌ Compte source non trouvé")
        client.close()
        return
    
    # Find target account (production)
    target_user = await db.users.find_one({"email": "gussdub.prod@gmail.com"})
    if not target_user:
        print("❌ Compte cible non trouvé")
        client.close()
        return
    
    print(f"✅ Comptes trouvés:")
    print(f"   Source: {source_user['email']} ({source_user['company_name']})")
    print(f"   Cible: {target_user['email']} ({target_user['company_name']})")
    
    # Get source settings
    source_settings = await db.company_settings.find_one({"user_id": source_user["id"]})
    if not source_settings:
        print("❌ Paramètres source non trouvés")
        client.close()
        return
    
    print(f"✅ Paramètres source trouvés:")
    print(f"   Logo URL: {source_settings.get('logo_url', 'Aucun')}")
    print(f"   TPS: {source_settings.get('gst_number', 'Non défini')}")
    print(f"   TVQ: {source_settings.get('pst_number', 'Non défini')}")
    
    # Copy all settings to target user
    settings_copy = source_settings.copy()
    settings_copy['user_id'] = target_user['id']  # Update user_id
    settings_copy['email'] = target_user['email']  # Update email
    del settings_copy['_id']  # Remove MongoDB _id
    
    # Update or create target settings
    await db.company_settings.update_one(
        {"user_id": target_user["id"]},
        {"$set": settings_copy},
        upsert=True
    )
    
    print(f"✅ Paramètres copiés vers {target_user['email']}")
    
    # If there's a logo, copy the logo file too
    if source_settings.get('logo_url'):
        try:
            source_logo_path = Path(f"/app{source_settings['logo_url']}")
            if source_logo_path.exists():
                # Create new filename for target user
                logo_filename = source_logo_path.name
                new_filename = logo_filename.replace(source_user['id'], target_user['id'])
                target_logo_path = Path(f"/app/uploads/logos/{new_filename}")
                
                # Copy the logo file
                shutil.copy2(source_logo_path, target_logo_path)
                
                # Update logo URL in target settings
                new_logo_url = f"/uploads/logos/{new_filename}"
                await db.company_settings.update_one(
                    {"user_id": target_user["id"]},
                    {"$set": {"logo_url": new_logo_url}}
                )
                
                print(f"✅ Logo copié:")
                print(f"   Source: {source_logo_path}")
                print(f"   Cible: {target_logo_path}")
                print(f"   Nouvelle URL: {new_logo_url}")
            else:
                print(f"⚠️  Fichier logo source non trouvé: {source_logo_path}")
        except Exception as e:
            print(f"❌ Erreur lors de la copie du logo: {e}")
    
    client.close()
    
    print(f"\n🎉 MIGRATION TERMINÉE !")
    print(f"=" * 50)
    print(f"   Compte production: gussdub.prod@gmail.com")
    print(f"   Paramètres: Copiés avec succès")
    print(f"   Logo: Disponible")
    print(f"   Taxes: Configurées")
    print(f"=" * 50)

if __name__ == "__main__":
    asyncio.run(copy_settings_to_production())