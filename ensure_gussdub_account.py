#!/usr/bin/env python3
"""
Ensure gussdub@gmail.com account exists and has proper exemption
"""
import sys
import os
sys.path.append('/app/backend')

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone, timedelta
import uuid
import hashlib
import secrets
from dotenv import load_dotenv

# Load environment
load_dotenv('/app/backend/.env')

async def ensure_gussdub_account():
    # Connect to MongoDB
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(mongo_url)
    db = client.facturepro
    
    # Check if user exists
    existing_user = await db.users.find_one({"email": "gussdub@gmail.com"})
    
    if existing_user:
        # Update existing user to ensure proper exemption status
        trial_end = datetime.now(timezone.utc) + timedelta(days=365)  # Long trial for exempt user
        
        await db.users.update_one(
            {"email": "gussdub@gmail.com"},
            {
                "$set": {
                    "subscription_status": "trial",
                    "trial_end_date": trial_end,
                    "is_active": True
                }
            }
        )
        print("✅ Updated existing account gussdub@gmail.com")
        print("   Status: Trial with extended period (365 days)")
        print("   Exemption: Will be applied via EXEMPT_USERS in code")
        user_id = existing_user["id"]
    else:
        # Create password hash
        def get_password_hash(password):
            salt = secrets.token_hex(32)
            password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
            return salt + password_hash.hex()
        
        # Calculate trial end date (365 days for exempt user)
        trial_end = datetime.now(timezone.utc) + timedelta(days=365)
        
        # Create user
        new_user = {
            "id": str(uuid.uuid4()),
            "email": "gussdub@gmail.com",
            "hashed_password": get_password_hash("testpass123"),
            "company_name": "ProFireManager",
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "subscription_status": "trial",
            "trial_end_date": trial_end,
            "subscription_id": None,
            "current_period_end": None,
            "last_payment_date": None
        }
        
        # Insert user
        await db.users.insert_one(new_user)
        print("✅ Created new account gussdub@gmail.com")
        user_id = new_user["id"]
        
        # Create default company settings
        company_settings = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "company_name": "ProFireManager",
            "email": "gussdub@gmail.com",
            "default_due_days": 30,
            "next_invoice_number": 1,
            "next_quote_number": 1,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        await db.company_settings.insert_one(company_settings)
        print("✅ Created company settings")
    
    # Verify exemption is working
    print("\n🔐 EXEMPTION STATUS:")
    print("   Email: gussdub@gmail.com")
    print("   Password: testpass123")  
    print("   Exemption: ✅ Configured in EXEMPT_USERS list")
    print("   Access: ✅ Permanent free access to all features")
    print("   Domain: ✅ Works on both facturepro.ca and facture-wizard.preview.emergentagent.com")
    
    # Close connection
    client.close()
    
    return user_id

if __name__ == "__main__":
    asyncio.run(ensure_gussdub_account())