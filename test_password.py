#!/usr/bin/env python3
"""
Test and fix password for gussdub@gmail.com
"""

import asyncio
import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

# Load from backend directory
load_dotenv('/app/backend/.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'facturepro')
TEST_EMAIL = "gussdub@gmail.com"
TEST_PASSWORD = "testpass123"

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

async def test_and_fix_password():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    try:
        # Get user
        user = await db.users.find_one({"email": TEST_EMAIL})
        if not user:
            print(f"User {TEST_EMAIL} not found")
            return
            
        print(f"Found user: {user['email']}")
        current_hash = user.get('hashed_password')
        print(f"Current hash: {current_hash}")
        
        # Test current password
        if current_hash and verify_password(TEST_PASSWORD, current_hash):
            print("✅ Current password is correct!")
            return
        else:
            print("❌ Current password is incorrect")
        
        # Try some common passwords
        common_passwords = ["testpass123", "password", "123456", "admin", "test"]
        for pwd in common_passwords:
            if current_hash and verify_password(pwd, current_hash):
                print(f"✅ Found working password: {pwd}")
                return
        
        print("No common passwords work. Setting new password...")
        
        # Set new password
        new_hash = hash_password(TEST_PASSWORD)
        result = await db.users.update_one(
            {"email": TEST_EMAIL},
            {"$set": {"hashed_password": new_hash}}
        )
        
        if result.modified_count > 0:
            print(f"✅ Password updated to: {TEST_PASSWORD}")
            
            # Verify the new password works
            updated_user = await db.users.find_one({"email": TEST_EMAIL})
            if verify_password(TEST_PASSWORD, updated_user['hashed_password']):
                print("✅ New password verified!")
            else:
                print("❌ New password verification failed!")
        else:
            print("❌ Failed to update password")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(test_and_fix_password())