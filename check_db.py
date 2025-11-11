#!/usr/bin/env python3
"""
Check database collections and contents
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'facturepro')

async def check_database():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    try:
        # List all collections
        collections = await db.list_collection_names()
        print(f"Collections in database '{DB_NAME}': {collections}")
        
        # Check each collection for user-related data
        for collection_name in collections:
            if 'user' in collection_name.lower():
                collection = db[collection_name]
                count = await collection.count_documents({})
                print(f"\nCollection '{collection_name}': {count} documents")
                
                if count > 0:
                    # Show sample documents
                    cursor = collection.find({}).limit(3)
                    async for doc in cursor:
                        # Remove _id for cleaner output
                        doc.pop('_id', None)
                        print(f"  Sample: {doc}")
        
        # Also check users collection specifically
        users_count = await db.users.count_documents({})
        print(f"\nUsers collection: {users_count} documents")
        
        if users_count > 0:
            cursor = db.users.find({})
            async for user in cursor:
                print(f"  User: {user.get('email')} - {user.get('company_name')}")
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(check_database())