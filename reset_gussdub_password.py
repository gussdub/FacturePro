#!/usr/bin/env python3
"""Reset gussdub@gmail.com password to testpass123"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import hashlib
import secrets

MONGO_URL = "mongodb://localhost:27017/facturepro"
DB_NAME = "facturepro"

def get_password_hash(password):
    salt = secrets.token_hex(32)
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return salt + password_hash.hex()

async def reset_password():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    new_hash = get_password_hash('testpass123')
    
    result = await db.users.update_one(
        {"email": "gussdub@gmail.com"},
        {"$set": {"hashed_password": new_hash}}
    )
    
    if result.modified_count > 0:
        print("✅ Password reset successfully to 'testpass123'")
    else:
        print("❌ Failed to reset password")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(reset_password())
