#!/usr/bin/env python3
"""
URGENT DIAGNOSTIC: gussdub@gmail.com Login Issue
Tests password authentication and account state for gussdub@gmail.com
"""

import asyncio
import sys
import os
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import hashlib
import secrets

# MongoDB connection
MONGO_URL = "mongodb://localhost:27017/facturepro"
DB_NAME = "facturepro"

def get_password_hash(password):
    """Generate password hash using same method as backend"""
    salt = secrets.token_hex(32)
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return salt + password_hash.hex()

def verify_password(plain_password, hashed_password):
    """Verify password using same method as backend"""
    try:
        salt = hashed_password[:64]
        stored_hash = hashed_password[64:]
        password_hash = hashlib.pbkdf2_hmac('sha256', plain_password.encode('utf-8'), salt.encode('utf-8'), 100000)
        return password_hash.hex() == stored_hash
    except Exception as e:
        print(f"❌ Error verifying password: {e}")
        return False

async def diagnose_gussdub_account():
    """Comprehensive diagnostic for gussdub@gmail.com account"""
    
    print("=" * 80)
    print("🔍 URGENT DIAGNOSTIC: gussdub@gmail.com Login Issue")
    print("=" * 80)
    print()
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    try:
        # Step 1: Check if account exists
        print("📋 Step 1: Checking if gussdub@gmail.com account exists...")
        user = await db.users.find_one({"email": "gussdub@gmail.com"})
        
        if not user:
            print("❌ CRITICAL: Account gussdub@gmail.com does NOT exist in database!")
            print("   Solution: User needs to register a new account")
            return
        
        print("✅ Account EXISTS in database")
        print(f"   User ID: {user.get('id')}")
        print(f"   Company: {user.get('company_name')}")
        print(f"   Created: {user.get('created_at')}")
        print()
        
        # Step 2: Check account state
        print("📋 Step 2: Examining account state...")
        print(f"   is_active: {user.get('is_active', 'NOT SET')}")
        print(f"   subscription_status: {user.get('subscription_status', 'NOT SET')}")
        print(f"   trial_end_date: {user.get('trial_end_date', 'NOT SET')}")
        print(f"   subscription_id: {user.get('subscription_id', 'NOT SET')}")
        print()
        
        # Step 3: Examine password hash
        print("📋 Step 3: Examining password hash structure...")
        hashed_password = user.get('hashed_password', '')
        print(f"   Hash length: {len(hashed_password)} characters")
        print(f"   Hash format: {'VALID (salt + hash)' if len(hashed_password) == 128 else 'INVALID'}")
        print(f"   Hash preview: {hashed_password[:20]}...{hashed_password[-20:]}")
        print()
        
        # Step 4: Test password verification with common passwords
        print("📋 Step 4: Testing password verification with common passwords...")
        test_passwords = [
            'testpass123',
            'password123', 
            'admin123',
            'gussdub123',
            '123456',
            'password',
            'test123',
            'facturepro123'
        ]
        
        successful_password = None
        for password in test_passwords:
            is_valid = verify_password(password, hashed_password)
            if is_valid:
                print(f"   ✅ SUCCESS: Password '{password}' is CORRECT!")
                successful_password = password
                break
            else:
                print(f"   ❌ Failed: '{password}'")
        
        if not successful_password:
            print()
            print("   ⚠️  NONE of the tested passwords work!")
            print()
        
        # Step 5: Compare with other working accounts
        print("📋 Step 5: Comparing with other accounts...")
        other_users = await db.users.find().limit(5).to_list(5)
        print(f"   Total users in database: {await db.users.count_documents({})}")
        
        for other_user in other_users:
            if other_user.get('email') != 'gussdub@gmail.com':
                other_hash = other_user.get('hashed_password', '')
                print(f"   User: {other_user.get('email')}")
                print(f"     Hash length: {len(other_hash)} (expected: 192)")
                print(f"     Hash format: {'VALID' if len(other_hash) == 192 else 'INVALID'}")
                
                # Test if testpass123 works for this user
                if verify_password('testpass123', other_hash):
                    print(f"     ✅ testpass123 works for this user")
                break
        print()
        
        # Step 6: Test hash function itself
        print("📋 Step 6: Testing password hashing function...")
        test_hash = get_password_hash('testpass123')
        print(f"   Generated test hash length: {len(test_hash)}")
        print(f"   Test hash format: {'VALID' if len(test_hash) == 192 else 'INVALID'}")
        
        # Verify the test hash works
        if verify_password('testpass123', test_hash):
            print(f"   ✅ Hash function is working correctly")
        else:
            print(f"   ❌ Hash function is BROKEN!")
        print()
        
        # Step 7: Provide solution
        print("=" * 80)
        print("📊 DIAGNOSTIC SUMMARY")
        print("=" * 80)
        
        if successful_password:
            print(f"✅ SOLUTION FOUND: User can login with password: '{successful_password}'")
            print()
            print("   Action: Inform user to use this password")
        else:
            print("❌ CRITICAL ISSUE: Cannot authenticate with any tested password")
            print()
            print("   Possible causes:")
            print("   1. Password was changed to something else")
            print("   2. Password hash is corrupted")
            print("   3. Password was set using different hashing method")
            print()
            print("   RECOMMENDED SOLUTION:")
            print("   Reset password to 'testpass123' by running:")
            print()
            print("   python3 /app/reset_gussdub_password.py")
            print()
            
            # Create password reset script
            reset_script = '''#!/usr/bin/env python3
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
'''
            
            with open('/app/reset_gussdub_password.py', 'w') as f:
                f.write(reset_script)
            
            print("   Reset script created at: /app/reset_gussdub_password.py")
        
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ ERROR during diagnostic: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(diagnose_gussdub_account())
