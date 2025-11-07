from fastapi import FastAPI, HTTPException, Depends, status, File, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorClient
import os
import jwt
import bcrypt
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import uuid
from enum import Enum
import secrets
from dotenv import load_dotenv

# Load environment
load_dotenv()

# FastAPI app
app = FastAPI(title="FacturePro API", version="2.0.0")

# Configuration
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017/facturepro')
DB_NAME = os.environ.get('DB_NAME', 'facturepro')
JWT_SECRET = os.environ.get('JWT_SECRET', 'default-secret')

# MongoDB connection
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# Security
security = HTTPBearer()

# Enums
class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid" 
    OVERDUE = "overdue"
    CANCELLED = "cancelled"

class ExpenseStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    PAID = "paid"
    REJECTED = "rejected"

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

class Product(BaseModel):
    id: str
    user_id: str
    name: str
    description: str
    unit_price: float
    unit: str = "unité"
    category: Optional[str] = None
    is_active: bool = True

class InvoiceItem(BaseModel):
    description: str
    quantity: float = 1.0
    unit_price: float
    total: float

class Invoice(BaseModel):
    id: str
    user_id: str
    client_id: str
    invoice_number: str
    issue_date: str
    due_date: str
    items: List[InvoiceItem] = []
    subtotal: float = 0
    gst_rate: float = 5.0
    pst_rate: float = 9.975
    hst_rate: float = 13.0
    gst_amount: float = 0
    pst_amount: float = 0
    hst_amount: float = 0
    total_tax: float = 0
    total: float = 0
    apply_gst: bool = True
    apply_pst: bool = True
    apply_hst: bool = False
    province: str = "QC"
    status: str = "draft"
    notes: str = ""

class Quote(BaseModel):
    id: str
    user_id: str
    client_id: str
    quote_number: str
    issue_date: str
    valid_until: str
    items: List[InvoiceItem] = []
    subtotal: float = 0
    gst_rate: float = 5.0
    pst_rate: float = 9.975
    hst_rate: float = 13.0
    gst_amount: float = 0
    pst_amount: float = 0
    hst_amount: float = 0
    total_tax: float = 0
    total: float = 0
    apply_gst: bool = True
    apply_pst: bool = True
    apply_hst: bool = False
    province: str = "QC"
    status: str = "pending"
    notes: str = ""

class Employee(BaseModel):
    id: str
    user_id: str
    name: str
    email: str
    phone: Optional[str] = None
    employee_number: Optional[str] = None
    department: Optional[str] = None
    is_active: bool = True

class Expense(BaseModel):
    id: str
    user_id: str
    employee_id: str
    description: str
    amount: float
    category: Optional[str] = None
    expense_date: str
    status: str = "pending"
    receipt_url: Optional[str] = None
    notes: Optional[str] = None

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

def calculate_taxes(subtotal, province):
    """Calculate Canadian taxes"""
    if province == "QC":
        gst = subtotal * 0.05
        pst = subtotal * 0.09975  
        hst = 0
        apply_gst, apply_pst, apply_hst = True, True, False
    elif province == "ON":
        gst = 0
        pst = 0
        hst = subtotal * 0.13
        apply_gst, apply_pst, apply_hst = False, False, True
    else:
        gst = subtotal * 0.05
        pst = 0
        hst = 0
        apply_gst, apply_pst, apply_hst = True, False, False
    
    total_tax = gst + pst + hst
    return gst, pst, hst, total_tax, apply_gst, apply_pst, apply_hst

def generate_invoice_number():
    existing = [int(inv["invoice_number"].replace("INV-", "")) for inv in invoices_db.values() 
                if isinstance(inv, dict) and "invoice_number" in inv]
    next_num = max(existing) + 1 if existing else 1
    return f"INV-{next_num:04d}"

def generate_quote_number():
    existing = [int(quote["quote_number"].replace("QUO-", "")) for quote in quotes_db.values() 
                if isinstance(quote, dict) and "quote_number" in quote]
    next_num = max(existing) + 1 if existing else 1
    return f"QUO-{next_num:04d}"

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
        
        user = await db.users.find_one({"id": user_id})
        if not user:
            raise HTTPException(401, "User not found")
        return User(**user)
    except:
        raise HTTPException(401, "Invalid token")

# Exemption for gussdub@gmail.com
async def get_current_user_with_access(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = await get_current_user(credentials)
    
    # Exempt users (always free access)
    EXEMPT_USERS = ["gussdub@gmail.com"]
    if user.email in EXEMPT_USERS:
        return user
    
    # For now, everyone has access
    return user

# Routes
@app.get("/")
async def root():
    return {"message": "FacturePro API v2.0", "status": "running"}

@app.get("/api/health")
async def health():
    return {"status": "healthy", "users": len([u for u in users_db.values() if isinstance(u, User)])}

# Auth Routes
@app.post("/api/auth/register", response_model=Token)
async def register(user_data: UserCreate):
    # Check if exists
    for user in users_db.values():
        if isinstance(user, User) and user.email == user_data.email:
            raise HTTPException(400, "Email already registered")
    
    # Create user with 14-day trial
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
    
    users_db[user_id] = new_user
    users_db[f"{user_id}_password"] = hash_password(user_data.password)
    
    # Create default settings
    settings_db[user_id] = CompanySettings(
        id=str(uuid.uuid4()),
        user_id=user_id,
        company_name=user_data.company_name,
        email=user_data.email
    ).__dict__
    
    token = create_token(user_id)
    return Token(access_token=token, token_type="bearer", user=new_user)

@app.post("/api/auth/login", response_model=Token)
async def login(credentials: UserLogin):
    user = None
    user_id = None
    for uid, u in users_db.items():
        if isinstance(u, User) and u.email == credentials.email:
            user = u
            user_id = uid
            break
    
    if not user:
        raise HTTPException(401, "Incorrect email or password")
    
    stored_password = users_db.get(f"{user_id}_password")
    if not stored_password or not verify_password(credentials.password, stored_password):
        raise HTTPException(401, "Incorrect email or password")
    
    token = create_token(user_id)
    return Token(access_token=token, token_type="bearer", user=user)

# Password Reset
@app.post("/api/auth/forgot-password")
async def forgot_password(request: dict):
    email = request.get("email")
    user = None
    for u in users_db.values():
        if isinstance(u, User) and u.email == email:
            user = u
            break
    
    if not user:
        return {"message": "Si cette adresse email existe, un code de récupération a été généré"}
    
    reset_token = secrets.token_urlsafe(32)
    reset_tokens[reset_token] = {
        "user_id": user.id,
        "email": user.email,
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
    
    user_id = token_data["user_id"]
    users_db[f"{user_id}_password"] = hash_password(new_password)
    del reset_tokens[token]
    
    return {"message": "Mot de passe réinitialisé avec succès"}

# Client Routes
@app.get("/api/clients")
async def get_clients(current_user: User = Depends(get_current_user)):
    return [client for client in clients_db.values() 
            if isinstance(client, dict) and client.get("user_id") == current_user.id]

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
    return new_client

@app.put("/api/clients/{client_id}")
async def update_client(client_id: str, client_data: dict, current_user: User = Depends(get_current_user)):
    if client_id in clients_db and clients_db[client_id]["user_id"] == current_user.id:
        clients_db[client_id].update(client_data)
        return clients_db[client_id]
    raise HTTPException(404, "Client not found")

@app.delete("/api/clients/{client_id}")
async def delete_client(client_id: str, current_user: User = Depends(get_current_user)):
    if client_id in clients_db and clients_db[client_id]["user_id"] == current_user.id:
        del clients_db[client_id]
        return {"message": "Client deleted"}
    raise HTTPException(404, "Client not found")

# Product Routes  
@app.get("/api/products")
async def get_products(current_user: User = Depends(get_current_user)):
    return [product for product in products_db.values() 
            if isinstance(product, dict) and product.get("user_id") == current_user.id]

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
    return new_product

@app.delete("/api/products/{product_id}")
async def delete_product(product_id: str, current_user: User = Depends(get_current_user)):
    if product_id in products_db and products_db[product_id]["user_id"] == current_user.id:
        products_db[product_id]["is_active"] = False
        return {"message": "Product deleted"}
    raise HTTPException(404, "Product not found")

# Invoice Routes
@app.get("/api/invoices")
async def get_invoices(current_user: User = Depends(get_current_user)):
    return [invoice for invoice in invoices_db.values() 
            if isinstance(invoice, dict) and invoice.get("user_id") == current_user.id]

@app.post("/api/invoices")
async def create_invoice(invoice_data: dict, current_user: User = Depends(get_current_user)):
    # Calculate totals
    items = invoice_data.get("items", [])
    subtotal = sum(item["quantity"] * item["unit_price"] for item in items)
    
    province = invoice_data.get("province", "QC")
    gst, pst, hst, total_tax, apply_gst, apply_pst, apply_hst = calculate_taxes(subtotal, province)
    total = subtotal + total_tax
    
    # Generate number
    invoice_number = generate_invoice_number()
    
    invoice_id = str(uuid.uuid4())
    new_invoice = {
        "id": invoice_id,
        "user_id": current_user.id,
        "client_id": invoice_data["client_id"],
        "invoice_number": invoice_number,
        "issue_date": datetime.now(timezone.utc).isoformat(),
        "due_date": invoice_data["due_date"],
        "items": items,
        "subtotal": round(subtotal, 2),
        "gst_rate": 5.0 if province == "QC" else 0,
        "pst_rate": 9.975 if province == "QC" else 0,
        "hst_rate": 13.0 if province == "ON" else 0,
        "gst_amount": round(gst, 2),
        "pst_amount": round(pst, 2),
        "hst_amount": round(hst, 2),
        "total_tax": round(total_tax, 2),
        "total": round(total, 2),
        "apply_gst": apply_gst,
        "apply_pst": apply_pst,
        "apply_hst": apply_hst,
        "province": province,
        "status": invoice_data.get("status", "draft"),
        "notes": invoice_data.get("notes", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    invoices_db[invoice_id] = new_invoice
    return new_invoice

@app.delete("/api/invoices/{invoice_id}")
async def delete_invoice(invoice_id: str, current_user: User = Depends(get_current_user)):
    if invoice_id in invoices_db and invoices_db[invoice_id]["user_id"] == current_user.id:
        del invoices_db[invoice_id]
        return {"message": "Invoice deleted"}
    raise HTTPException(404, "Invoice not found")

# Quote Routes
@app.get("/api/quotes")
async def get_quotes(current_user: User = Depends(get_current_user)):
    return [quote for quote in quotes_db.values() 
            if isinstance(quote, dict) and quote.get("user_id") == current_user.id]

@app.post("/api/quotes")
async def create_quote(quote_data: dict, current_user: User = Depends(get_current_user)):
    # Calculate totals (same as invoice)
    items = quote_data.get("items", [])
    subtotal = sum(item["quantity"] * item["unit_price"] for item in items)
    
    province = quote_data.get("province", "QC")
    gst, pst, hst, total_tax, apply_gst, apply_pst, apply_hst = calculate_taxes(subtotal, province)
    total = subtotal + total_tax
    
    quote_number = generate_quote_number()
    
    quote_id = str(uuid.uuid4())
    new_quote = {
        "id": quote_id,
        "user_id": current_user.id,
        "client_id": quote_data["client_id"],
        "quote_number": quote_number,
        "issue_date": datetime.now(timezone.utc).isoformat(),
        "valid_until": quote_data["valid_until"],
        "items": items,
        "subtotal": round(subtotal, 2),
        "gst_rate": 5.0 if province == "QC" else 0,
        "pst_rate": 9.975 if province == "QC" else 0,
        "hst_rate": 13.0 if province == "ON" else 0,
        "gst_amount": round(gst, 2),
        "pst_amount": round(pst, 2),
        "hst_amount": round(hst, 2),
        "total_tax": round(total_tax, 2),
        "total": round(total, 2),
        "apply_gst": apply_gst,
        "apply_pst": apply_pst,
        "apply_hst": apply_hst,
        "province": province,
        "status": "pending",
        "notes": quote_data.get("notes", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    quotes_db[quote_id] = new_quote
    return new_quote

@app.post("/api/quotes/{quote_id}/convert")
async def convert_quote_to_invoice(quote_id: str, due_date_data: dict, current_user: User = Depends(get_current_user)):
    if quote_id in quotes_db and quotes_db[quote_id]["user_id"] == current_user.id:
        quote = quotes_db[quote_id]
        
        # Create invoice from quote
        invoice_id = str(uuid.uuid4())
        invoice_number = generate_invoice_number()
        
        new_invoice = {
            **quote,
            "id": invoice_id,
            "invoice_number": invoice_number,
            "due_date": due_date_data["due_date"],
            "status": "draft"
        }
        new_invoice.pop("quote_number")
        new_invoice.pop("valid_until")
        
        invoices_db[invoice_id] = new_invoice
        quotes_db[quote_id]["status"] = "converted"
        
        return new_invoice
    raise HTTPException(404, "Quote not found")

# Employee Routes
@app.get("/api/employees")
async def get_employees(current_user: User = Depends(get_current_user)):
    return [emp for emp in employees_db.values() 
            if isinstance(emp, dict) and emp.get("user_id") == current_user.id]

@app.post("/api/employees")
async def create_employee(employee_data: dict, current_user: User = Depends(get_current_user)):
    employee_id = str(uuid.uuid4())
    new_employee = {
        "id": employee_id,
        "user_id": current_user.id,
        "name": employee_data["name"],
        "email": employee_data["email"],
        "phone": employee_data.get("phone", ""),
        "employee_number": employee_data.get("employee_number", ""),
        "department": employee_data.get("department", ""),
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    employees_db[employee_id] = new_employee
    return new_employee

@app.delete("/api/employees/{employee_id}")
async def delete_employee(employee_id: str, current_user: User = Depends(get_current_user)):
    if employee_id in employees_db and employees_db[employee_id]["user_id"] == current_user.id:
        employees_db[employee_id]["is_active"] = False
        return {"message": "Employee deleted"}
    raise HTTPException(404, "Employee not found")

# Expense Routes
@app.get("/api/expenses")
async def get_expenses(current_user: User = Depends(get_current_user)):
    return [expense for expense in expenses_db.values() 
            if isinstance(expense, dict) and expense.get("user_id") == current_user.id]

@app.post("/api/expenses")
async def create_expense(expense_data: dict, current_user: User = Depends(get_current_user)):
    expense_id = str(uuid.uuid4())
    new_expense = {
        "id": expense_id,
        "user_id": current_user.id,
        "employee_id": expense_data["employee_id"],
        "description": expense_data["description"],
        "amount": float(expense_data["amount"]),
        "category": expense_data.get("category", ""),
        "expense_date": expense_data.get("expense_date", datetime.now(timezone.utc).isoformat()),
        "status": "pending",
        "receipt_url": None,
        "notes": expense_data.get("notes", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    expenses_db[expense_id] = new_expense
    return new_expense

@app.put("/api/expenses/{expense_id}/status")
async def update_expense_status(expense_id: str, status_data: dict, current_user: User = Depends(get_current_user)):
    if expense_id in expenses_db and expenses_db[expense_id]["user_id"] == current_user.id:
        expenses_db[expense_id]["status"] = status_data["status"]
        return {"message": "Status updated"}
    raise HTTPException(404, "Expense not found")

# Settings Routes
@app.get("/api/settings/company")
async def get_settings(current_user: User = Depends(get_current_user)):
    return settings_db.get(current_user.id, CompanySettings(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        company_name=current_user.company_name,
        email=current_user.email
    ).__dict__)

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
    return settings_db[current_user.id]

@app.post("/api/settings/company/upload-logo")
async def upload_logo(logo_data: dict, current_user: User = Depends(get_current_user)):
    if current_user.id in settings_db:
        settings_db[current_user.id]["logo_url"] = logo_data.get("logo_url")
    return {"message": "Logo saved", "logo_url": logo_data.get("logo_url")}

# Dashboard Stats
@app.get("/api/dashboard/stats")
async def get_stats(current_user: User = Depends(get_current_user)):
    user_clients = len([c for c in clients_db.values() if isinstance(c, dict) and c.get("user_id") == current_user.id])
    user_invoices = len([i for i in invoices_db.values() if isinstance(i, dict) and i.get("user_id") == current_user.id])
    user_quotes = len([q for q in quotes_db.values() if isinstance(q, dict) and q.get("user_id") == current_user.id])
    user_products = len([p for p in products_db.values() if isinstance(p, dict) and p.get("user_id") == current_user.id])
    
    # Calculate revenue from paid invoices
    revenue = sum(inv.get("total", 0) for inv in invoices_db.values() 
                  if isinstance(inv, dict) and inv.get("user_id") == current_user.id and inv.get("status") == "paid")
    
    return {
        "total_clients": user_clients,
        "total_invoices": user_invoices,
        "total_quotes": user_quotes,
        "total_products": user_products,
        "total_revenue": revenue,
        "pending_invoices": len([i for i in invoices_db.values() 
                               if isinstance(i, dict) and i.get("user_id") == current_user.id and i.get("status") in ["sent", "overdue"]])
    }

# Export Routes
@app.get("/api/export/invoices")
async def export_invoices(current_user: User = Depends(get_current_user)):
    user_invoices = [inv for inv in invoices_db.values() 
                     if isinstance(inv, dict) and inv.get("user_id") == current_user.id]
    return {"invoices": user_invoices, "total_count": len(user_invoices)}

@app.get("/api/export/expenses")
async def export_expenses(current_user: User = Depends(get_current_user)):
    user_expenses = [exp for exp in expenses_db.values() 
                     if isinstance(exp, dict) and exp.get("user_id") == current_user.id]
    return {"expenses": user_expenses, "total_count": len(user_expenses)}

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
    # Create gussdub account with exemption
    user_id = str(uuid.uuid4())
    gussdub = User(
        id=user_id,
        email="gussdub@gmail.com",
        company_name="ProFireManager",
        is_active=True,
        subscription_status="trial",
        trial_end_date=datetime.now(timezone.utc) + timedelta(days=3650)  # 10 years
    )
    
    users_db[user_id] = gussdub
    users_db[f"{user_id}_password"] = hash_password("testpass123")
    
    settings_db[user_id] = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "company_name": "ProFireManager",
        "email": "gussdub@gmail.com",
        "gst_number": "123456789",
        "pst_number": "1234567890",
        "primary_color": "#3B82F6",
        "secondary_color": "#1F2937"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))