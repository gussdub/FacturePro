from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import os
import jwt
import bcrypt
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from typing import Optional, List
import uuid
import secrets
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Load environment
load_dotenv()

# Configuration
MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'facturepro')
JWT_SECRET = os.environ.get('JWT_SECRET', 'default-secret')

# FastAPI app
app = FastAPI(title="FacturePro API", version="2.0.0")
security = HTTPBearer()

# MongoDB client
mongo_client = None
db = None

# Models
class User(BaseModel):
    id: str
    email: str
    company_name: str
    is_active: bool = True

class UserCreate(BaseModel):
    email: str
    password: str
    company_name: str

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User

class Client(BaseModel):
    id: str
    user_id: str
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None

# Utility functions
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(hours=24)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

# MongoDB helpers
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
        
        user_doc = await db.users.find_one({"id": user_id})
        if not user_doc:
            raise HTTPException(401, "User not found")
        
        return User(
            id=user_doc["id"],
            email=user_doc["email"],
            company_name=user_doc["company_name"],
            is_active=user_doc.get("is_active", True)
        )
    except Exception as e:
        print(f"Auth error: {e}")
        raise HTTPException(401, "Invalid token")

# Routes
@app.get("/")
async def root():
    return {"message": "FacturePro API v2.0", "status": "running", "database": "MongoDB"}

@app.get("/api/health")
async def health():
    try:
        # Test MongoDB connection
        await db.command('ping')
        users_count = await db.users.count_documents({})
        return {"status": "healthy", "database": "connected", "users_count": users_count}
    except Exception as e:
        return {"status": "unhealthy", "database": "error", "error": str(e)}

# Auth Routes
@app.post("/api/auth/register", response_model=Token)
async def register(user_data: UserCreate):
    try:
        # Check if exists
        existing = await db.users.find_one({"email": user_data.email})
        if existing:
            raise HTTPException(400, "Email already registered")
        
        # Create user
        user_id = str(uuid.uuid4())
        new_user = {
            "id": user_id,
            "email": user_data.email,
            "company_name": user_data.company_name,
            "hashed_password": hash_password(user_data.password),
            "is_active": True,
            "created_at": datetime.now(timezone.utc)
        }
        
        await db.users.insert_one(new_user)
        
        # Create default settings
        settings = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "company_name": user_data.company_name,
            "email": user_data.email,
            "logo_url": "",
            "gst_number": "",
            "pst_number": "",
            "hst_number": ""
        }
        await db.company_settings.insert_one(settings)
        
        user_obj = User(
            id=user_id,
            email=user_data.email,
            company_name=user_data.company_name,
            is_active=True
        )
        
        token = create_token(user_id)
        return Token(access_token=token, token_type="bearer", user=user_obj)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Register error: {e}")
        raise HTTPException(500, "Registration failed")

@app.post("/api/auth/login", response_model=Token)
async def login(credentials: UserLogin):
    try:
        user = await db.users.find_one({"email": credentials.email})
        if not user:
            raise HTTPException(401, "Incorrect email or password")
        
        print(f"DEBUG: User found: {user.get('email')}")
        print(f"DEBUG: User has password: {'hashed_password' in user}")
        print(f"DEBUG: User keys: {list(user.keys())}")
        
        if not verify_password(credentials.password, user["hashed_password"]):
            raise HTTPException(401, "Incorrect email or password")
        
        user_obj = User(
            id=user["id"],
            email=user["email"],
            company_name=user["company_name"],
            is_active=user.get("is_active", True)
        )
        
        token = create_token(user["id"])
        return Token(access_token=token, token_type="bearer", user=user_obj)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, "Login failed")

# Password Reset
@app.post("/api/auth/forgot-password")
async def forgot_password(request: dict):
    email = request.get("email")
    reset_token = secrets.token_urlsafe(32)
    
    # Update user with reset token
    await db.users.update_one(
        {"email": email},
        {"$set": {
            "reset_token": reset_token,
            "reset_token_expires": datetime.now(timezone.utc) + timedelta(hours=1)
        }}
    )
    
    return {"message": "Code généré", "reset_token": reset_token}

@app.post("/api/auth/reset-password")
async def reset_password(request: dict):
    token = request.get("token")
    new_password = request.get("new_password")
    
    # Find user with valid token
    user = await db.users.find_one({"reset_token": token})
    if not user:
        raise HTTPException(400, "Code invalide")
    
    # Update password
    await db.users.update_one(
        {"reset_token": token},
        {"$set": {
            "hashed_password": hash_password(new_password),
            "reset_token": None,
            "reset_token_expires": None
        }}
    )
    
    return {"message": "Mot de passe réinitialisé"}

# Client Routes
@app.get("/api/clients")
async def get_clients(current_user: User = Depends(get_current_user)):
    clients = []
    cursor = db.clients.find({"user_id": current_user.id})
    async for client in cursor:
        # Remove MongoDB _id field
        client.pop('_id', None)
        clients.append(Client(**client))
    return clients

@app.post("/api/clients")
async def create_client(client_data: dict, current_user: User = Depends(get_current_user)):
    client_id = str(uuid.uuid4())
    new_client = {
        "id": client_id,
        "user_id": current_user.id,
        **client_data,
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.clients.insert_one(new_client)
    new_client.pop('_id', None)
    return Client(**new_client)

@app.delete("/api/clients/{client_id}")
async def delete_client(client_id: str, current_user: User = Depends(get_current_user)):
    await db.clients.delete_one({"id": client_id, "user_id": current_user.id})
    return {"message": "Client deleted"}

# Settings Routes
@app.get("/api/settings/company")
async def get_settings(current_user: User = Depends(get_current_user)):
    settings = await db.company_settings.find_one({"user_id": current_user.id})
    
    if not settings:
        # Create default
        default = {
            "id": str(uuid.uuid4()),
            "user_id": current_user.id,
            "company_name": current_user.company_name,
            "email": current_user.email,
            "logo_url": "",
            "gst_number": "",
            "pst_number": "",
            "hst_number": ""
        }
        await db.company_settings.insert_one(default)
        default.pop('_id', None)
        return default
    
    settings.pop('_id', None)
    return settings

@app.put("/api/settings/company")
async def update_settings(settings_data: dict, current_user: User = Depends(get_current_user)):
    await db.company_settings.update_one(
        {"user_id": current_user.id},
        {"$set": settings_data}
    )
    
    settings = await db.company_settings.find_one({"user_id": current_user.id})
    settings.pop('_id', None)
    return settings

@app.post("/api/settings/company/upload-logo")
async def upload_logo(logo_data: dict, current_user: User = Depends(get_current_user)):
    await db.company_settings.update_one(
        {"user_id": current_user.id},
        {"$set": {"logo_url": logo_data.get("logo_url")}}
    )
    
    return {"message": "Logo saved", "logo_url": logo_data.get("logo_url")}

# Dashboard Stats
@app.get("/api/dashboard/stats")
async def get_stats(current_user: User = Depends(get_current_user)):
    clients_count = await db.clients.count_documents({"user_id": current_user.id})
    products_count = await db.products.count_documents({"user_id": current_user.id})
    
    return {
        "total_clients": clients_count,
        "total_invoices": 0,
        "total_quotes": 0,
        "total_products": products_count,
        "total_revenue": 0,
        "pending_invoices": 0
    }

# Product routes
@app.get("/api/products")
async def get_products(current_user: User = Depends(get_current_user)):
    products = []
    cursor = db.products.find({"user_id": current_user.id})
    async for product in cursor:
        product.pop('_id', None)
        products.append(product)
    return products

@app.post("/api/products")
async def create_product(product_data: dict, current_user: User = Depends(get_current_user)):
    product_id = str(uuid.uuid4())
    new_product = {
        "id": product_id,
        "user_id": current_user.id,
        **product_data,
        "is_active": True,
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.products.insert_one(new_product)
    new_product.pop('_id', None)
    return new_product

# Placeholder routes
@app.get("/api/invoices")
async def get_invoices(current_user: User = Depends(get_current_user)):
    return []

@app.get("/api/quotes") 
async def get_quotes(current_user: User = Depends(get_current_user)):
    return []

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup
@app.on_event("startup")
async def startup():
    global mongo_client, db
    
    print("🚀 FacturePro starting with MongoDB...")
    
    try:
        # Connect to MongoDB
        mongo_client = AsyncIOMotorClient(MONGO_URL)
        db = mongo_client[DB_NAME]
        
        # Test connection
        await db.command('ping')
        print("✅ MongoDB connected successfully")
        
        # Create indexes
        await db.users.create_index("email", unique=True)
        await db.users.create_index("id", unique=True)
        await db.clients.create_index([("user_id", 1)])
        await db.products.create_index([("user_id", 1)])
        await db.company_settings.create_index([("user_id", 1)])
        print("✅ Indexes created")
        
        # Create default user if needed
        existing = await db.users.find_one({"email": "gussdub@gmail.com"})
        
        if not existing:
            user_id = str(uuid.uuid4())
            new_user = {
                "id": user_id,
                "email": "gussdub@gmail.com", 
                "company_name": "ProFireManager",
                "hashed_password": hash_password("testpass123"),
                "is_active": True,
                "created_at": datetime.now(timezone.utc)
            }
            
            await db.users.insert_one(new_user)
            print("✅ Account gussdub@gmail.com created")
            
    except Exception as e:
        print(f"❌ Startup error: {e}")

@app.on_event("shutdown")
async def shutdown():
    if mongo_client:
        mongo_client.close()
        print("MongoDB connection closed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8001)))
