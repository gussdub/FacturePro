from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient
import os
import jwt
import bcrypt
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from typing import Optional, List
import uuid
import secrets
import io
import csv
from dotenv import load_dotenv

load_dotenv()

# Configuration
MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
JWT_SECRET = os.environ.get('JWT_SECRET')

# MongoDB connection via Motor
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# FastAPI app
app = FastAPI(title="FacturePro API", version="2.0.0")
security = HTTPBearer()

# CORS - must be added before routes
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Pydantic Models ───
class User(BaseModel):
    id: str
    email: str
    company_name: str
    is_active: bool = True
    subscription_status: str = "trial"
    trial_end_date: Optional[str] = None

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
    primary_color: str = "#00A08C"
    secondary_color: str = "#1F2937"
    default_due_days: int = 30
    gst_number: Optional[str] = None
    pst_number: Optional[str] = None
    hst_number: Optional[str] = None

# ─── Utility Functions ───
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(hours=24)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def clean_doc(doc):
    """Remove MongoDB _id from document"""
    if doc and "_id" in doc:
        del doc["_id"]
    return doc

def clean_docs(docs):
    """Remove MongoDB _id from list of documents"""
    return [clean_doc(d) for d in docs]

def calculate_taxes(subtotal, province):
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
    return round(gst, 2), round(pst, 2), round(hst, 2), round(gst + pst + hst, 2)

# ─── Auth Dependencies ───
EXEMPT_USERS = ["gussdub@gmail.com"]

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(401, "User not found")
        return User(**user)
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except Exception:
        raise HTTPException(401, "Invalid token")

async def get_current_user_with_access(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = await get_current_user(credentials)
    if user.email in EXEMPT_USERS:
        return user
    return user

# ─── Health & Root ───
@app.get("/")
async def root():
    return {"message": "FacturePro API v2.0", "status": "running"}

@app.get("/api/health")
async def health():
    try:
        await client.admin.command('ping')
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

# ─── Auth Routes ───
@app.post("/api/auth/register", response_model=Token)
async def register(user_data: UserCreate):
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(400, "Email already registered")

    user_id = str(uuid.uuid4())
    trial_end = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()

    user_doc = {
        "id": user_id,
        "email": user_data.email,
        "company_name": user_data.company_name,
        "is_active": True,
        "subscription_status": "trial",
        "trial_end_date": trial_end,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(user_doc)
    await db.user_passwords.insert_one({
        "user_id": user_id,
        "hashed_password": hash_password(user_data.password)
    })

    settings_doc = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "company_name": user_data.company_name,
        "email": user_data.email,
        "phone": "", "address": "", "city": "", "postal_code": "", "country": "",
        "logo_url": "", "primary_color": "#00A08C", "secondary_color": "#1F2937",
        "default_due_days": 30, "gst_number": "", "pst_number": "", "hst_number": ""
    }
    await db.company_settings.insert_one(settings_doc)

    token = create_token(user_id)
    return Token(access_token=token, user=User(**{k: v for k, v in user_doc.items() if k != "created_at" and k != "_id"}))

@app.post("/api/auth/login", response_model=Token)
async def login(credentials: UserLogin):
    user = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user:
        raise HTTPException(401, "Incorrect email or password")

    pwd_doc = await db.user_passwords.find_one({"user_id": user["id"]})
    if not pwd_doc or not verify_password(credentials.password, pwd_doc["hashed_password"]):
        raise HTTPException(401, "Incorrect email or password")

    token = create_token(user["id"])
    return Token(access_token=token, user=User(**user))

# ─── Password Reset ───
reset_tokens_store = {}

@app.post("/api/auth/forgot-password")
async def forgot_password(request: dict):
    email = request.get("email")
    user = await db.users.find_one({"email": email})
    if not user:
        return {"message": "Si cette adresse email existe, un code de recuperation a ete genere"}

    reset_token = secrets.token_urlsafe(32)
    reset_tokens_store[reset_token] = {
        "user_id": user["id"],
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    return {"message": "Code genere", "reset_token": reset_token}

@app.post("/api/auth/reset-password")
async def reset_password(request: dict):
    token = request.get("token")
    new_password = request.get("new_password")

    token_data = reset_tokens_store.get(token)
    if not token_data or datetime.now(timezone.utc) > token_data["expires_at"]:
        raise HTTPException(400, "Code invalide ou expire")

    await db.user_passwords.update_one(
        {"user_id": token_data["user_id"]},
        {"$set": {"hashed_password": hash_password(new_password)}}
    )
    del reset_tokens_store[token]
    return {"message": "Mot de passe reinitialise"}

# ─── Clients CRUD ───
@app.get("/api/clients")
async def get_clients(current_user: User = Depends(get_current_user_with_access)):
    clients = await db.clients.find({"user_id": current_user.id}, {"_id": 0}).to_list(1000)
    return clients

@app.post("/api/clients")
async def create_client(client_data: dict, current_user: User = Depends(get_current_user_with_access)):
    client_id = str(uuid.uuid4())
    doc = {
        "id": client_id,
        "user_id": current_user.id,
        "name": client_data.get("name", ""),
        "email": client_data.get("email", ""),
        "phone": client_data.get("phone", ""),
        "address": client_data.get("address", ""),
        "city": client_data.get("city", ""),
        "postal_code": client_data.get("postal_code", ""),
        "country": client_data.get("country", "Canada"),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.clients.insert_one(doc)
    return clean_doc(doc)

@app.put("/api/clients/{client_id}")
async def update_client(client_id: str, client_data: dict, current_user: User = Depends(get_current_user_with_access)):
    client_data.pop("id", None)
    client_data.pop("user_id", None)
    client_data.pop("_id", None)
    result = await db.clients.update_one(
        {"id": client_id, "user_id": current_user.id},
        {"$set": client_data}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Client not found")
    updated = await db.clients.find_one({"id": client_id}, {"_id": 0})
    return updated

@app.delete("/api/clients/{client_id}")
async def delete_client(client_id: str, current_user: User = Depends(get_current_user_with_access)):
    result = await db.clients.delete_one({"id": client_id, "user_id": current_user.id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Client not found")
    return {"message": "Client deleted"}

# ─── Products CRUD ───
@app.get("/api/products")
async def get_products(current_user: User = Depends(get_current_user_with_access)):
    products = await db.products.find({"user_id": current_user.id, "is_active": True}, {"_id": 0}).to_list(1000)
    return products

@app.post("/api/products")
async def create_product(product_data: dict, current_user: User = Depends(get_current_user_with_access)):
    product_id = str(uuid.uuid4())
    doc = {
        "id": product_id,
        "user_id": current_user.id,
        "name": product_data.get("name", ""),
        "description": product_data.get("description", ""),
        "unit_price": float(product_data.get("unit_price", 0)),
        "unit": product_data.get("unit", "unite"),
        "category": product_data.get("category", ""),
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.products.insert_one(doc)
    return clean_doc(doc)

@app.put("/api/products/{product_id}")
async def update_product(product_id: str, product_data: dict, current_user: User = Depends(get_current_user_with_access)):
    product_data.pop("id", None)
    product_data.pop("user_id", None)
    product_data.pop("_id", None)
    result = await db.products.update_one(
        {"id": product_id, "user_id": current_user.id},
        {"$set": product_data}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Product not found")
    updated = await db.products.find_one({"id": product_id}, {"_id": 0})
    return updated

@app.delete("/api/products/{product_id}")
async def delete_product(product_id: str, current_user: User = Depends(get_current_user_with_access)):
    result = await db.products.update_one(
        {"id": product_id, "user_id": current_user.id},
        {"$set": {"is_active": False}}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Product not found")
    return {"message": "Product deleted"}

# ─── Invoices CRUD ───
@app.get("/api/invoices")
async def get_invoices(current_user: User = Depends(get_current_user_with_access)):
    invoices = await db.invoices.find({"user_id": current_user.id}, {"_id": 0}).to_list(1000)
    return invoices

@app.post("/api/invoices")
async def create_invoice(invoice_data: dict, current_user: User = Depends(get_current_user_with_access)):
    invoice_id = str(uuid.uuid4())
    items = invoice_data.get("items", [])
    subtotal = sum(float(item.get("quantity", 1)) * float(item.get("unit_price", 0)) for item in items)
    province = invoice_data.get("province", "QC")
    gst, pst, hst, total_tax = calculate_taxes(subtotal, province)
    total = round(subtotal + total_tax, 2)

    count = await db.invoices.count_documents({"user_id": current_user.id})
    invoice_number = f"INV-{count + 1:04d}"

    doc = {
        "id": invoice_id,
        "user_id": current_user.id,
        "client_id": invoice_data.get("client_id", ""),
        "invoice_number": invoice_number,
        "issue_date": datetime.now(timezone.utc).isoformat(),
        "due_date": invoice_data.get("due_date", ""),
        "items": items,
        "subtotal": round(subtotal, 2),
        "gst_amount": gst,
        "pst_amount": pst,
        "hst_amount": hst,
        "total_tax": total_tax,
        "total": total,
        "province": province,
        "status": invoice_data.get("status", "draft"),
        "notes": invoice_data.get("notes", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.invoices.insert_one(doc)
    return clean_doc(doc)

@app.put("/api/invoices/{invoice_id}")
async def update_invoice(invoice_id: str, invoice_data: dict, current_user: User = Depends(get_current_user_with_access)):
    invoice_data.pop("id", None)
    invoice_data.pop("user_id", None)
    invoice_data.pop("_id", None)

    # Recalculate taxes if items changed
    if "items" in invoice_data:
        items = invoice_data["items"]
        subtotal = sum(float(item.get("quantity", 1)) * float(item.get("unit_price", 0)) for item in items)
        province = invoice_data.get("province", "QC")
        gst, pst, hst, total_tax = calculate_taxes(subtotal, province)
        invoice_data["subtotal"] = round(subtotal, 2)
        invoice_data["gst_amount"] = gst
        invoice_data["pst_amount"] = pst
        invoice_data["hst_amount"] = hst
        invoice_data["total_tax"] = total_tax
        invoice_data["total"] = round(subtotal + total_tax, 2)

    result = await db.invoices.update_one(
        {"id": invoice_id, "user_id": current_user.id},
        {"$set": invoice_data}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Invoice not found")
    updated = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
    return updated

@app.put("/api/invoices/{invoice_id}/status")
async def update_invoice_status(invoice_id: str, status_data: dict, current_user: User = Depends(get_current_user_with_access)):
    result = await db.invoices.update_one(
        {"id": invoice_id, "user_id": current_user.id},
        {"$set": {"status": status_data.get("status", "draft")}}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Invoice not found")
    return {"message": "Status updated"}

@app.delete("/api/invoices/{invoice_id}")
async def delete_invoice(invoice_id: str, current_user: User = Depends(get_current_user_with_access)):
    result = await db.invoices.delete_one({"id": invoice_id, "user_id": current_user.id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Invoice not found")
    return {"message": "Invoice deleted"}

# ─── Quotes CRUD ───
@app.get("/api/quotes")
async def get_quotes(current_user: User = Depends(get_current_user_with_access)):
    quotes = await db.quotes.find({"user_id": current_user.id}, {"_id": 0}).to_list(1000)
    return quotes

@app.post("/api/quotes")
async def create_quote(quote_data: dict, current_user: User = Depends(get_current_user_with_access)):
    quote_id = str(uuid.uuid4())
    items = quote_data.get("items", [])
    subtotal = sum(float(item.get("quantity", 1)) * float(item.get("unit_price", 0)) for item in items)
    province = quote_data.get("province", "QC")
    gst, pst, hst, total_tax = calculate_taxes(subtotal, province)
    total = round(subtotal + total_tax, 2)

    count = await db.quotes.count_documents({"user_id": current_user.id})
    quote_number = f"QUO-{count + 1:04d}"

    doc = {
        "id": quote_id,
        "user_id": current_user.id,
        "client_id": quote_data.get("client_id", ""),
        "quote_number": quote_number,
        "issue_date": datetime.now(timezone.utc).isoformat(),
        "valid_until": quote_data.get("valid_until", ""),
        "items": items,
        "subtotal": round(subtotal, 2),
        "gst_amount": gst,
        "pst_amount": pst,
        "hst_amount": hst,
        "total_tax": total_tax,
        "total": total,
        "province": province,
        "status": "pending",
        "notes": quote_data.get("notes", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.quotes.insert_one(doc)
    return clean_doc(doc)

@app.put("/api/quotes/{quote_id}")
async def update_quote(quote_id: str, quote_data: dict, current_user: User = Depends(get_current_user_with_access)):
    quote_data.pop("id", None)
    quote_data.pop("user_id", None)
    quote_data.pop("_id", None)
    result = await db.quotes.update_one(
        {"id": quote_id, "user_id": current_user.id},
        {"$set": quote_data}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Quote not found")
    updated = await db.quotes.find_one({"id": quote_id}, {"_id": 0})
    return updated

@app.post("/api/quotes/{quote_id}/convert")
async def convert_quote_to_invoice(quote_id: str, body: dict, current_user: User = Depends(get_current_user_with_access)):
    quote = await db.quotes.find_one({"id": quote_id, "user_id": current_user.id}, {"_id": 0})
    if not quote:
        raise HTTPException(404, "Quote not found")

    invoice_id = str(uuid.uuid4())
    count = await db.invoices.count_documents({"user_id": current_user.id})
    invoice_number = f"INV-{count + 1:04d}"

    invoice_doc = {
        "id": invoice_id,
        "user_id": current_user.id,
        "client_id": quote["client_id"],
        "invoice_number": invoice_number,
        "issue_date": datetime.now(timezone.utc).isoformat(),
        "due_date": body.get("due_date", ""),
        "items": quote.get("items", []),
        "subtotal": quote.get("subtotal", 0),
        "gst_amount": quote.get("gst_amount", 0),
        "pst_amount": quote.get("pst_amount", 0),
        "hst_amount": quote.get("hst_amount", 0),
        "total_tax": quote.get("total_tax", 0),
        "total": quote.get("total", 0),
        "province": quote.get("province", "QC"),
        "status": "draft",
        "notes": quote.get("notes", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.invoices.insert_one(invoice_doc)
    await db.quotes.update_one({"id": quote_id}, {"$set": {"status": "converted"}})
    return clean_doc(invoice_doc)

@app.delete("/api/quotes/{quote_id}")
async def delete_quote(quote_id: str, current_user: User = Depends(get_current_user_with_access)):
    result = await db.quotes.delete_one({"id": quote_id, "user_id": current_user.id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Quote not found")
    return {"message": "Quote deleted"}

# ─── Employees CRUD ───
@app.get("/api/employees")
async def get_employees(current_user: User = Depends(get_current_user_with_access)):
    employees = await db.employees.find({"user_id": current_user.id, "is_active": True}, {"_id": 0}).to_list(1000)
    return employees

@app.post("/api/employees")
async def create_employee(employee_data: dict, current_user: User = Depends(get_current_user_with_access)):
    employee_id = str(uuid.uuid4())
    doc = {
        "id": employee_id,
        "user_id": current_user.id,
        "name": employee_data.get("name", ""),
        "email": employee_data.get("email", ""),
        "phone": employee_data.get("phone", ""),
        "employee_number": employee_data.get("employee_number", ""),
        "department": employee_data.get("department", ""),
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.employees.insert_one(doc)
    return clean_doc(doc)

@app.put("/api/employees/{employee_id}")
async def update_employee(employee_id: str, employee_data: dict, current_user: User = Depends(get_current_user_with_access)):
    employee_data.pop("id", None)
    employee_data.pop("user_id", None)
    employee_data.pop("_id", None)
    result = await db.employees.update_one(
        {"id": employee_id, "user_id": current_user.id},
        {"$set": employee_data}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Employee not found")
    updated = await db.employees.find_one({"id": employee_id}, {"_id": 0})
    return updated

@app.delete("/api/employees/{employee_id}")
async def delete_employee(employee_id: str, current_user: User = Depends(get_current_user_with_access)):
    result = await db.employees.update_one(
        {"id": employee_id, "user_id": current_user.id},
        {"$set": {"is_active": False}}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Employee not found")
    return {"message": "Employee deleted"}

# ─── Expenses CRUD ───
@app.get("/api/expenses")
async def get_expenses(current_user: User = Depends(get_current_user_with_access)):
    expenses = await db.expenses.find({"user_id": current_user.id}, {"_id": 0}).to_list(1000)
    return expenses

@app.post("/api/expenses")
async def create_expense(expense_data: dict, current_user: User = Depends(get_current_user_with_access)):
    expense_id = str(uuid.uuid4())
    doc = {
        "id": expense_id,
        "user_id": current_user.id,
        "employee_id": expense_data.get("employee_id", ""),
        "description": expense_data.get("description", ""),
        "amount": float(expense_data.get("amount", 0)),
        "category": expense_data.get("category", ""),
        "expense_date": expense_data.get("expense_date", datetime.now(timezone.utc).isoformat()),
        "status": "pending",
        "receipt_url": expense_data.get("receipt_url", ""),
        "notes": expense_data.get("notes", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.expenses.insert_one(doc)
    return clean_doc(doc)

@app.put("/api/expenses/{expense_id}")
async def update_expense(expense_id: str, expense_data: dict, current_user: User = Depends(get_current_user_with_access)):
    expense_data.pop("id", None)
    expense_data.pop("user_id", None)
    expense_data.pop("_id", None)
    result = await db.expenses.update_one(
        {"id": expense_id, "user_id": current_user.id},
        {"$set": expense_data}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Expense not found")
    updated = await db.expenses.find_one({"id": expense_id}, {"_id": 0})
    return updated

@app.put("/api/expenses/{expense_id}/status")
async def update_expense_status(expense_id: str, status_data: dict, current_user: User = Depends(get_current_user_with_access)):
    result = await db.expenses.update_one(
        {"id": expense_id, "user_id": current_user.id},
        {"$set": {"status": status_data.get("status", "pending")}}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Expense not found")
    return {"message": "Status updated"}

@app.delete("/api/expenses/{expense_id}")
async def delete_expense(expense_id: str, current_user: User = Depends(get_current_user_with_access)):
    result = await db.expenses.delete_one({"id": expense_id, "user_id": current_user.id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Expense not found")
    return {"message": "Expense deleted"}

# ─── Settings Routes ───
@app.get("/api/settings/company")
async def get_settings(current_user: User = Depends(get_current_user_with_access)):
    settings = await db.company_settings.find_one({"user_id": current_user.id}, {"_id": 0})
    if not settings:
        default = {
            "id": str(uuid.uuid4()),
            "user_id": current_user.id,
            "company_name": current_user.company_name,
            "email": current_user.email,
            "phone": "", "address": "", "city": "", "postal_code": "", "country": "",
            "logo_url": "", "primary_color": "#3B82F6", "secondary_color": "#1F2937",
            "default_due_days": 30, "gst_number": "", "pst_number": "", "hst_number": ""
        }
        await db.company_settings.insert_one(default)
        return {k: v for k, v in default.items() if k != "_id"}
    return settings

@app.put("/api/settings/company")
async def update_settings(settings_data: dict, current_user: User = Depends(get_current_user_with_access)):
    settings_data.pop("_id", None)
    settings_data.pop("user_id", None)
    await db.company_settings.update_one(
        {"user_id": current_user.id},
        {"$set": settings_data},
        upsert=True
    )
    updated = await db.company_settings.find_one({"user_id": current_user.id}, {"_id": 0})
    return updated

@app.post("/api/settings/company/upload-logo")
async def upload_logo(logo_data: dict, current_user: User = Depends(get_current_user_with_access)):
    await db.company_settings.update_one(
        {"user_id": current_user.id},
        {"$set": {"logo_url": logo_data.get("logo_url", "")}},
        upsert=True
    )
    return {"message": "Logo saved", "logo_url": logo_data.get("logo_url", "")}

# ─── Dashboard Stats ───
@app.get("/api/dashboard/stats")
async def get_stats(current_user: User = Depends(get_current_user_with_access)):
    total_clients = await db.clients.count_documents({"user_id": current_user.id})
    total_invoices = await db.invoices.count_documents({"user_id": current_user.id})
    total_quotes = await db.quotes.count_documents({"user_id": current_user.id})
    total_products = await db.products.count_documents({"user_id": current_user.id, "is_active": True})
    total_employees = await db.employees.count_documents({"user_id": current_user.id, "is_active": True})
    total_expenses = await db.expenses.count_documents({"user_id": current_user.id})

    # Revenue from paid invoices
    paid_invoices = await db.invoices.find(
        {"user_id": current_user.id, "status": "paid"}, {"total": 1, "_id": 0}
    ).to_list(1000)
    total_revenue = sum(inv.get("total", 0) for inv in paid_invoices)

    pending_count = await db.invoices.count_documents(
        {"user_id": current_user.id, "status": {"$in": ["sent", "overdue"]}}
    )

    return {
        "total_clients": total_clients,
        "total_invoices": total_invoices,
        "total_quotes": total_quotes,
        "total_products": total_products,
        "total_employees": total_employees,
        "total_expenses": total_expenses,
        "total_revenue": round(total_revenue, 2),
        "pending_invoices": pending_count
    }

# ─── CSV Export ───
@app.get("/api/export/invoices/csv")
async def export_invoices_csv(current_user: User = Depends(get_current_user_with_access)):
    invoices = await db.invoices.find({"user_id": current_user.id}, {"_id": 0}).to_list(1000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Numero", "Client ID", "Date", "Echeance", "Sous-total", "TPS", "TVQ", "TVH", "Total", "Statut"])
    for inv in invoices:
        writer.writerow([
            inv.get("invoice_number", ""), inv.get("client_id", ""),
            inv.get("issue_date", ""), inv.get("due_date", ""),
            inv.get("subtotal", 0), inv.get("gst_amount", 0),
            inv.get("pst_amount", 0), inv.get("hst_amount", 0),
            inv.get("total", 0), inv.get("status", "")
        ])
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=factures.csv"}
    )

@app.get("/api/export/expenses/csv")
async def export_expenses_csv(current_user: User = Depends(get_current_user_with_access)):
    expenses = await db.expenses.find({"user_id": current_user.id}, {"_id": 0}).to_list(1000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Description", "Montant", "Categorie", "Date", "Employe ID", "Statut"])
    for exp in expenses:
        writer.writerow([
            exp.get("description", ""), exp.get("amount", 0),
            exp.get("category", ""), exp.get("expense_date", ""),
            exp.get("employee_id", ""), exp.get("status", "")
        ])
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=depenses.csv"}
    )

# ─── Startup: Seed gussdub account ───
@app.on_event("startup")
async def seed_data():
    try:
        await client.admin.command('ping')
        print("MongoDB connected")

        existing = await db.users.find_one({"email": "gussdub@gmail.com"})
        if existing:
            # Ensure password doc exists
            uid = existing["id"]
            pwd_exists = await db.user_passwords.find_one({"user_id": uid})
            if not pwd_exists:
                await db.user_passwords.insert_one({
                    "user_id": uid,
                    "hashed_password": hash_password("testpass123")
                })
                print("Repaired missing password for gussdub@gmail.com")
            print("gussdub@gmail.com already exists")
        if not existing:
            user_id = str(uuid.uuid4())
            trial_end = (datetime.now(timezone.utc) + timedelta(days=3650)).isoformat()

            await db.users.insert_one({
                "id": user_id,
                "email": "gussdub@gmail.com",
                "company_name": "ProFireManager",
                "is_active": True,
                "subscription_status": "trial",
                "trial_end_date": trial_end,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            await db.user_passwords.insert_one({
                "user_id": user_id,
                "hashed_password": hash_password("testpass123")
            })
            await db.company_settings.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "company_name": "ProFireManager",
                "email": "gussdub@gmail.com",
                "phone": "", "address": "", "city": "", "postal_code": "", "country": "Canada",
                "logo_url": "", "primary_color": "#3B82F6", "secondary_color": "#1F2937",
                "default_due_days": 30, "gst_number": "123456789", "pst_number": "1234567890", "hst_number": ""
            })
            await db.clients.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "name": "Client Test",
                "email": "test@client.com",
                "phone": "514-123-4567",
                "address": "123 Rue Test",
                "city": "Montreal",
                "postal_code": "H1A 1A1",
                "country": "Canada",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            await db.products.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "name": "Consultation",
                "description": "Consultation professionnelle",
                "unit_price": 100.0,
                "unit": "heure",
                "category": "Services",
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            print("Seeded gussdub@gmail.com account with sample data")
    except Exception as e:
        print(f"Startup error: {e}")
