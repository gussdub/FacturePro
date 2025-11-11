#!/usr/bin/env python3
"""
Update logo URL in company settings
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

# Load from backend directory
load_dotenv('/app/backend/.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'facturepro')
TEST_EMAIL = "gussdub@gmail.com"
LOGO_URL = "https://customer-assets.emergentagent.com/job_facturepro/artifacts/y8rea1ms_2c256145-633e-411d-9781-dce2201c8da3_wm.jpeg"

async def update_logo():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    try:
        # Get user
        user = await db.users.find_one({"email": TEST_EMAIL})
        if not user:
            print(f"User {TEST_EMAIL} not found")
            return
            
        print(f"Found user: {user['email']}")
        user_id = user['id']
        
        # Update company settings with logo
        result = await db.company_settings.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "logo_url": LOGO_URL,
                    "primary_color": "#0d9488",
                    "secondary_color": "#06b6d4"
                }
            },
            upsert=True
        )
        
        if result.modified_count > 0 or result.upserted_id:
            print(f"✅ Logo URL updated successfully!")
            print(f"   Logo URL: {LOGO_URL}")
            
            # Verify the update
            settings = await db.company_settings.find_one({"user_id": user_id})
            if settings:
                print(f"\n✅ Verified settings:")
                print(f"   Logo URL: {settings.get('logo_url')}")
                print(f"   Primary Color: {settings.get('primary_color')}")
                print(f"   Company Name: {settings.get('company_name')}")
        else:
            print("❌ Failed to update logo")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(update_logo())
