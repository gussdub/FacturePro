#!/usr/bin/env python3
"""
Debug user existence issue
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'facturepro')
TEST_EMAIL = "gussdub@gmail.com"

async def debug_user():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    try:
        print(f"Connecting to: {MONGO_URL}")
        print(f"Database: {DB_NAME}")
        
        # Check connection
        await client.admin.command('ping')
        print("✅ MongoDB connection successful")
        
        # List all databases
        db_list = await client.list_database_names()
        print(f"Available databases: {db_list}")
        
        # Check current database collections
        collections = await db.list_collection_names()
        print(f"Collections in '{DB_NAME}': {collections}")
        
        # Search for the user in all possible ways
        print(f"\nSearching for user: {TEST_EMAIL}")
        
        # Direct search
        user = await db.users.find_one({"email": TEST_EMAIL})
        print(f"Direct search result: {user}")
        
        # Case insensitive search
        user_ci = await db.users.find_one({"email": {"$regex": f"^{TEST_EMAIL}$", "$options": "i"}})
        print(f"Case insensitive search: {user_ci}")
        
        # Search all users
        all_users = []
        cursor = db.users.find({})
        async for u in cursor:
            all_users.append(u.get('email'))
        print(f"All users in database: {all_users}")
        
        # Check if there are any documents at all
        total_users = await db.users.count_documents({})
        print(f"Total users count: {total_users}")
        
        # Try other possible collections
        for collection_name in ['user', 'User', 'USERS']:
            try:
                count = await db[collection_name].count_documents({})
                if count > 0:
                    print(f"Found {count} documents in collection '{collection_name}'")
            except:
                pass
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(debug_user())