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
import json
from pathlib import Path

# FastAPI app
app = FastAPI(title="FacturePro API", version="2.0.0")

# Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', 'facturepro-ultra-secure-jwt-2024')
DATA_DIR = Path("/tmp/facturepro_data")
DATA_DIR.mkdir(exist_ok=True)

# Security
security = HTTPBearer()

# Simple file-based storage
def load_data(filename):
    file_path = DATA_DIR / f"{filename}.json"
    if file_path.exists():
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_data(filename, data):
    file_path = DATA_DIR / f"{filename}.json"
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, default=str, indent=2)
    except Exception as e:
        print(f"Error saving {filename}: {e}")

# Load initial data
users_db = load_data("users")
clients_db = load_data("clients")
settings_db = load_data("settings")
products_db = load_data("products")
invoices_db = load_data("invoices")
quotes_db = load_data("quotes")
reset_tokens = {}

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

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
        
        if user_id in users_db:
            return User(**users_db[user_id])
        else:
            raise HTTPException(401, "User not found")
    except:
        raise HTTPException(401, "Invalid token")

# Routes
@app.get("/")
async def root():
    return {"message": "FacturePro API v2.0", "status": "running", "storage": "file-based"}

@app.get("/api/health")
async def health():
    return {
        "status": "healthy", 
        "users": len([u for u in users_db.values() if isinstance(u, dict)]),
        "clients": len([c for c in clients_db.values() if isinstance(c, dict)]),
        "storage": "persistent files"
    }

# Auth Routes
@app.post("/api/auth/register", response_model=Token)
async def register(user_data: UserCreate):
    # Check if exists
    for user in users_db.values():
        if isinstance(user, dict) and user.get("email") == user_data.email:
            raise HTTPException(400, "Email already registered")
    
    # Create user
    user_id = str(uuid.uuid4())
    new_user = {
        "id": user_id,
        "email": user_data.email,
        "company_name": user_data.company_name,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    users_db[user_id] = new_user
    users_db[f"{user_id}_password"] = hash_password(user_data.password)
    
    # Save to file
    save_data("users", users_db)
    
    # Create default settings
    settings_db[user_id] = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "company_name": user_data.company_name,
        "email": user_data.email,
        "gst_number": "",
        "pst_number": "",
        "hst_number": "",
        "logo_url": ""
    }
    save_data("settings", settings_db)
    
    token = create_token(user_id)
    return Token(access_token=token, token_type="bearer", user=User(**new_user))

@app.post("/api/auth/login", response_model=Token)
async def login(credentials: UserLogin):
    user = None
    user_id = None
    
    for uid, u in users_db.items():
        if isinstance(u, dict) and u.get("email") == credentials.email:
            user = u
            user_id = uid
            break
    
    if not user:
        raise HTTPException(401, "Incorrect email or password")
    
    stored_password = users_db.get(f"{user_id}_password")
    if not stored_password or not verify_password(credentials.password, stored_password):
        raise HTTPException(401, "Incorrect email or password")
    
    token = create_token(user_id)
    return Token(access_token=token, token_type="bearer", user=User(**user))

# Password Reset
@app.post("/api/auth/forgot-password")
async def forgot_password(request: dict):
    email = request.get("email")
    reset_token = secrets.token_urlsafe(32)
    reset_tokens[reset_token] = {
        "email": email,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    return {"message": "Code généré", "reset_token": reset_token}

@app.post("/api/auth/reset-password")
async def reset_password(request: dict):
    token = request.get("token")
    new_password = request.get("new_password")
    
    token_data = reset_tokens.get(token)
    if not token_data or datetime.now(timezone.utc) > token_data["expires_at"]:
        raise HTTPException(400, "Code invalide ou expiré")
    
    # Find and update user password
    for uid, u in users_db.items():
        if isinstance(u, dict) and u.get("email") == token_data["email"]:
            users_db[f"{uid}_password"] = hash_password(new_password)
            save_data("users", users_db)
            break
    
    del reset_tokens[token]
    return {"message": "Mot de passe réinitialisé"}

# Client Routes
@app.get("/api/clients")
async def get_clients(current_user: User = Depends(get_current_user)):
    user_clients = [client for client in clients_db.values() 
                    if isinstance(client, dict) and client.get("user_id") == current_user.id]
    return user_clients

@app.post("/api/clients")
async def create_client(client_data: dict, current_user: User = Depends(get_current_user)):
    client_id = str(uuid.uuid4())
    new_client = {
        "id": client_id,
        "user_id": current_user.id,
        "name": client_data["name"],
        "email": client_data["email"],
        "phone": client_data.get("phone", ""),
        "address": client_data.get("address", ""),
        "city": client_data.get("city", ""),
        "postal_code": client_data.get("postal_code", ""),
        "country": client_data.get("country", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    clients_db[client_id] = new_client
    save_data("clients", clients_db)
    return new_client

@app.put("/api/clients/{client_id}")
async def update_client(client_id: str, client_data: dict, current_user: User = Depends(get_current_user)):
    if client_id in clients_db and clients_db[client_id]["user_id"] == current_user.id:
        clients_db[client_id].update(client_data)
        save_data("clients", clients_db)
        return clients_db[client_id]
    raise HTTPException(404, "Client not found")

@app.delete("/api/clients/{client_id}")
async def delete_client(client_id: str, current_user: User = Depends(get_current_user)):
    if client_id in clients_db and clients_db[client_id]["user_id"] == current_user.id:
        del clients_db[client_id]
        save_data("clients", clients_db)
        return {"message": "Client deleted"}
    raise HTTPException(404, "Client not found")

# Product Routes
@app.get("/api/products")
async def get_products(current_user: User = Depends(get_current_user)):
    user_products = [product for product in products_db.values() 
                     if isinstance(product, dict) and product.get("user_id") == current_user.id]
    return user_products

@app.post("/api/products")
async def create_product(product_data: dict, current_user: User = Depends(get_current_user)):
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
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    products_db[product_id] = new_product
    save_data("products", products_db)
    return new_product

@app.delete("/api/products/{product_id}")
async def delete_product(product_id: str, current_user: User = Depends(get_current_user)):
    if product_id in products_db and products_db[product_id]["user_id"] == current_user.id:
        products_db[product_id]["is_active"] = False
        save_data("products", products_db)
        return {"message": "Product deleted"}
    raise HTTPException(404, "Product not found")

# Invoice Routes
@app.get("/api/invoices")
async def get_invoices(current_user: User = Depends(get_current_user)):
    user_invoices = [invoice for invoice in invoices_db.values() 
                     if isinstance(invoice, dict) and invoice.get("user_id") == current_user.id]
    return user_invoices

@app.post("/api/invoices")
async def create_invoice(invoice_data: dict, current_user: User = Depends(get_current_user)):
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
    user_invoices = [inv for inv in invoices_db.values() 
                     if isinstance(inv, dict) and inv.get("user_id") == current_user.id]
    invoice_number = f"INV-{len(user_invoices) + 1:04d}"
    
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
    
    invoices_db[invoice_id] = new_invoice
    save_data("invoices", invoices_db)
    return new_invoice

# Quote Routes
@app.get("/api/quotes")
async def get_quotes(current_user: User = Depends(get_current_user)):
    user_quotes = [quote for quote in quotes_db.values() 
                   if isinstance(quote, dict) and quote.get("user_id") == current_user.id]
    return user_quotes

@app.post("/api/quotes")
async def create_quote(quote_data: dict, current_user: User = Depends(get_current_user)):
    quote_id = str(uuid.uuid4())
    
    user_quotes = [q for q in quotes_db.values() 
                   if isinstance(q, dict) and q.get("user_id") == current_user.id]
    quote_number = f"QUO-{len(user_quotes) + 1:04d}"
    
    new_quote = {
        "id": quote_id,
        "user_id": current_user.id,
        "client_id": quote_data["client_id"],
        "quote_number": quote_number,
        "issue_date": datetime.now(timezone.utc).isoformat(),
        "valid_until": quote_data["valid_until"],
        "items": quote_data.get("items", []),
        "total": 0,  # Calculate later
        "status": "pending",
        "notes": quote_data.get("notes", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    quotes_db[quote_id] = new_quote
    save_data("quotes", quotes_db)
    return new_quote

# Settings Routes
@app.get("/api/settings/company")
async def get_settings(current_user: User = Depends(get_current_user)):
    user_settings = settings_db.get(current_user.id, {
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "company_name": current_user.company_name,
        "email": current_user.email,
        "logo_url": "",
        "gst_number": "",
        "pst_number": "",
        "hst_number": ""
    })
    return user_settings

@app.put("/api/settings/company")
async def update_settings(settings_data: dict, current_user: User = Depends(get_current_user)):
    if current_user.id in settings_db:
        settings_db[current_user.id].update(settings_data)
    else:
        settings_db[current_user.id] = {
            "id": str(uuid.uuid4()),
            "user_id": current_user.id,
            **settings_data
        }
    
    save_data("settings", settings_db)
    return settings_db[current_user.id]

@app.post("/api/settings/company/upload-logo")
async def upload_logo(logo_data: dict, current_user: User = Depends(get_current_user)):
    if current_user.id in settings_db:
        settings_db[current_user.id]["logo_url"] = logo_data.get("logo_url")
    else:
        settings_db[current_user.id] = {
            "logo_url": logo_data.get("logo_url")
        }
    
    save_data("settings", settings_db)
    return {"message": "Logo saved", "logo_url": logo_data.get("logo_url")}

# Dashboard Stats
@app.get("/api/dashboard/stats")
async def get_stats(current_user: User = Depends(get_current_user)):
    user_clients = len([c for c in clients_db.values() 
                        if isinstance(c, dict) and c.get("user_id") == current_user.id])
    user_invoices = len([i for i in invoices_db.values() 
                         if isinstance(i, dict) and i.get("user_id") == current_user.id])
    user_quotes = len([q for q in quotes_db.values() 
                       if isinstance(q, dict) and q.get("user_id") == current_user.id])
    user_products = len([p for p in products_db.values() 
                         if isinstance(p, dict) and p.get("user_id") == current_user.id])
    
    return {
        "total_clients": user_clients,
        "total_invoices": user_invoices,
        "total_quotes": user_quotes,
        "total_products": user_products,
        "total_revenue": 0,
        "pending_invoices": 0
    }

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize gussdub account on startup
@app.on_event("startup")
async def create_accounts():
    # Create gussdub if doesn't exist
    gussdub_exists = any(
        isinstance(u, dict) and u.get("email") == "gussdub@gmail.com" 
        for u in users_db.values()
    )
    
    if not gussdub_exists:
        user_id = str(uuid.uuid4())
        users_db[user_id] = {
            "id": user_id,
            "email": "gussdub@gmail.com",
            "company_name": "ProFireManager",
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        users_db[f"{user_id}_password"] = hash_password("testpass123")
        
        settings_db[user_id] = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "company_name": "ProFireManager",
            "email": "gussdub@gmail.com",
            "gst_number": "123456789",
            "pst_number": "1234567890",
            "logo_url": ""
        }
        
        # Create sample client
        client_id = str(uuid.uuid4())
        clients_db[client_id] = {
            "id": client_id,
            "user_id": user_id,
            "name": "Client Test",
            "email": "test@client.com",
            "phone": "514-123-4567",
            "address": "123 Rue Test",
            "city": "Montréal",
            "postal_code": "H1A 1A1",
            "country": "Canada"
        }
        
        # Save all data
        save_data("users", users_db)
        save_data("settings", settings_db)
        save_data("clients", clients_db)
        
        print("✅ Compte gussdub@gmail.com créé avec données de test")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))