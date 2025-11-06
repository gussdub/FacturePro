#!/usr/bin/env python3
"""
Script pour vérifier et corriger le compte gussdub@gmail.com
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import hashlib
import secrets
from datetime import datetime, timezone, timedelta

# MongoDB connection
MONGO_URL = "mongodb://localhost:27017/facturepro"
DB_NAME = "facturepro"

def get_password_hash(password):
    """Same as backend"""
    salt = secrets.token_hex(32)
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return salt + password_hash.hex()

def verify_password(plain_password, hashed_password):
    """Same as backend"""
    try:
        salt = hashed_password[:64]
        stored_hash = hashed_password[64:]
        password_hash = hashlib.pbkdf2_hmac('sha256', plain_password.encode('utf-8'), salt.encode('utf-8'), 100000)
        return password_hash.hex() == stored_hash
    except:
        return False

async def fix_gussdub_account():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Check account
    user = await db.users.find_one({"email": "gussdub@gmail.com"})
    if not user:
        print("❌ Account not found!")
        client.close()
        return
    
    print("✅ Account found")
    print(f"   Company: {user.get('company_name')}")
    print(f"   Active: {user.get('is_active')}")
    print(f"   Status: {user.get('subscription_status')}")
    
    # Test current password
    current_works = verify_password('testpass123', user.get('hashed_password', ''))
    print(f"   Current password works: {current_works}")
    
    if not current_works:
        print("🔧 Fixing password...")
        new_hash = get_password_hash('testpass123')
        await db.users.update_one(
            {"email": "gussdub@gmail.com"},
            {
                "$set": {
                    "hashed_password": new_hash,
                    "is_active": True,
                    "subscription_status": "trial",
                    "trial_end_date": datetime.now(timezone.utc) + timedelta(days=3650)  # 10 years
                }
            }
        )
        print("✅ Password fixed and account updated")
    
    # Verify fix
    updated_user = await db.users.find_one({"email": "gussdub@gmail.com"})
    works_now = verify_password('testpass123', updated_user.get('hashed_password', ''))
    print(f"✅ Final verification: password works = {works_now}")
    
    client.close()
    
    print("\n🎯 LOGIN CREDENTIALS:")
    print("   URL: https://facture-wizard.preview.emergentagent.com")
    print("   Email: gussdub@gmail.com")
    print("   Password: testpass123")
    print("   Status: EXEMPT (free access forever)")

if __name__ == "__main__":
    asyncio.run(fix_gussdub_account())