from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import pymongo
from pymongo import AsyncMongoClient
import os
import jwt
import bcrypt
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import uuid
import secrets
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configuration
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'facturepro')
JWT_SECRET = os.environ.get('JWT_SECRET', 'default-secret')

print(f"🔧 Connecting to MongoDB: {MONGO_URL}")

# MongoDB connection with NEW PyMongo Async
client = AsyncMongoClient(MONGO_URL)
db = client[DB_NAME]

# FastAPI app
app = FastAPI(title="FacturePro API", version="2.0.0")

# Security
security = HTTPBearer()

# Models
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

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
        
        user = await db.users.find_one({"id": user_id})
        if not user:
            raise HTTPException(401, "User not found")
        return User(**user)
    except Exception as e:
        print(f"Auth error: {e}")
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
        result = await client.admin.command('ping')
        return {"status": "healthy", "database": "connected", "ping": result}
    except Exception as e:
        print(f"MongoDB connection error: {e}")
        return {"status": "healthy", "database": "error", "error": str(e)}

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
        trial_end = datetime.now(timezone.utc) + timedelta(days=14)
        
        new_user = User(
            id=user_id,
            email=user_data.email,
            company_name=user_data.company_name,
            is_active=True,
            subscription_status="trial",
            trial_end_date=trial_end
        )
        
        # Insert user
        await db.users.insert_one(new_user.model_dump())
        
        # Insert password separately
        await db.user_passwords.insert_one({
            "user_id": user_id,
            "hashed_password": hash_password(user_data.password)
        })
        
        # Create default settings
        settings = CompanySettings(
            id=str(uuid.uuid4()),
            user_id=user_id,
            company_name=user_data.company_name,
            email=user_data.email
        )
        await db.company_settings.insert_one(settings.model_dump())
        
        token = create_token(user_id)
        return Token(access_token=token, token_type="bearer", user=new_user)
        
    except Exception as e:
        print(f"Register error: {e}")
        raise HTTPException(500, f"Registration failed: {str(e)}")

@app.post("/api/auth/login", response_model=Token)
async def login(credentials: UserLogin):
    try:
        user = await db.users.find_one({"email": credentials.email})
        if not user:
            raise HTTPException(401, "Incorrect email or password")
        
        # Check password
        password_doc = await db.user_passwords.find_one({"user_id": user["id"]})
        if not password_doc or not verify_password(credentials.password, password_doc["hashed_password"]):
            raise HTTPException(401, "Incorrect email or password")
        
        token = create_token(user["id"])
        return Token(access_token=token, token_type="bearer", user=User(**user))
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(500, f"Login failed: {str(e)}")

# Password Reset
reset_tokens = {}

@app.post("/api/auth/forgot-password")
async def forgot_password(request: dict):
    try:
        email = request.get("email")
        user = await db.users.find_one({"email": email})
        
        if not user:
            return {"message": "Si cette adresse email existe, un code de récupération a été généré"}
        
        reset_token = secrets.token_urlsafe(32)
        reset_tokens[reset_token] = {
            "user_id": user["id"],
            "email": user["email"],
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)
        }
        
        return {"message": "Code généré", "reset_token": reset_token}
    except Exception as e:
        print(f"Forgot password error: {e}")
        raise HTTPException(500, "Error generating reset code")

@app.post("/api/auth/reset-password")
async def reset_password(request: dict):
    try:
        token = request.get("token")
        new_password = request.get("new_password")
        
        token_data = reset_tokens.get(token)
        if not token_data or datetime.now(timezone.utc) > token_data["expires_at"]:
            raise HTTPException(400, "Code invalide ou expiré")
        
        # Update password
        await db.user_passwords.update_one(
            {"user_id": token_data["user_id"]},
            {"$set": {"hashed_password": hash_password(new_password)}}
        )
        
        del reset_tokens[token]
        return {"message": "Mot de passe réinitialisé"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Reset password error: {e}")
        raise HTTPException(500, "Error resetting password")

# Client Routes
@app.get("/api/clients")
async def get_clients(current_user: User = Depends(get_current_user_with_access)):
    try:
        cursor = db.clients.find({"user_id": current_user.id})
        clients = []
        async for client in cursor:
            clients.append(Client(**client))
        return clients
    except Exception as e:
        print(f"Get clients error: {e}")
        raise HTTPException(500, "Error fetching clients")

@app.post("/api/clients")
async def create_client(client_data: dict, current_user: User = Depends(get_current_user_with_access)):
    try:
        client_id = str(uuid.uuid4())
        new_client = Client(
            id=client_id,
            user_id=current_user.id,
            **client_data
        )
        
        await db.clients.insert_one(new_client.model_dump())
        return new_client
    except Exception as e:
        print(f"Create client error: {e}")
        raise HTTPException(500, "Error creating client")

@app.put("/api/clients/{client_id}")
async def update_client(client_id: str, client_data: dict, current_user: User = Depends(get_current_user_with_access)):
    try:
        result = await db.clients.update_one(
            {"id": client_id, "user_id": current_user.id},
            {"$set": client_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(404, "Client not found")
        
        updated_client = await db.clients.find_one({"id": client_id})
        return Client(**updated_client)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Update client error: {e}")
        raise HTTPException(500, "Error updating client")

@app.delete("/api/clients/{client_id}")
async def delete_client(client_id: str, current_user: User = Depends(get_current_user_with_access)):
    try:
        result = await db.clients.delete_one({"id": client_id, "user_id": current_user.id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Client not found")
        return {"message": "Client deleted"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Delete client error: {e}")
        raise HTTPException(500, "Error deleting client")

# Product Routes
@app.get("/api/products")
async def get_products(current_user: User = Depends(get_current_user_with_access)):
    try:
        cursor = db.products.find({"user_id": current_user.id, "is_active": True})
        products = []
        async for product in cursor:
            # Remove MongoDB _id field
            if "_id" in product:
                del product["_id"]
            products.append(product)
        return products
    except Exception as e:
        print(f"Get products error: {e}")
        return []

@app.post("/api/products")
async def create_product(product_data: dict, current_user: User = Depends(get_current_user_with_access)):
    try:
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
        
        await db.products.insert_one(new_product)
        return new_product
    except Exception as e:
        print(f"Create product error: {e}")
        raise HTTPException(500, "Error creating product")

# Settings Routes
@app.get("/api/settings/company")
async def get_settings(current_user: User = Depends(get_current_user_with_access)):
    try:
        settings = await db.company_settings.find_one({"user_id": current_user.id})
        if not settings:
            # Create default
            default_settings = CompanySettings(
                id=str(uuid.uuid4()),
                user_id=current_user.id,
                company_name=current_user.company_name,
                email=current_user.email
            )
            await db.company_settings.insert_one(default_settings.model_dump())
            return default_settings
        return CompanySettings(**settings)
    except Exception as e:
        print(f"Get settings error: {e}")
        # Return default if error
        return {
            "id": str(uuid.uuid4()),
            "user_id": current_user.id,
            "company_name": current_user.company_name,
            "email": current_user.email,
            "logo_url": "",
            "gst_number": "",
            "pst_number": "",
            "hst_number": ""
        }

@app.put("/api/settings/company")
async def update_settings(settings_data: dict, current_user: User = Depends(get_current_user_with_access)):
    try:
        result = await db.company_settings.update_one(
            {"user_id": current_user.id},
            {"$set": settings_data},
            upsert=True
        )
        
        updated_settings = await db.company_settings.find_one({"user_id": current_user.id})
        return updated_settings
    except Exception as e:
        print(f"Update settings error: {e}")
        raise HTTPException(500, "Error updating settings")

@app.post("/api/settings/company/upload-logo")
async def upload_logo(logo_data: dict, current_user: User = Depends(get_current_user_with_access)):
    try:
        await db.company_settings.update_one(
            {"user_id": current_user.id},
            {"$set": {"logo_url": logo_data.get("logo_url")}},
            upsert=True
        )
        return {"message": "Logo saved", "logo_url": logo_data.get("logo_url")}
    except Exception as e:
        print(f"Upload logo error: {e}")
        raise HTTPException(500, "Error saving logo")

# Dashboard Stats
@app.get("/api/dashboard/stats")
async def get_stats(current_user: User = Depends(get_current_user_with_access)):
    try:
        total_clients = await db.clients.count_documents({"user_id": current_user.id})
        total_invoices = await db.invoices.count_documents({"user_id": current_user.id})
        total_quotes = await db.quotes.count_documents({"user_id": current_user.id})
        total_products = await db.products.count_documents({"user_id": current_user.id, "is_active": True})
        
        return {
            "total_clients": total_clients,
            "total_invoices": total_invoices,
            "total_quotes": total_quotes,
            "total_products": total_products,
            "total_revenue": 0,
            "pending_invoices": 0
        }
    except Exception as e:
        print(f"Dashboard stats error: {e}")
        return {
            "total_clients": 0,
            "total_invoices": 0,
            "total_quotes": 0,
            "total_products": 0,
            "total_revenue": 0,
            "pending_invoices": 0
        }

# Invoice Routes
@app.get("/api/invoices")
async def get_invoices(current_user: User = Depends(get_current_user_with_access)):
    try:
        cursor = db.invoices.find({"user_id": current_user.id})
        invoices = []
        async for invoice in cursor:
            invoices.append(invoice)
        return invoices
    except Exception as e:
        print(f"Get invoices error: {e}")
        return []

@app.post("/api/invoices")
async def create_invoice(invoice_data: dict, current_user: User = Depends(get_current_user_with_access)):
    try:
        invoice_id = str(uuid.uuid4())
        
        # Calculate totals
        items = invoice_data.get("items", [])
        subtotal = sum(item["quantity"] * item["unit_price"] for item in items)
        
        # Tax calculation
        province = invoice_data.get("province", "QC")
        if province == "QC":
            gst = subtotal * 0.05
            pst = subtotal * 0.09975
            hst = 0
        elif province == "ON":
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
        invoice_count = await db.invoices.count_documents({"user_id": current_user.id})
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
            "province": province,
            "status": "draft",
            "notes": invoice_data.get("notes", ""),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.invoices.insert_one(new_invoice)
        return new_invoice
        
    except Exception as e:
        print(f"Create invoice error: {e}")
        raise HTTPException(500, "Error creating invoice")

# Quote Routes
@app.get("/api/quotes")
async def get_quotes(current_user: User = Depends(get_current_user_with_access)):
    try:
        cursor = db.quotes.find({"user_id": current_user.id})
        quotes = []
        async for quote in cursor:
            quotes.append(quote)
        return quotes
    except Exception as e:
        print(f"Get quotes error: {e}")
        return []

@app.post("/api/quotes")
async def create_quote(quote_data: dict, current_user: User = Depends(get_current_user_with_access)):
    try:
        quote_id = str(uuid.uuid4())
        
        quote_count = await db.quotes.count_documents({"user_id": current_user.id})
        quote_number = f"QUO-{quote_count + 1:04d}"
        
        new_quote = {
            "id": quote_id,
            "user_id": current_user.id,
            "client_id": quote_data["client_id"],
            "quote_number": quote_number,
            "issue_date": datetime.now(timezone.utc).isoformat(),
            "valid_until": quote_data["valid_until"],
            "items": quote_data.get("items", []),
            "total": 0,
            "status": "pending",
            "notes": quote_data.get("notes", ""),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.quotes.insert_one(new_quote)
        return new_quote
        
    except Exception as e:
        print(f"Create quote error: {e}")
        raise HTTPException(500, "Error creating quote")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup - Create gussdub account
@app.on_event("startup")
async def create_accounts():
    try:
        print("🔧 Initializing FacturePro...")
        
        # Test MongoDB connection
        await client.admin.command('ping')
        print("✅ MongoDB Atlas connected!")
        
        # Create gussdub account if doesn't exist
        existing_user = await db.users.find_one({"email": "gussdub@gmail.com"})
        
        if not existing_user:
            print("🔧 Creating gussdub@gmail.com account...")
            
            user_id = str(uuid.uuid4())
            trial_end = datetime.now(timezone.utc) + timedelta(days=3650)  # 10 years
            
            new_user = {
                "id": user_id,
                "email": "gussdub@gmail.com",
                "company_name": "ProFireManager",
                "is_active": True,
                "subscription_status": "trial",
                "trial_end_date": trial_end,
                "created_at": datetime.now(timezone.utc)
            }
            
            await db.users.insert_one(new_user)
            await db.user_passwords.insert_one({
                "user_id": user_id,
                "hashed_password": hash_password("testpass123")
            })
            
            # Create settings
            await db.company_settings.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "company_name": "ProFireManager",
                "email": "gussdub@gmail.com",
                "gst_number": "123456789",
                "pst_number": "1234567890",
                "logo_url": "",
                "primary_color": "#3B82F6",
                "secondary_color": "#1F2937"
            })
            
            # Create sample client
            await db.clients.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "name": "Client Test",
                "email": "test@client.com",
                "phone": "514-123-4567",
                "address": "123 Rue Test",
                "city": "Montréal",
                "postal_code": "H1A 1A1",
                "country": "Canada"
            })
            
            # Create sample product
            await db.products.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "name": "Consultation",
                "description": "Consultation professionnelle",
                "unit_price": 100.0,
                "unit": "heure",
                "category": "Services",
                "is_active": True
            })
            
            print("✅ Account gussdub@gmail.com created with sample data")
        else:
            print("✅ Account gussdub@gmail.com already exists")
            
    except Exception as e:
        print(f"❌ Startup error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))