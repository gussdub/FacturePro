#!/usr/bin/env python3
"""
Script pour créer le compte gussdub@gmail.com avec exemption sur facturepro.ca
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

async def create_exempt_account():
    # Connect to MongoDB
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(mongo_url)
    db = client.facturepro
    
    # Check if user already exists
    existing_user = await db.users.find_one({"email": "gussdub@gmail.com"})
    if existing_user:
        print("✅ Account gussdub@gmail.com already exists")
        print(f"   Company: {existing_user.get('company_name', 'N/A')}")
        print(f"   Status: {existing_user.get('subscription_status', 'N/A')}")
        print(f"   Active: {existing_user.get('is_active', 'N/A')}")
        return existing_user['id']
    
    # Create password hash
    def get_password_hash(password):
        salt = secrets.token_hex(32)
        password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
        return salt + password_hash.hex()
    
    # Calculate trial end date (14 days from now)
    trial_end = datetime.now(timezone.utc) + timedelta(days=14)
    
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
    print("✅ Created account gussdub@gmail.com")
    
    # Create default company settings
    company_settings = {
        "id": str(uuid.uuid4()),
        "user_id": new_user["id"],
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
    
    # Close connection
    client.close()
    print("\n🎉 Account gussdub@gmail.com created successfully with trial exemption!")
    print("   Email: gussdub@gmail.com")
    print("   Password: testpass123")
    print("   Company: ProFireManager")
    print("   Status: Exempt from subscription (permanent free access)")
    
    return new_user["id"]

if __name__ == "__main__":
    asyncio.run(create_exempt_account())