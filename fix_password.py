#!/usr/bin/env python3
"""
Fix password for test user
"""

import asyncio
import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'facturepro')
TEST_EMAIL = "gussdub@gmail.com"
TEST_PASSWORD = "testpass123"

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

async def fix_password():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    try:
        # Check if user exists
        user = await db.users.find_one({"email": TEST_EMAIL})
        if not user:
            print(f"User {TEST_EMAIL} not found")
            return
            
        print(f"Found user: {user['email']}")
        print(f"Current password hash: {user.get('hashed_password', 'N/A')}")
        
        # Update password
        new_hash = hash_password(TEST_PASSWORD)
        print(f"New password hash: {new_hash}")
        
        result = await db.users.update_one(
            {"email": TEST_EMAIL},
            {"$set": {"hashed_password": new_hash}}
        )
        
        if result.modified_count > 0:
            print("Password updated successfully!")
        else:
            print("Failed to update password")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(fix_password())