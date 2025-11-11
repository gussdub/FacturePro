#!/usr/bin/env python3
"""
Check what users exist in the database
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'facturepro')

async def check_users():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    try:
        # Get all users
        users = []
        cursor = db.users.find({})
        async for user in cursor:
            users.append({
                'email': user.get('email'),
                'company_name': user.get('company_name'),
                'id': user.get('id'),
                'has_password': bool(user.get('hashed_password'))
            })
        
        print(f"Found {len(users)} users:")
        for user in users:
            print(f"  - {user['email']} ({user['company_name']}) - ID: {user['id']} - Has password: {user['has_password']}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(check_users())