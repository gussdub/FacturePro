from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
import jwt
import bcrypt
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from typing import Optional, List
import uuid
import secrets
import json
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configuration
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mnstslbjzolgjxexhpfd.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_ANON_KEY', '')
JWT_SECRET = os.environ.get('JWT_SECRET', 'default-secret')

# FastAPI app
app = FastAPI(title="FacturePro API", version="2.0.0")
security = HTTPBearer()

# HTTP client for Supabase REST API
http_client = httpx.AsyncClient()

# Models (same as before)
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

# Supabase API helpers
async def supabase_query(table: str, method: str = "GET", data: dict = None, filters: dict = None):
    """Query Supabase via REST API"""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    # Add filters
    if filters:
        params = {}
        for key, value in filters.items():
            params[key] = f"eq.{value}"
        url += "?" + "&".join([f"{k}={v}" for k, v in params.items()])
    
    try:
        if method == "GET":
            response = await http_client.get(url, headers=headers)
        elif method == "POST":
            response = await http_client.post(url, headers=headers, json=data)
        elif method == "PUT":
            response = await http_client.patch(url, headers=headers, json=data)
        elif method == "DELETE":
            response = await http_client.delete(url, headers=headers)
        
        if response.status_code < 400:
            return response.json() if response.text else []
        else:
            print(f"Supabase error: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"HTTP error: {e}")
        return []

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
        
        users = await supabase_query("users", filters={"id": user_id})
        if not users:
            raise HTTPException(401, "User not found")
        
        return User(**users[0])
    except Exception as e:
        print(f"Auth error: {e}")
        raise HTTPException(401, "Invalid token")

# Routes
@app.get("/")
async def root():
    return {"message": "FacturePro API v2.0", "status": "running", "database": "Supabase REST API"}

@app.get("/api/health")
async def health():
    try:
        # Test Supabase connection
        users = await supabase_query("users")
        return {"status": "healthy", "database": "connected", "users_count": len(users)}
    except Exception as e:
        return {"status": "unhealthy", "database": "error", "error": str(e)}

# Auth Routes
@app.post("/api/auth/register", response_model=Token)
async def register(user_data: UserCreate):
    try:
        # Check if exists
        existing = await supabase_query("users", filters={"email": user_data.email})
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
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        result = await supabase_query("users", "POST", new_user)
        
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
        await supabase_query("company_settings", "POST", settings)
        
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
        users = await supabase_query("users", filters={"email": credentials.email})
        if not users:
            raise HTTPException(401, "Incorrect email or password")
        
        user = users[0]
        if not verify_password(credentials.password, user["hashed_password"]):
            raise HTTPException(401, "Incorrect email or password")
        
        user_obj = User(
            id=user["id"],
            email=user["email"],
            company_name=user["company_name"],
            is_active=user["is_active"]
        )
        
        token = create_token(user["id"])
        return Token(access_token=token, token_type="bearer", user=user_obj)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(500, "Login failed")

# Password Reset
@app.post("/api/auth/forgot-password")
async def forgot_password(request: dict):
    email = request.get("email")
    reset_token = secrets.token_urlsafe(32)
    
    # Update user with reset token
    await supabase_query("users", "PUT", {
        "reset_token": reset_token,
        "reset_token_expires": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    }, filters={"email": email})
    
    return {"message": "Code généré", "reset_token": reset_token}

@app.post("/api/auth/reset-password")
async def reset_password(request: dict):
    token = request.get("token")
    new_password = request.get("new_password")
    
    # Find user with valid token
    users = await supabase_query("users", filters={"reset_token": token})
    if not users:
        raise HTTPException(400, "Code invalide")
    
    # Update password
    await supabase_query("users", "PUT", {
        "hashed_password": hash_password(new_password),
        "reset_token": None,
        "reset_token_expires": None
    }, filters={"reset_token": token})
    
    return {"message": "Mot de passe réinitialisé"}

# Client Routes
@app.get("/api/clients")
async def get_clients(current_user: User = Depends(get_current_user)):
    clients = await supabase_query("clients", filters={"user_id": current_user.id})
    return [Client(**client) for client in clients]

@app.post("/api/clients")
async def create_client(client_data: dict, current_user: User = Depends(get_current_user)):
    client_id = str(uuid.uuid4())
    new_client = {
        "id": client_id,
        "user_id": current_user.id,
        **client_data,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    result = await supabase_query("clients", "POST", new_client)
    return Client(**new_client)

@app.delete("/api/clients/{client_id}")
async def delete_client(client_id: str, current_user: User = Depends(get_current_user)):
    await supabase_query("clients", "DELETE", filters={"id": client_id, "user_id": current_user.id})
    return {"message": "Client deleted"}

# Settings Routes
@app.get("/api/settings/company")
async def get_settings(current_user: User = Depends(get_current_user)):
    settings = await supabase_query("company_settings", filters={"user_id": current_user.id})
    
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
        await supabase_query("company_settings", "POST", default)
        return default
    
    return settings[0]

@app.put("/api/settings/company")
async def update_settings(settings_data: dict, current_user: User = Depends(get_current_user)):
    await supabase_query("company_settings", "PUT", settings_data, filters={"user_id": current_user.id})
    
    settings = await supabase_query("company_settings", filters={"user_id": current_user.id})
    return settings[0] if settings else {}

@app.post("/api/settings/company/upload-logo")
async def upload_logo(logo_data: dict, current_user: User = Depends(get_current_user)):
    await supabase_query("company_settings", "PUT", {
        "logo_url": logo_data.get("logo_url")
    }, filters={"user_id": current_user.id})
    
    return {"message": "Logo saved", "logo_url": logo_data.get("logo_url")}

# Dashboard Stats
@app.get("/api/dashboard/stats")
async def get_stats(current_user: User = Depends(get_current_user)):
    clients = await supabase_query("clients", filters={"user_id": current_user.id})
    products = await supabase_query("products", filters={"user_id": current_user.id})
    
    return {
        "total_clients": len(clients),
        "total_invoices": 0,
        "total_quotes": 0,
        "total_products": len(products),
        "total_revenue": 0,
        "pending_invoices": 0
    }

# Product routes (basic)
@app.get("/api/products")
async def get_products(current_user: User = Depends(get_current_user)):
    products = await supabase_query("products", filters={"user_id": current_user.id})
    return products

@app.post("/api/products")
async def create_product(product_data: dict, current_user: User = Depends(get_current_user)):
    product_id = str(uuid.uuid4())
    new_product = {
        "id": product_id,
        "user_id": current_user.id,
        **product_data,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await supabase_query("products", "POST", new_product)
    return new_product

# Placeholder routes (will work with Supabase)
@app.get("/api/invoices")
async def get_invoices(current_user: User = Depends(get_current_user)):
    return []  # Will implement later

@app.get("/api/quotes") 
async def get_quotes(current_user: User = Depends(get_current_user)):
    return []  # Will implement later

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
    print("🚀 FacturePro starting with Supabase REST API...")
    
    try:
        # Test Supabase connection
        response = await http_client.get(f"{SUPABASE_URL}/rest/v1/users", headers={
            "apikey": SUPABASE_KEY
        })
        
        if response.status_code == 200:
            print("✅ Supabase REST API connected")
            
            # Create gussdub account if needed
            existing = await supabase_query("users", filters={"email": "gussdub@gmail.com"})
            
            if not existing:
                user_id = str(uuid.uuid4())
                new_user = {
                    "id": user_id,
                    "email": "gussdub@gmail.com", 
                    "company_name": "ProFireManager",
                    "hashed_password": hash_password("testpass123"),
                    "is_active": True,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                
                await supabase_query("users", "POST", new_user)
                print("✅ Account gussdub@gmail.com created")
        else:
            print(f"❌ Supabase connection failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Startup error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))