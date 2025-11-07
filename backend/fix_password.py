import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import bcrypt
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017/facturepro')
DB_NAME = os.environ.get('DB_NAME', 'facturepro')

async def fix_password():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Find the user
    user = await db.users.find_one({"email": "gussdub@gmail.com"})
    
    if user:
        print(f"Found user: {user['email']}")
        print(f"Current hashed_password: {user.get('hashed_password', 'N/A')}")
        
        # Hash the password properly
        new_password = "testpass123"
        hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        
        # Update the user
        result = await db.users.update_one(
            {"email": "gussdub@gmail.com"},
            {"$set": {"hashed_password": hashed.decode('utf-8')}}
        )
        
        print(f"Updated {result.modified_count} user(s)")
        print(f"New hashed_password: {hashed.decode('utf-8')}")
    else:
        print("User not found")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(fix_password())
