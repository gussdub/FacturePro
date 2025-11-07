from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import pymongo
import os
import jwt
import bcrypt
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import uuid
from enum import Enum
import secrets
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# Load environment
load_dotenv()

# FastAPI app
app = FastAPI(title="FacturePro API", version="2.0.0")

# Configuration
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'facturepro')
JWT_SECRET = os.environ.get('JWT_SECRET', 'default-secret')

# MongoDB connection (synchrone)
mongo_client = pymongo.MongoClient(MONGO_URL)
db = mongo_client[DB_NAME]

# Thread executor for blocking operations
executor = ThreadPoolExecutor(max_workers=10)

# Security
security = HTTPBearer()

# Models (same as before)
class User(BaseModel):
    id: str
    email: str
    company_name: str
    is_active: bool = True
    subscription_status: str = "trial"
    trial_end_date: Optional[datetime] = None

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

class CompanySettings(BaseModel):
    id: str
    user_id: str
    company_name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: str = "#3B82F6"
    secondary_color: str = "#1F2937"
    default_due_days: int = 30
    next_invoice_number: int = 1
    next_quote_number: int = 1
    gst_number: Optional[str] = None
    pst_number: Optional[str] = None
    hst_number: Optional[str] = None

# Utility functions
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(hours=24)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

# Database helper functions
def run_in_thread(func):
    """Run synchronous function in thread to avoid blocking"""
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(executor, func, *args, **kwargs)
    return wrapper

@run_in_thread
def find_user_by_email(email: str):
    return db.users.find_one({"email": email})

@run_in_thread
def find_user_by_id(user_id: str):
    return db.users.find_one({"id": user_id})

@run_in_thread
def find_user_password(user_id: str):
    return db.user_passwords.find_one({"user_id": user_id})

@run_in_thread
def insert_user(user_data: dict):
    return db.users.insert_one(user_data)

@run_in_thread
def insert_user_password(password_data: dict):
    return db.user_passwords.insert_one(password_data)

@run_in_thread
def insert_company_settings(settings_data: dict):
    return db.company_settings.insert_one(settings_data)

@run_in_thread
def get_clients_for_user(user_id: str):
    return list(db.clients.find({"user_id": user_id}))

@run_in_thread
def insert_client(client_data: dict):
    return db.clients.insert_one(client_data)

@run_in_thread
def update_client_by_id(client_id: str, user_id: str, update_data: dict):
    return db.clients.update_one(
        {"id": client_id, "user_id": user_id},
        {"$set": update_data}
    )

@run_in_thread
def delete_client_by_id(client_id: str, user_id: str):
    return db.clients.delete_one({"id": client_id, "user_id": user_id})

@run_in_thread
def get_company_settings(user_id: str):
    return db.company_settings.find_one({"user_id": user_id})

@run_in_thread
def update_company_settings(user_id: str, settings_data: dict):
    return db.company_settings.update_one(
        {"user_id": user_id},
        {"$set": settings_data},
        upsert=True
    )

# Auth functions
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
        
        user = await find_user_by_id(user_id)
        if not user:
            raise HTTPException(401, "User not found")
        return User(**user)
    except:
        raise HTTPException(401, "Invalid token")

async def get_current_user_with_access(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = await get_current_user(credentials)
    
    # Exempt users
    EXEMPT_USERS = ["gussdub@gmail.com"]
    if user.email in EXEMPT_USERS:
        return user
    
    return user

# Routes
@app.get("/")
async def root():
    return {"message": "FacturePro API v2.0", "status": "running", "database": "MongoDB Atlas"}

@app.get("/api/health")
async def health():
    try:
        # Test MongoDB connection
        info = await asyncio.get_event_loop().run_in_executor(
            executor, lambda: mongo_client.server_info()
        )
        return {"status": "healthy", "database": "connected", "mongodb_version": info.get("version")}
    except:
        return {"status": "healthy", "database": "error"}

# Auth Routes
@app.post("/api/auth/register", response_model=Token)
async def register(user_data: UserCreate):
    # Check if exists
    existing = await find_user_by_email(user_data.email)
    if existing:
        raise HTTPException(400, "Email already registered")
    
    # Create user
    user_id = str(uuid.uuid4())
    trial_end = datetime.now(timezone.utc) + timedelta(days=14)
    
    new_user = User(
        id=user_id,
        email=user_data.email,
        company_name=user_data.company_name,
        is_active=True,
        subscription_status="trial",
        trial_end_date=trial_end
    )
    
    # Save to MongoDB
    await insert_user(new_user.dict())
    await insert_user_password({
        "user_id": user_id,
        "hashed_password": hash_password(user_data.password)
    })
    
    # Create settings
    settings = CompanySettings(
        id=str(uuid.uuid4()),
        user_id=user_id,
        company_name=user_data.company_name,
        email=user_data.email
    )
    await insert_company_settings(settings.dict())
    
    token = create_token(user_id)
    return Token(access_token=token, token_type="bearer", user=new_user)

@app.post("/api/auth/login", response_model=Token)
async def login(credentials: UserLogin):
    user = await find_user_by_email(credentials.email)
    if not user:
        raise HTTPException(401, "Incorrect email or password")
    
    password_doc = await find_user_password(user["id"])
    if not password_doc or not verify_password(credentials.password, password_doc["hashed_password"]):
        raise HTTPException(401, "Incorrect email or password")
    
    token = create_token(user["id"])
    return Token(access_token=token, token_type="bearer", user=User(**user))

# Password Reset (in-memory for simplicity)
reset_tokens = {}

@app.post("/api/auth/forgot-password")
async def forgot_password(request: dict):
    email = request.get("email")
    user = await find_user_by_email(email)
    
    if not user:
        return {"message": "Si cette adresse email existe, un code de récupération a été généré"}
    
    reset_token = secrets.token_urlsafe(32)
    reset_tokens[reset_token] = {
        "user_id": user["id"],
        "email": user["email"],
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    
    return {"message": "Code de récupération généré", "reset_token": reset_token}

@app.post("/api/auth/reset-password")
async def reset_password(request: dict):
    token = request.get("token")
    new_password = request.get("new_password")
    
    token_data = reset_tokens.get(token)
    if not token_data:
        raise HTTPException(400, "Code invalide")
    
    if datetime.now(timezone.utc) > token_data["expires_at"]:
        del reset_tokens[token]
        raise HTTPException(400, "Code expiré")
    
    # Update password in MongoDB
    await asyncio.get_event_loop().run_in_executor(
        executor,
        lambda: db.user_passwords.update_one(
            {"user_id": token_data["user_id"]},
            {"$set": {"hashed_password": hash_password(new_password)}}
        )
    )
    
    del reset_tokens[token]
    return {"message": "Mot de passe réinitialisé avec succès"}

# Client Routes
@app.get("/api/clients")
async def get_clients(current_user: User = Depends(get_current_user_with_access)):
    clients = await get_clients_for_user(current_user.id)
    return [Client(**client) for client in clients]

@app.post("/api/clients")
async def create_client(client_data: dict, current_user: User = Depends(get_current_user_with_access)):
    client_id = str(uuid.uuid4())
    new_client = Client(
        id=client_id,
        user_id=current_user.id,
        **client_data
    )
    await insert_client(new_client.dict())
    return new_client

@app.put("/api/clients/{client_id}")
async def update_client(client_id: str, client_data: dict, current_user: User = Depends(get_current_user_with_access)):
    result = await update_client_by_id(client_id, current_user.id, client_data)
    if result.modified_count == 0:
        raise HTTPException(404, "Client not found")
    
    # Get updated client
    client = await asyncio.get_event_loop().run_in_executor(
        executor, lambda: db.clients.find_one({"id": client_id})
    )
    return Client(**client)

@app.delete("/api/clients/{client_id}")
async def delete_client(client_id: str, current_user: User = Depends(get_current_user_with_access)):
    result = await delete_client_by_id(client_id, current_user.id)
    if result.deleted_count == 0:
        raise HTTPException(404, "Client not found")
    return {"message": "Client deleted"}

# Settings Routes
@app.get("/api/settings/company")
async def get_settings(current_user: User = Depends(get_current_user_with_access)):
    settings = await get_company_settings(current_user.id)
    if not settings:
        # Create default settings
        default_settings = CompanySettings(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            company_name=current_user.company_name,
            email=current_user.email
        )
        await insert_company_settings(default_settings.dict())
        return default_settings
    return CompanySettings(**settings)

@app.put("/api/settings/company")
async def update_settings(settings_data: dict, current_user: User = Depends(get_current_user_with_access)):
    await update_company_settings(current_user.id, settings_data)
    updated_settings = await get_company_settings(current_user.id)
    return CompanySettings(**updated_settings)

@app.post("/api/settings/company/upload-logo")
async def upload_logo(logo_data: dict, current_user: User = Depends(get_current_user_with_access)):
    await update_company_settings(current_user.id, {"logo_url": logo_data.get("logo_url")})
    return {"message": "Logo saved", "logo_url": logo_data.get("logo_url")}

# Dashboard Stats (simplified)
@app.get("/api/dashboard/stats")
async def get_stats(current_user: User = Depends(get_current_user_with_access)):
    # Count clients
    clients_count = await asyncio.get_event_loop().run_in_executor(
        executor, lambda: db.clients.count_documents({"user_id": current_user.id})
    )
    
    return {
        "total_clients": clients_count,
        "total_invoices": 0,  # Will implement later
        "total_quotes": 0,    # Will implement later
        "total_products": 0,  # Will implement later
        "total_revenue": 0,   # Will implement later
        "pending_invoices": 0
    }

# Product routes (basic)
@app.get("/api/products")
async def get_products(current_user: User = Depends(get_current_user_with_access)):
    products = await asyncio.get_event_loop().run_in_executor(
        executor, lambda: list(db.products.find({"user_id": current_user.id, "is_active": True}))
    )
    return products

@app.post("/api/products")
async def create_product(product_data: dict, current_user: User = Depends(get_current_user_with_access)):
    product_id = str(uuid.uuid4())
    new_product = {
        "id": product_id,
        "user_id": current_user.id,
        "name": product_data["name"],
        "description": product_data.get("description", ""),
        "unit_price": float(product_data["unit_price"]),
        "unit": product_data.get("unit", "unité"),
        "category": product_data.get("category", ""),
        "is_active": True,
        "created_at": datetime.now(timezone.utc)
    }
    
    await asyncio.get_event_loop().run_in_executor(
        executor, lambda: db.products.insert_one(new_product)
    )
    return new_product

# Invoice routes (basic)
@app.get("/api/invoices")
async def get_invoices(current_user: User = Depends(get_current_user_with_access)):
    invoices = await asyncio.get_event_loop().run_in_executor(
        executor, lambda: list(db.invoices.find({"user_id": current_user.id}))
    )
    return invoices

@app.post("/api/invoices")
async def create_invoice(invoice_data: dict, current_user: User = Depends(get_current_user_with_access)):
    invoice_id = str(uuid.uuid4())
    
    # Calculate totals
    items = invoice_data.get("items", [])
    subtotal = sum(item["quantity"] * item["unit_price"] for item in items)
    
    # Simple tax calculation
    if invoice_data.get("province") == "QC":
        gst = subtotal * 0.05
        pst = subtotal * 0.09975
        hst = 0
    elif invoice_data.get("province") == "ON":
        gst = 0
        pst = 0
        hst = subtotal * 0.13
    else:
        gst = subtotal * 0.05
        pst = 0
        hst = 0
    
    total_tax = gst + pst + hst
    total = subtotal + total_tax
    
    # Generate invoice number
    invoice_count = await asyncio.get_event_loop().run_in_executor(
        executor, lambda: db.invoices.count_documents({"user_id": current_user.id})
    )
    invoice_number = f"INV-{invoice_count + 1:04d}"
    
    new_invoice = {
        "id": invoice_id,
        "user_id": current_user.id,
        "client_id": invoice_data["client_id"],
        "invoice_number": invoice_number,
        "issue_date": datetime.now(timezone.utc).isoformat(),
        "due_date": invoice_data["due_date"],
        "items": items,
        "subtotal": round(subtotal, 2),
        "gst_amount": round(gst, 2),
        "pst_amount": round(pst, 2),
        "hst_amount": round(hst, 2),
        "total_tax": round(total_tax, 2),
        "total": round(total, 2),
        "province": invoice_data.get("province", "QC"),
        "status": "draft",
        "notes": invoice_data.get("notes", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await asyncio.get_event_loop().run_in_executor(
        executor, lambda: db.invoices.insert_one(new_invoice)
    )
    return new_invoice

# Quote routes (basic)
@app.get("/api/quotes")
async def get_quotes(current_user: User = Depends(get_current_user_with_access)):
    quotes = await asyncio.get_event_loop().run_in_executor(
        executor, lambda: list(db.quotes.find({"user_id": current_user.id}))
    )
    return quotes

@app.post("/api/quotes")
async def create_quote(quote_data: dict, current_user: User = Depends(get_current_user_with_access)):
    quote_id = str(uuid.uuid4())
    
    # Simple quote creation
    quote_count = await asyncio.get_event_loop().run_in_executor(
        executor, lambda: db.quotes.count_documents({"user_id": current_user.id})
    )
    quote_number = f"QUO-{quote_count + 1:04d}"
    
    new_quote = {
        "id": quote_id,
        "user_id": current_user.id,
        "client_id": quote_data["client_id"],
        "quote_number": quote_number,
        "issue_date": datetime.now(timezone.utc).isoformat(),
        "valid_until": quote_data["valid_until"],
        "items": quote_data.get("items", []),
        "total": 0,  # Will calculate later
        "status": "pending",
        "notes": quote_data.get("notes", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await asyncio.get_event_loop().run_in_executor(
        executor, lambda: db.quotes.insert_one(new_quote)
    )
    return new_quote

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))