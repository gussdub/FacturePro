from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pymongo import MongoClient
import os
import jwt
import bcrypt
import resend
import requests as http_requests
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from typing import Optional
import uuid
import secrets
import io
import csv
import base64
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch, mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

load_dotenv()

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
JWT_SECRET = os.environ.get('JWT_SECRET')
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY')
SUBSCRIPTION_PRICE_CAD = 15.00

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
APP_NAME = "facturepro"
storage_key = None

def init_storage():
    global storage_key
    if storage_key:
        return storage_key
    if not EMERGENT_LLM_KEY:
        print("WARNING: EMERGENT_LLM_KEY not set, file uploads disabled")
        return None
    try:
        resp = http_requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_LLM_KEY}, timeout=30)
        resp.raise_for_status()
        storage_key = resp.json()["storage_key"]
        return storage_key
    except Exception as e:
        print(f"Storage init error: {e}")
        return None

def put_object(path, data, content_type):
    key = init_storage()
    if not key:
        raise HTTPException(500, "Storage not available")
    resp = http_requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data, timeout=120
    )
    resp.raise_for_status()
    return resp.json()

def get_object(path):
    key = init_storage()
    if not key:
        raise HTTPException(500, "Storage not available")
    resp = http_requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key}, timeout=60
    )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")

client = MongoClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="FacturePro API", version="2.0.0")
security = HTTPBearer()

cors_origins_str = os.environ.get('CORS_ORIGINS', '*')
if cors_origins_str == '*':
    origins = ["*"]
else:
    origins = [o.strip() for o in cors_origins_str.split(',')]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=origins,
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

# ─── Utility Functions ───
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(hours=24)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def clean_doc(doc):
    if doc and "_id" in doc:
        del doc["_id"]
    return doc

def clean_docs(cursor):
    return [clean_doc(d) for d in cursor]

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

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
        user = db.users.find_one({"id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(401, "User not found")
        return User(**user)
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except Exception:
        raise HTTPException(401, "Invalid token")

def get_current_user_with_access(credentials: HTTPAuthorizationCredentials = Depends(security)):
    return get_current_user(credentials)

@app.get("/api/auth/me")
def get_me(current_user: User = Depends(get_current_user_with_access)):
    user_doc = db.users.find_one({"id": current_user.id}, {"_id": 0})
    sub_status = user_doc.get("subscription_status", "trial")
    trial_end = user_doc.get("trial_end_date")
    is_exempt = user_doc.get("email") in EXEMPT_USERS
    if sub_status == "trial" and trial_end and not is_exempt:
        try:
            trial_end_dt = datetime.fromisoformat(trial_end)
            if datetime.now(timezone.utc) > trial_end_dt:
                sub_status = "expired"
        except Exception:
            pass
    return {
        "id": current_user.id,
        "email": current_user.email,
        "company_name": current_user.company_name,
        "subscription_status": "active" if is_exempt else sub_status,
        "trial_end_date": trial_end,
        "is_exempt": is_exempt
    }

# ─── Health ───
@app.get("/")
def root():
    return {"message": "FacturePro API v2.0", "status": "running"}

@app.get("/api/health")
def health():
    try:
        client.admin.command('ping')
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

# ─── Auth Routes ───
@app.post("/api/auth/register", response_model=Token)
def register(user_data: UserCreate):
    existing = db.users.find_one({"email": user_data.email})
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
    db.users.insert_one(user_doc)
    db.user_passwords.insert_one({
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
    db.company_settings.insert_one(settings_doc)

    token = create_token(user_id)
    user_response = {k: v for k, v in user_doc.items() if k not in ("created_at", "_id")}
    return Token(access_token=token, user=User(**user_response))

@app.post("/api/auth/login", response_model=Token)
def login(credentials: UserLogin):
    user = db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user:
        raise HTTPException(401, "Incorrect email or password")

    pwd_doc = db.user_passwords.find_one({"user_id": user["id"]})
    if not pwd_doc or not verify_password(credentials.password, pwd_doc["hashed_password"]):
        raise HTTPException(401, "Incorrect email or password")

    token = create_token(user["id"])
    return Token(access_token=token, user=User(**user))

# ─── Password Reset ───
reset_tokens_store = {}

@app.post("/api/auth/forgot-password")
def forgot_password(request: dict):
    email = request.get("email")
    if not email:
        raise HTTPException(400, "Email required")

    user = db.users.find_one({"email": email})
    if not user:
        return {"message": "Si cette adresse email existe, un code de recuperation a ete genere"}

    reset_token = secrets.token_urlsafe(32)
    reset_tokens_store[reset_token] = {
        "user_id": user["id"],
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    return {"message": "Code genere", "reset_token": reset_token}

@app.post("/api/auth/reset-password")
def reset_password(request: dict):
    token = request.get("token")
    new_password = request.get("new_password")

    token_data = reset_tokens_store.get(token)
    if not token_data or datetime.now(timezone.utc) > token_data["expires_at"]:
        raise HTTPException(400, "Code invalide ou expire")

    db.user_passwords.update_one(
        {"user_id": token_data["user_id"]},
        {"$set": {"hashed_password": hash_password(new_password)}}
    )
    del reset_tokens_store[token]
    return {"message": "Mot de passe reinitialise"}

# ─── Clients CRUD ───
@app.get("/api/clients")
def get_clients(current_user: User = Depends(get_current_user_with_access)):
    return clean_docs(db.clients.find({"user_id": current_user.id}, {"_id": 0}))

@app.post("/api/clients")
def create_client(client_data: dict, current_user: User = Depends(get_current_user_with_access)):
    doc = {
        "id": str(uuid.uuid4()), "user_id": current_user.id,
        "name": client_data.get("name", ""), "email": client_data.get("email", ""),
        "phone": client_data.get("phone", ""), "address": client_data.get("address", ""),
        "city": client_data.get("city", ""), "postal_code": client_data.get("postal_code", ""),
        "country": client_data.get("country", "Canada"),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    db.clients.insert_one(doc)
    return clean_doc(doc)

@app.put("/api/clients/{client_id}")
def update_client(client_id: str, client_data: dict, current_user: User = Depends(get_current_user_with_access)):
    for k in ("id", "user_id", "_id"):
        client_data.pop(k, None)
    result = db.clients.update_one({"id": client_id, "user_id": current_user.id}, {"$set": client_data})
    if result.matched_count == 0:
        raise HTTPException(404, "Client not found")
    return clean_doc(db.clients.find_one({"id": client_id}, {"_id": 0}))

@app.delete("/api/clients/{client_id}")
def delete_client(client_id: str, current_user: User = Depends(get_current_user_with_access)):
    result = db.clients.delete_one({"id": client_id, "user_id": current_user.id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Client not found")
    return {"message": "Client deleted"}

# ─── Products CRUD ───
@app.get("/api/products")
def get_products(current_user: User = Depends(get_current_user_with_access)):
    return clean_docs(db.products.find({"user_id": current_user.id, "is_active": True}, {"_id": 0}))

@app.post("/api/products")
def create_product(product_data: dict, current_user: User = Depends(get_current_user_with_access)):
    doc = {
        "id": str(uuid.uuid4()), "user_id": current_user.id,
        "name": product_data.get("name", ""), "description": product_data.get("description", ""),
        "unit_price": float(product_data.get("unit_price", 0)),
        "unit": product_data.get("unit", "unite"), "category": product_data.get("category", ""),
        "is_active": True, "created_at": datetime.now(timezone.utc).isoformat()
    }
    db.products.insert_one(doc)
    return clean_doc(doc)

@app.put("/api/products/{product_id}")
def update_product(product_id: str, product_data: dict, current_user: User = Depends(get_current_user_with_access)):
    for k in ("id", "user_id", "_id"):
        product_data.pop(k, None)
    result = db.products.update_one({"id": product_id, "user_id": current_user.id}, {"$set": product_data})
    if result.matched_count == 0:
        raise HTTPException(404, "Product not found")
    return clean_doc(db.products.find_one({"id": product_id}, {"_id": 0}))

@app.delete("/api/products/{product_id}")
def delete_product(product_id: str, current_user: User = Depends(get_current_user_with_access)):
    result = db.products.update_one({"id": product_id, "user_id": current_user.id}, {"$set": {"is_active": False}})
    if result.matched_count == 0:
        raise HTTPException(404, "Product not found")
    return {"message": "Product deleted"}

# ─── Invoices CRUD ───
@app.get("/api/invoices")
def get_invoices(current_user: User = Depends(get_current_user_with_access)):
    return clean_docs(db.invoices.find({"user_id": current_user.id}, {"_id": 0}))

@app.post("/api/invoices")
def create_invoice(invoice_data: dict, current_user: User = Depends(get_current_user_with_access)):
    items = invoice_data.get("items", [])
    subtotal = sum(float(item.get("quantity", 1)) * float(item.get("unit_price", 0)) for item in items)
    province = invoice_data.get("province", "QC")
    gst, pst, hst, total_tax = calculate_taxes(subtotal, province)
    total = round(subtotal + total_tax, 2)
    count = db.invoices.count_documents({"user_id": current_user.id})
    doc = {
        "id": str(uuid.uuid4()), "user_id": current_user.id,
        "client_id": invoice_data.get("client_id", ""),
        "invoice_number": invoice_data.get("invoice_number") or f"INV-{count + 1:04d}",
        "issue_date": datetime.now(timezone.utc).isoformat(),
        "due_date": invoice_data.get("due_date", ""),
        "items": items, "subtotal": round(subtotal, 2),
        "gst_amount": gst, "pst_amount": pst, "hst_amount": hst,
        "total_tax": total_tax, "total": total, "province": province,
        "status": invoice_data.get("status", "draft"),
        "notes": invoice_data.get("notes", ""),
        "recurrence": invoice_data.get("recurrence", "none"),
        "next_send_date": invoice_data.get("next_send_date", ""),
        "recurrence_active": invoice_data.get("recurrence", "none") != "none",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    db.invoices.insert_one(doc)
    return clean_doc(doc)

@app.put("/api/invoices/{invoice_id}")
def update_invoice(invoice_id: str, invoice_data: dict, current_user: User = Depends(get_current_user_with_access)):
    for k in ("id", "user_id", "_id"):
        invoice_data.pop(k, None)
    if "items" in invoice_data:
        items = invoice_data["items"]
        subtotal = sum(float(item.get("quantity", 1)) * float(item.get("unit_price", 0)) for item in items)
        province = invoice_data.get("province", "QC")
        gst, pst, hst, total_tax = calculate_taxes(subtotal, province)
        invoice_data.update({"subtotal": round(subtotal, 2), "gst_amount": gst, "pst_amount": pst, "hst_amount": hst, "total_tax": total_tax, "total": round(subtotal + total_tax, 2)})
    result = db.invoices.update_one({"id": invoice_id, "user_id": current_user.id}, {"$set": invoice_data})
    if result.matched_count == 0:
        raise HTTPException(404, "Invoice not found")
    return clean_doc(db.invoices.find_one({"id": invoice_id}, {"_id": 0}))

@app.put("/api/invoices/{invoice_id}/status")
def update_invoice_status(invoice_id: str, status_data: dict, current_user: User = Depends(get_current_user_with_access)):
    result = db.invoices.update_one({"id": invoice_id, "user_id": current_user.id}, {"$set": {"status": status_data.get("status", "draft")}})
    if result.matched_count == 0:
        raise HTTPException(404, "Invoice not found")
    return {"message": "Status updated"}

@app.delete("/api/invoices/{invoice_id}")
def delete_invoice(invoice_id: str, current_user: User = Depends(get_current_user_with_access)):
    result = db.invoices.delete_one({"id": invoice_id, "user_id": current_user.id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Invoice not found")
    return {"message": "Invoice deleted"}

@app.put("/api/invoices/{invoice_id}/recurrence")
def toggle_recurrence(invoice_id: str, body: dict, current_user: User = Depends(get_current_user_with_access)):
    active = body.get("recurrence_active", False)
    update = {"recurrence_active": active}
    if not active:
        update["recurrence"] = "none"
        update["next_send_date"] = ""
    result = db.invoices.update_one({"id": invoice_id, "user_id": current_user.id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Invoice not found")
    return {"message": "Recurrence updated"}

def _advance_date(date_str, recurrence):
    from dateutil.relativedelta import relativedelta
    d = datetime.fromisoformat(date_str + "T00:00:00+00:00") if len(date_str) == 10 else datetime.fromisoformat(date_str)
    if recurrence == "biweekly":
        d += timedelta(days=14)
    elif recurrence == "monthly":
        d += relativedelta(months=1)
    elif recurrence == "quarterly":
        d += relativedelta(months=3)
    elif recurrence == "annual":
        d += relativedelta(years=1)
    return d.strftime("%Y-%m-%d")

@app.post("/api/invoices/process-recurring")
def process_recurring_invoices(current_user: User = Depends(get_current_user_with_access)):
    if not RESEND_API_KEY:
        raise HTTPException(500, "Email service not configured")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    invoices = list(db.invoices.find({
        "user_id": current_user.id,
        "recurrence_active": True,
        "recurrence": {"$ne": "none"},
        "next_send_date": {"$lte": today, "$ne": ""}
    }, {"_id": 0}))
    sent_count = 0
    errors = []
    settings = db.company_settings.find_one({"user_id": current_user.id}, {"_id": 0}) or {}
    products = list(db.products.find({"user_id": current_user.id}, {"_id": 0}))
    for inv in invoices:
        client = db.clients.find_one({"id": inv.get("client_id"), "user_id": current_user.id}, {"_id": 0})
        to_email = (client or {}).get("email", "")
        if not to_email:
            errors.append(f"{inv.get('invoice_number')}: pas d'email client")
            continue
        try:
            pdf_buffer = generate_document_pdf("invoice", inv, settings, client, products)
            pdf_bytes = pdf_buffer.read()
            pdf_b64 = base64.b64encode(pdf_bytes).decode()
            comp_name = settings.get('company_name', 'FacturePro')
            inv_num = inv.get('invoice_number', 'N/A')
            params = {
                "from": SENDER_EMAIL,
                "to": [to_email],
                "subject": f"Facture {inv_num} - {comp_name}",
                "text": f"Bonjour,\n\nVeuillez trouver ci-joint la facture {inv_num}.\n\nCordialement,\n{comp_name}",
                "attachments": [{"filename": f"facture_{inv_num}.pdf", "content": pdf_b64}]
            }
            resend.Emails.send(params)
            new_next = _advance_date(inv["next_send_date"], inv["recurrence"])
            new_due = _advance_date(inv.get("due_date", inv["next_send_date"]), inv["recurrence"])
            db.invoices.update_one({"id": inv["id"]}, {"$set": {
                "next_send_date": new_next,
                "due_date": new_due,
                "status": "sent",
                "last_sent": datetime.now(timezone.utc).isoformat()
            }})
            sent_count += 1
        except Exception as e:
            errors.append(f"{inv.get('invoice_number')}: {str(e)}")
    return {"sent": sent_count, "errors": errors}

# ─── Quotes CRUD ───
@app.get("/api/quotes")
def get_quotes(current_user: User = Depends(get_current_user_with_access)):
    return clean_docs(db.quotes.find({"user_id": current_user.id}, {"_id": 0}))

@app.post("/api/quotes")
def create_quote(quote_data: dict, current_user: User = Depends(get_current_user_with_access)):
    items = quote_data.get("items", [])
    subtotal = sum(float(item.get("quantity", 1)) * float(item.get("unit_price", 0)) for item in items)
    province = quote_data.get("province", "QC")
    gst, pst, hst, total_tax = calculate_taxes(subtotal, province)
    total = round(subtotal + total_tax, 2)
    count = db.quotes.count_documents({"user_id": current_user.id})
    doc = {
        "id": str(uuid.uuid4()), "user_id": current_user.id,
        "client_id": quote_data.get("client_id", ""),
        "quote_number": f"QUO-{count + 1:04d}",
        "issue_date": datetime.now(timezone.utc).isoformat(),
        "valid_until": quote_data.get("valid_until", ""),
        "items": items, "subtotal": round(subtotal, 2),
        "gst_amount": gst, "pst_amount": pst, "hst_amount": hst,
        "total_tax": total_tax, "total": total, "province": province,
        "status": "pending", "notes": quote_data.get("notes", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    db.quotes.insert_one(doc)
    return clean_doc(doc)

@app.put("/api/quotes/{quote_id}")
def update_quote(quote_id: str, quote_data: dict, current_user: User = Depends(get_current_user_with_access)):
    for k in ("id", "user_id", "_id"):
        quote_data.pop(k, None)
    if "items" in quote_data:
        items = quote_data["items"]
        subtotal = sum(float(item.get("quantity", 1)) * float(item.get("unit_price", 0)) for item in items)
        province = quote_data.get("province", "QC")
        gst, pst, hst, total_tax = calculate_taxes(subtotal, province)
        quote_data.update({"subtotal": round(subtotal, 2), "gst_amount": gst, "pst_amount": pst, "hst_amount": hst, "total_tax": total_tax, "total": round(subtotal + total_tax, 2)})
    result = db.quotes.update_one({"id": quote_id, "user_id": current_user.id}, {"$set": quote_data})
    if result.matched_count == 0:
        raise HTTPException(404, "Quote not found")
    return clean_doc(db.quotes.find_one({"id": quote_id}, {"_id": 0}))

@app.post("/api/quotes/{quote_id}/convert")
def convert_quote_to_invoice(quote_id: str, body: dict, current_user: User = Depends(get_current_user_with_access)):
    quote = db.quotes.find_one({"id": quote_id, "user_id": current_user.id}, {"_id": 0})
    if not quote:
        raise HTTPException(404, "Quote not found")
    count = db.invoices.count_documents({"user_id": current_user.id})
    invoice_doc = {
        "id": str(uuid.uuid4()), "user_id": current_user.id,
        "client_id": quote["client_id"], "invoice_number": f"INV-{count + 1:04d}",
        "issue_date": datetime.now(timezone.utc).isoformat(),
        "due_date": body.get("due_date", ""), "items": quote.get("items", []),
        "subtotal": quote.get("subtotal", 0), "gst_amount": quote.get("gst_amount", 0),
        "pst_amount": quote.get("pst_amount", 0), "hst_amount": quote.get("hst_amount", 0),
        "total_tax": quote.get("total_tax", 0), "total": quote.get("total", 0),
        "province": quote.get("province", "QC"), "status": "draft",
        "notes": quote.get("notes", ""), "created_at": datetime.now(timezone.utc).isoformat()
    }
    db.invoices.insert_one(invoice_doc)
    db.quotes.update_one({"id": quote_id}, {"$set": {"status": "converted"}})
    return clean_doc(invoice_doc)

@app.put("/api/quotes/{quote_id}/status")
def update_quote_status(quote_id: str, status_data: dict, current_user: User = Depends(get_current_user_with_access)):
    new_status = status_data.get("status", "pending")
    result = db.quotes.update_one({"id": quote_id, "user_id": current_user.id}, {"$set": {"status": new_status}})
    if result.matched_count == 0:
        raise HTTPException(404, "Quote not found")
    return {"message": "Status updated"}

@app.delete("/api/quotes/{quote_id}")
def delete_quote(quote_id: str, current_user: User = Depends(get_current_user_with_access)):
    result = db.quotes.delete_one({"id": quote_id, "user_id": current_user.id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Quote not found")
    return {"message": "Quote deleted"}

# ─── Employees CRUD ───
@app.get("/api/employees")
def get_employees(current_user: User = Depends(get_current_user_with_access)):
    return clean_docs(db.employees.find({"user_id": current_user.id, "is_active": True}, {"_id": 0}))

@app.post("/api/employees")
def create_employee(employee_data: dict, current_user: User = Depends(get_current_user_with_access)):
    doc = {
        "id": str(uuid.uuid4()), "user_id": current_user.id,
        "name": employee_data.get("name", ""), "email": employee_data.get("email", ""),
        "phone": employee_data.get("phone", ""), "employee_number": employee_data.get("employee_number", ""),
        "department": employee_data.get("department", ""), "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    db.employees.insert_one(doc)
    return clean_doc(doc)

@app.put("/api/employees/{employee_id}")
def update_employee(employee_id: str, employee_data: dict, current_user: User = Depends(get_current_user_with_access)):
    for k in ("id", "user_id", "_id"):
        employee_data.pop(k, None)
    result = db.employees.update_one({"id": employee_id, "user_id": current_user.id}, {"$set": employee_data})
    if result.matched_count == 0:
        raise HTTPException(404, "Employee not found")
    return clean_doc(db.employees.find_one({"id": employee_id}, {"_id": 0}))

@app.delete("/api/employees/{employee_id}")
def delete_employee(employee_id: str, current_user: User = Depends(get_current_user_with_access)):
    result = db.employees.update_one({"id": employee_id, "user_id": current_user.id}, {"$set": {"is_active": False}})
    if result.matched_count == 0:
        raise HTTPException(404, "Employee not found")
    return {"message": "Employee deleted"}

# ─── Expenses CRUD ───
@app.get("/api/expenses")
def get_expenses(current_user: User = Depends(get_current_user_with_access)):
    return clean_docs(db.expenses.find({"user_id": current_user.id}, {"_id": 0}))

@app.post("/api/expenses")
def create_expense(expense_data: dict, current_user: User = Depends(get_current_user_with_access)):
    doc = {
        "id": str(uuid.uuid4()), "user_id": current_user.id,
        "employee_id": expense_data.get("employee_id", ""),
        "description": expense_data.get("description", ""),
        "amount": float(expense_data.get("amount", 0)),
        "category": expense_data.get("category", ""),
        "expense_date": expense_data.get("expense_date", datetime.now(timezone.utc).isoformat()),
        "status": "pending", "receipt_url": expense_data.get("receipt_url", ""),
        "notes": expense_data.get("notes", ""), "created_at": datetime.now(timezone.utc).isoformat()
    }
    db.expenses.insert_one(doc)
    return clean_doc(doc)

@app.put("/api/expenses/{expense_id}")
def update_expense(expense_id: str, expense_data: dict, current_user: User = Depends(get_current_user_with_access)):
    for k in ("id", "user_id", "_id"):
        expense_data.pop(k, None)
    result = db.expenses.update_one({"id": expense_id, "user_id": current_user.id}, {"$set": expense_data})
    if result.matched_count == 0:
        raise HTTPException(404, "Expense not found")
    return clean_doc(db.expenses.find_one({"id": expense_id}, {"_id": 0}))

@app.put("/api/expenses/{expense_id}/status")
def update_expense_status(expense_id: str, status_data: dict, current_user: User = Depends(get_current_user_with_access)):
    result = db.expenses.update_one({"id": expense_id, "user_id": current_user.id}, {"$set": {"status": status_data.get("status", "pending")}})
    if result.matched_count == 0:
        raise HTTPException(404, "Expense not found")
    return {"message": "Status updated"}

@app.delete("/api/expenses/{expense_id}")
def delete_expense(expense_id: str, current_user: User = Depends(get_current_user_with_access)):
    result = db.expenses.delete_one({"id": expense_id, "user_id": current_user.id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Expense not found")
    return {"message": "Expense deleted"}

# ─── CSV Import for Expenses ───
import csv
import io
import re as re_module

FIELD_PATTERNS = {
    "expense_date": [r"date", r"jour", r"day", r"posted", r"effective"],
    "amount": [r"amount", r"montant", r"total", r"debit", r"d.bit", r"credit", r"cr.dit", r"sum", r"value", r"prix", r"cost", r"cout", r"co.t"],
    "description": [r"desc", r"libell", r"detail", r"memo", r"narr", r"ref", r"comment", r"name", r"nom", r"transaction"],
    "category": [r"categ", r"type", r"class", r"group", r"dept", r"department", r"service"],
    "notes": [r"note", r"remarque", r"observ", r"info"],
}

def detect_column_mapping(headers):
    mapping = {}
    used = set()
    for field, patterns in FIELD_PATTERNS.items():
        best = None
        for i, h in enumerate(headers):
            if i in used:
                continue
            h_lower = h.lower().strip()
            for pat in patterns:
                if re_module.search(pat, h_lower):
                    best = i
                    break
            if best is not None:
                break
        if best is not None:
            mapping[field] = best
            used.add(best)
    return mapping

def parse_amount(val):
    if not val:
        return 0.0
    val = str(val).strip().replace(" ", "").replace("\u00a0", "")
    val = val.replace("$", "").replace("CAD", "").replace("€", "").replace(",", ".").strip()
    neg = val.startswith("(") and val.endswith(")")
    if neg:
        val = val[1:-1]
    val = re_module.sub(r"[^\d.\-]", "", val)
    try:
        result = abs(float(val))
        return -result if neg else result
    except:
        return 0.0

def parse_date(val):
    if not val:
        return ""
    val = str(val).strip()
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y", "%m-%d-%Y", "%d.%m.%Y", "%Y%m%d"]:
        try:
            return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
        except:
            continue
    return val[:10]

@app.post("/api/expenses/import-csv")
def import_csv_preview(file: UploadFile = File(...), current_user: User = Depends(get_current_user_with_access)):
    content = file.file.read()
    for encoding in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            text = content.decode(encoding)
            break
        except:
            continue
    else:
        raise HTTPException(400, "Impossible de lire le fichier CSV")

    for delimiter in [",", ";", "\t", "|"]:
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        rows = list(reader)
        if len(rows) > 1 and len(rows[0]) > 1:
            break
    else:
        rows = list(csv.reader(io.StringIO(text)))

    if len(rows) < 2:
        raise HTTPException(400, "Le fichier CSV est vide ou invalide")

    headers = [h.strip() for h in rows[0]]
    data_rows = rows[1:]
    mapping = detect_column_mapping(headers)

    preview = []
    for row in data_rows[:10]:
        entry = {}
        for field, col_idx in mapping.items():
            if col_idx < len(row):
                if field == "amount":
                    entry[field] = parse_amount(row[col_idx])
                elif field == "expense_date":
                    entry[field] = parse_date(row[col_idx])
                else:
                    entry[field] = row[col_idx].strip()
            else:
                entry[field] = "" if field != "amount" else 0
        preview.append(entry)

    return {
        "headers": headers,
        "mapping": {f: {"column_index": idx, "column_name": headers[idx]} for f, idx in mapping.items()},
        "total_rows": len(data_rows),
        "preview": preview,
        "raw_preview": [r for r in data_rows[:5]]
    }

@app.post("/api/expenses/import-confirm")
def import_csv_confirm(import_data: dict, current_user: User = Depends(get_current_user_with_access)):
    rows = import_data.get("rows", [])
    if not rows:
        raise HTTPException(400, "Aucune donnee a importer")
    created = 0
    for row in rows:
        amt = parse_amount(str(row.get("amount", 0)))
        if amt == 0 and not row.get("description"):
            continue
        doc = {
            "id": str(uuid.uuid4()), "user_id": current_user.id,
            "employee_id": row.get("employee_id", ""),
            "description": row.get("description", "Import CSV"),
            "amount": abs(amt),
            "category": row.get("category", ""),
            "expense_date": row.get("expense_date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
            "status": "pending", "receipt_url": "",
            "notes": row.get("notes", ""), "created_at": datetime.now(timezone.utc).isoformat()
        }
        db.expenses.insert_one(doc)
        created += 1
    return {"message": f"{created} depense(s) importee(s)", "created": created}

@app.get("/api/dashboard/expense-analytics")
def get_expense_analytics(current_user: User = Depends(get_current_user_with_access)):
    expenses = list(db.expenses.find({"user_id": current_user.id}, {"_id": 0}))
    by_category = {}
    by_month = {}
    for exp in expenses:
        cat = exp.get("category", "").strip() or "Non classé"
        amt = float(exp.get("amount", 0))
        by_category[cat] = round(by_category.get(cat, 0) + amt, 2)
        raw_date = exp.get("expense_date", "")
        if isinstance(raw_date, datetime):
            month_key = raw_date.strftime("%Y-%m")
        else:
            month_key = str(raw_date)[:7] if raw_date else ""
        if month_key:
            if month_key not in by_month:
                by_month[month_key] = {}
            by_month[month_key][cat] = round(by_month[month_key].get(cat, 0) + amt, 2)
    categories_chart = sorted([{"name": k, "value": v} for k, v in by_category.items()], key=lambda x: -x["value"])
    months_sorted = sorted(by_month.keys())
    all_cats = sorted(by_category.keys())
    monthly_chart = []
    for m in months_sorted:
        entry = {"month": m}
        for cat in all_cats:
            entry[cat] = by_month[m].get(cat, 0)
        entry["total"] = round(sum(by_month[m].values()), 2)
        monthly_chart.append(entry)
    total = round(sum(by_category.values()), 2)
    return {"by_category": categories_chart, "by_month": monthly_chart, "categories": all_cats, "total": total}

# ─── Settings ───
@app.get("/api/settings/company")
def get_settings(current_user: User = Depends(get_current_user_with_access)):
    settings = db.company_settings.find_one({"user_id": current_user.id}, {"_id": 0})
    if not settings:
        default = {
            "id": str(uuid.uuid4()), "user_id": current_user.id,
            "company_name": current_user.company_name, "email": current_user.email,
            "phone": "", "address": "", "city": "", "postal_code": "", "country": "",
            "logo_url": "", "primary_color": "#00A08C", "secondary_color": "#1F2937",
            "default_due_days": 30, "gst_number": "", "pst_number": "", "hst_number": ""
        }
        db.company_settings.insert_one(default)
        return {k: v for k, v in default.items() if k != "_id"}
    return settings

@app.put("/api/settings/company")
def update_settings(settings_data: dict, current_user: User = Depends(get_current_user_with_access)):
    settings_data.pop("_id", None)
    settings_data.pop("user_id", None)
    db.company_settings.update_one({"user_id": current_user.id}, {"$set": settings_data}, upsert=True)
    return clean_doc(db.company_settings.find_one({"user_id": current_user.id}, {"_id": 0}))

@app.post("/api/settings/company/upload-logo")
def upload_logo(logo_data: dict, current_user: User = Depends(get_current_user_with_access)):
    db.company_settings.update_one({"user_id": current_user.id}, {"$set": {"logo_url": logo_data.get("logo_url", "")}}, upsert=True)
    return {"message": "Logo saved", "logo_url": logo_data.get("logo_url", "")}

# ─── File Upload/Download ───
@app.post("/api/upload")
def upload_file(file: UploadFile = File(...), current_user: User = Depends(get_current_user_with_access)):
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp", "application/pdf"]
    if file.content_type not in allowed_types:
        raise HTTPException(400, f"Type de fichier non supporte: {file.content_type}")

    max_size = 5 * 1024 * 1024
    data = file.file.read()
    if len(data) > max_size:
        raise HTTPException(400, "Fichier trop volumineux (max 5 MB)")

    ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
    storage_path = f"{APP_NAME}/uploads/{current_user.id}/{uuid.uuid4()}.{ext}"

    result = put_object(storage_path, data, file.content_type or "application/octet-stream")

    file_doc = {
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "storage_path": result["path"],
        "original_filename": file.filename,
        "content_type": file.content_type,
        "size": result.get("size", len(data)),
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    db.files.insert_one(file_doc)

    return {"file_id": file_doc["id"], "storage_path": result["path"], "filename": file.filename}

@app.get("/api/files/{file_id}")
def download_file(file_id: str):
    record = db.files.find_one({"id": file_id, "is_deleted": False}, {"_id": 0})
    if not record:
        raise HTTPException(404, "File not found")
    data, content_type = get_object(record["storage_path"])
    return Response(content=data, media_type=record.get("content_type", content_type))

@app.post("/api/settings/company/upload-logo-file")
def upload_logo_file(file: UploadFile = File(...), current_user: User = Depends(get_current_user_with_access)):
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(400, "Seules les images sont acceptees (JPG, PNG, GIF, WebP)")

    data = file.file.read()
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(400, "Logo trop volumineux (max 2 MB)")

    ext = file.filename.split(".")[-1] if "." in file.filename else "png"
    storage_path = f"{APP_NAME}/logos/{current_user.id}/{uuid.uuid4()}.{ext}"

    result = put_object(storage_path, data, file.content_type)

    file_doc = {
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "storage_path": result["path"],
        "original_filename": file.filename,
        "content_type": file.content_type,
        "size": result.get("size", len(data)),
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    db.files.insert_one(file_doc)

    logo_url = f"/api/files/{file_doc['id']}"
    db.company_settings.update_one(
        {"user_id": current_user.id},
        {"$set": {"logo_url": logo_url}},
        upsert=True
    )

    return {"message": "Logo televerse avec succes", "logo_url": logo_url, "file_id": file_doc["id"]}

# ─── Dashboard ───
@app.get("/api/dashboard/stats")
def get_stats(current_user: User = Depends(get_current_user_with_access)):
    total_clients = db.clients.count_documents({"user_id": current_user.id})
    total_invoices = db.invoices.count_documents({"user_id": current_user.id})
    total_quotes = db.quotes.count_documents({"user_id": current_user.id})
    total_products = db.products.count_documents({"user_id": current_user.id, "is_active": True})
    total_employees = db.employees.count_documents({"user_id": current_user.id, "is_active": True})
    total_expenses = db.expenses.count_documents({"user_id": current_user.id})
    paid_invoices = list(db.invoices.find({"user_id": current_user.id, "status": "paid"}, {"total": 1, "_id": 0}))
    total_revenue = sum(inv.get("total", 0) for inv in paid_invoices)
    pending_count = db.invoices.count_documents({"user_id": current_user.id, "status": {"$in": ["sent", "overdue"]}})
    return {
        "total_clients": total_clients, "total_invoices": total_invoices,
        "total_quotes": total_quotes, "total_products": total_products,
        "total_employees": total_employees, "total_expenses": total_expenses,
        "total_revenue": round(total_revenue, 2), "pending_invoices": pending_count
    }

@app.get("/api/dashboard/overdue")
def get_overdue_invoices(current_user: User = Depends(get_current_user_with_access)):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    invoices = list(db.invoices.find({"user_id": current_user.id, "status": {"$nin": ["paid"]}}, {"_id": 0}))
    overdue = []
    for inv in invoices:
        raw_due = inv.get("due_date", "")
        if isinstance(raw_due, datetime):
            due = raw_due.strftime("%Y-%m-%d")
        else:
            due = str(raw_due)[:10] if raw_due else ""
        if due and due < today:
            days = (datetime.now(timezone.utc) - datetime.fromisoformat(due + "T00:00:00+00:00")).days
            if inv.get("status") != "overdue":
                db.invoices.update_one({"id": inv["id"]}, {"$set": {"status": "overdue"}})
                inv["status"] = "overdue"
            client = db.clients.find_one({"id": inv.get("client_id"), "user_id": current_user.id}, {"_id": 0})
            overdue.append({
                "id": inv["id"],
                "invoice_number": inv.get("invoice_number", ""),
                "client_name": client.get("name", "Inconnu") if client else "Inconnu",
                "client_email": client.get("email", "") if client else "",
                "total": inv.get("total", 0),
                "due_date": due,
                "days_overdue": days,
                "last_reminded": inv.get("last_reminded", ""),
            })
    overdue.sort(key=lambda x: x["days_overdue"], reverse=True)
    total_overdue = sum(i["total"] for i in overdue)
    return {"overdue_invoices": overdue, "total_overdue": round(total_overdue, 2), "count": len(overdue)}

@app.post("/api/invoices/{invoice_id}/remind")
def send_invoice_reminder(invoice_id: str, body: dict, current_user: User = Depends(get_current_user_with_access)):
    if not RESEND_API_KEY:
        raise HTTPException(500, "Email service not configured")
    invoice = db.invoices.find_one({"id": invoice_id, "user_id": current_user.id}, {"_id": 0})
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    settings = db.company_settings.find_one({"user_id": current_user.id}, {"_id": 0}) or {}
    client_info = db.clients.find_one({"id": invoice.get("client_id"), "user_id": current_user.id}, {"_id": 0})
    to_email = body.get("to_email") or (client_info or {}).get("email")
    if not to_email:
        raise HTTPException(400, "Adresse email du destinataire requise")
    products = list(db.products.find({"user_id": current_user.id}, {"_id": 0}))
    pdf_buffer = generate_document_pdf("invoice", invoice, settings, client_info, products)
    pdf_bytes = pdf_buffer.read()
    pdf_b64 = base64.b64encode(pdf_bytes).decode()
    comp_name = settings.get('company_name', 'FacturePro')
    inv_num = invoice.get('invoice_number', 'N/A')
    due_date = invoice.get('due_date', '')[:10]
    total = invoice.get('total', 0)
    subject = f"Rappel: Facture {inv_num} en retard - {comp_name}"
    message = (f"Bonjour,\n\n"
               f"Nous vous rappelons que la facture {inv_num} d'un montant de {total:.2f} $ "
               f"etait due le {due_date} et reste impayee.\n\n"
               f"Veuillez trouver ci-joint une copie de la facture.\n\n"
               f"Merci de proceder au paiement dans les meilleurs delais.\n\n"
               f"Cordialement,\n{comp_name}")
    params = {
        "from": SENDER_EMAIL,
        "to": [to_email],
        "subject": subject,
        "text": message,
        "attachments": [{"filename": f"facture_{inv_num}.pdf", "content": pdf_b64}]
    }
    try:
        r = resend.Emails.send(params)
        db.invoices.update_one({"id": invoice_id}, {"$set": {"last_reminded": datetime.now(timezone.utc).isoformat()}})
        return {"message": f"Rappel envoye a {to_email}", "email_id": r.get("id") if isinstance(r, dict) else str(r)}
    except Exception as e:
        raise HTTPException(500, f"Erreur envoi rappel: {str(e)}")

# ─── CSV Exports ───
@app.get("/api/export/invoices/csv")
def export_invoices_csv(current_user: User = Depends(get_current_user_with_access)):
    invoices = list(db.invoices.find({"user_id": current_user.id}, {"_id": 0}))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Numero", "Client ID", "Date", "Echeance", "Sous-total", "TPS", "TVQ", "TVH", "Total", "Statut"])
    for inv in invoices:
        writer.writerow([inv.get("invoice_number", ""), inv.get("client_id", ""), inv.get("issue_date", ""),
            inv.get("due_date", ""), inv.get("subtotal", 0), inv.get("gst_amount", 0),
            inv.get("pst_amount", 0), inv.get("hst_amount", 0), inv.get("total", 0), inv.get("status", "")])
    output.seek(0)
    return StreamingResponse(io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv", headers={"Content-Disposition": "attachment; filename=factures.csv"})

@app.get("/api/export/expenses/csv")
def export_expenses_csv(current_user: User = Depends(get_current_user_with_access)):
    expenses = list(db.expenses.find({"user_id": current_user.id}, {"_id": 0}))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Description", "Montant", "Categorie", "Date", "Employe ID", "Statut"])
    for exp in expenses:
        writer.writerow([exp.get("description", ""), exp.get("amount", 0), exp.get("category", ""),
            exp.get("expense_date", ""), exp.get("employee_id", ""), exp.get("status", "")])
    output.seek(0)
    return StreamingResponse(io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv", headers={"Content-Disposition": "attachment; filename=depenses.csv"})


# ─── PDF Generation ───
def generate_document_pdf(doc_type, document, company_settings, client_info, products_list):
    """Generate a professional PDF for a quote or invoice."""
    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch, leftMargin=0.6*inch, rightMargin=0.6*inch)

    styles = getSampleStyleSheet()
    teal = HexColor('#00A08C')
    dark = HexColor('#1f2937')
    gray = HexColor('#6b7280')

    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=28, textColor=teal, spaceAfter=4)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=11, textColor=gray)
    company_style = ParagraphStyle('Company', parent=styles['Normal'], fontSize=10, textColor=dark, leading=14)
    small_style = ParagraphStyle('Small', parent=styles['Normal'], fontSize=9, textColor=gray, leading=12)
    right_style = ParagraphStyle('Right', parent=styles['Normal'], fontSize=10, textColor=dark, alignment=TA_RIGHT)
    terms_style = ParagraphStyle('Terms', parent=styles['Normal'], fontSize=8, textColor=gray, leading=11)

    elements = []

    # Header with company info
    comp_name = company_settings.get('company_name', 'Mon Entreprise')
    comp_email = company_settings.get('email', '')
    comp_phone = company_settings.get('phone', '')
    comp_address = company_settings.get('address', '')
    comp_city = company_settings.get('city', '')

    # Try to load logo
    logo_elem = None
    logo_url = company_settings.get('logo_url', '')
    if logo_url:
        try:
            if logo_url.startswith('/api/files/'):
                file_id = logo_url.split('/')[-1]
                record = db.files.find_one({"id": file_id, "is_deleted": False})
                if record:
                    data, _ = get_object(record["storage_path"])
                    logo_buf = io.BytesIO(data)
                    logo_elem = RLImage(logo_buf, width=1.2*inch, height=1.2*inch)
        except Exception:
            pass

    # Build header table
    left_parts = []
    if logo_elem:
        left_parts.append(logo_elem)
        left_parts.append(Spacer(1, 8))
    left_parts.append(Paragraph(comp_name, ParagraphStyle('CompName', parent=styles['Normal'], fontSize=14, textColor=dark, fontName='Helvetica-Bold', leading=18)))
    left_parts.append(Spacer(1, 4))
    if comp_address:
        left_parts.append(Paragraph(comp_address, small_style))
    if comp_city:
        left_parts.append(Paragraph(comp_city, small_style))
    if comp_email:
        left_parts.append(Paragraph(comp_email, small_style))
    if comp_phone:
        left_parts.append(Paragraph(comp_phone, small_style))

    gst = company_settings.get('gst_number', '')
    pst = company_settings.get('pst_number', '')
    if gst:
        left_parts.append(Paragraph(f"TPS: {gst}", small_style))
    if pst:
        left_parts.append(Paragraph(f"TVQ: {pst}", small_style))

    doc_label = "SOUMISSION" if doc_type == "quote" else "FACTURE"
    doc_number = document.get('quote_number' if doc_type == 'quote' else 'invoice_number', 'N/A')

    right_parts = []
    right_parts.append(Paragraph(doc_label, ParagraphStyle('DocLabel', parent=styles['Normal'], fontSize=20, textColor=teal, alignment=TA_RIGHT, fontName='Helvetica-Bold', spaceAfter=6)))
    right_parts.append(Spacer(1, 4))
    right_parts.append(Paragraph(f"No: {doc_number}", right_style))

    raw_issue = document.get('issue_date', '')
    if isinstance(raw_issue, datetime):
        issue_date = raw_issue.strftime("%Y-%m-%d")
    else:
        issue_date = str(raw_issue)[:10] if raw_issue else ""
    right_parts.append(Paragraph(f"Date: {issue_date}", right_style))

    if doc_type == 'quote':
        raw_valid = document.get('valid_until', '')
        if isinstance(raw_valid, datetime):
            valid = raw_valid.strftime("%Y-%m-%d")
        else:
            valid = str(raw_valid)[:10] if raw_valid else ""
        if valid:
            right_parts.append(Paragraph(f"Valide jusqu'au: {valid}", right_style))
    else:
        raw_due = document.get('due_date', '')
        if isinstance(raw_due, datetime):
            due = raw_due.strftime("%Y-%m-%d")
        else:
            due = str(raw_due)[:10] if raw_due else ""
        if due:
            right_parts.append(Paragraph(f"Echeance: {due}", right_style))

    status_label = document.get('status', '')
    if status_label:
        right_parts.append(Spacer(1, 6))
        right_parts.append(Paragraph(f"Statut: {status_label.upper()}", ParagraphStyle('Status', parent=styles['Normal'], fontSize=10, textColor=teal, alignment=TA_RIGHT, fontName='Helvetica-Bold')))

    header_data = [[left_parts, right_parts]]
    header_table = Table(header_data, colWidths=[3.5*inch, 3.5*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.3*inch))

    # Client info
    client_name = client_info.get('name', 'N/A') if client_info else 'N/A'
    client_email = client_info.get('email', '') if client_info else ''
    client_addr = client_info.get('address', '') if client_info else ''
    client_city = client_info.get('city', '') if client_info else ''
    client_postal = client_info.get('postal_code', '') if client_info else ''

    bill_to = [Paragraph("<b>Facturer a:</b>", company_style)]
    bill_to.append(Spacer(1, 6))
    bill_to.append(Paragraph(client_name, ParagraphStyle('ClientName', parent=styles['Normal'], fontSize=12, textColor=dark, fontName='Helvetica-Bold', leading=16)))
    if client_addr:
        bill_to.append(Spacer(1, 3))
        bill_to.append(Paragraph(client_addr, ParagraphStyle('ClientAddr', parent=small_style, leading=14)))
    if client_city or client_postal:
        bill_to.append(Spacer(1, 3))
        bill_to.append(Paragraph(f"{client_city} {client_postal}".strip(), ParagraphStyle('ClientCity', parent=small_style, leading=14)))
    if client_email:
        bill_to.append(Spacer(1, 3))
        bill_to.append(Paragraph(client_email, ParagraphStyle('ClientEmail', parent=small_style, leading=14)))

    client_table = Table([[bill_to]], colWidths=[7*inch])
    client_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor('#f8fafb')),
        ('BOX', (0, 0), (-1, -1), 0.5, HexColor('#e5e7eb')),
        ('TOPPADDING', (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 14),
        ('LEFTPADDING', (0, 0), (-1, -1), 16),
    ]))
    elements.append(client_table)
    elements.append(Spacer(1, 0.3*inch))

    # Items table
    items = document.get('items', [])
    table_header = ['Description', 'Qte', 'Prix unitaire', 'Total']
    table_data = [table_header]

    for item in items:
        qty = float(item.get('quantity', 1))
        price = float(item.get('unit_price', 0))
        total = qty * price
        table_data.append([
            Paragraph(item.get('description', ''), company_style),
            f"{qty:.2f}",
            f"{price:.2f} $",
            f"{total:.2f} $"
        ])

    items_table = Table(table_data, colWidths=[3.5*inch, 1*inch, 1.5*inch, 1.5*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), teal),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#ffffff')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#e5e7eb')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#ffffff'), HexColor('#f9fafb')]),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 0.2*inch))

    # Totals
    subtotal = document.get('subtotal', 0)
    gst_amt = document.get('gst_amount', 0)
    pst_amt = document.get('pst_amount', 0)
    hst_amt = document.get('hst_amount', 0)
    total = document.get('total', 0)

    totals_data = [['', 'Sous-total:', f"{subtotal:.2f} $"]]
    province = document.get('province', 'QC')
    if province == 'QC':
        if gst_amt:
            totals_data.append(['', 'TPS (5%):', f"{gst_amt:.2f} $"])
        if pst_amt:
            totals_data.append(['', 'TVQ (9.975%):', f"{pst_amt:.2f} $"])
    elif province == 'ON' and hst_amt:
        totals_data.append(['', 'TVH (13%):', f"{hst_amt:.2f} $"])
    totals_data.append(['', 'TOTAL:', f"{total:.2f} $"])

    totals_table = Table(totals_data, colWidths=[4.5*inch, 1.5*inch, 1.5*inch])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (1, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (1, -1), (-1, -1), 12),
        ('TEXTCOLOR', (1, -1), (-1, -1), teal),
        ('LINEABOVE', (1, -1), (-1, -1), 1.5, teal),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(totals_table)

    # Notes
    notes = document.get('notes', '')
    if notes:
        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph("<b>Notes / Commentaires:</b>", company_style))
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(notes, small_style))

    # Terms
    terms = document.get('terms', '')
    if terms:
        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph("<b>Conditions generales:</b>", company_style))
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(terms, terms_style))

    # Footer
    elements.append(Spacer(1, 0.5*inch))
    elements.append(Paragraph(f"Merci pour votre confiance ! — {comp_name}", ParagraphStyle('Footer', parent=styles['Normal'], fontSize=10, textColor=teal, alignment=TA_CENTER)))

    pdf.build(elements)
    buffer.seek(0)
    return buffer

# ─── PDF Endpoints ───
@app.get("/api/quotes/{quote_id}/pdf")
def get_quote_pdf(quote_id: str, current_user: User = Depends(get_current_user_with_access)):
    quote = db.quotes.find_one({"id": quote_id, "user_id": current_user.id}, {"_id": 0})
    if not quote:
        raise HTTPException(404, "Quote not found")
    settings = db.company_settings.find_one({"user_id": current_user.id}, {"_id": 0}) or {}
    client_info = db.clients.find_one({"id": quote.get("client_id"), "user_id": current_user.id}, {"_id": 0})
    products = list(db.products.find({"user_id": current_user.id}, {"_id": 0}))

    pdf_buffer = generate_document_pdf("quote", quote, settings, client_info, products)
    filename = f"soumission_{quote.get('quote_number', 'N-A')}.pdf"
    return StreamingResponse(pdf_buffer, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"})

@app.get("/api/invoices/{invoice_id}/pdf")
def get_invoice_pdf(invoice_id: str, current_user: User = Depends(get_current_user_with_access)):
    invoice = db.invoices.find_one({"id": invoice_id, "user_id": current_user.id}, {"_id": 0})
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    settings = db.company_settings.find_one({"user_id": current_user.id}, {"_id": 0}) or {}
    client_info = db.clients.find_one({"id": invoice.get("client_id"), "user_id": current_user.id}, {"_id": 0})
    products = list(db.products.find({"user_id": current_user.id}, {"_id": 0}))

    pdf_buffer = generate_document_pdf("invoice", invoice, settings, client_info, products)
    filename = f"facture_{invoice.get('invoice_number', 'N-A')}.pdf"
    return StreamingResponse(pdf_buffer, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"})

# ─── Email Sending ───
@app.post("/api/quotes/{quote_id}/send")
def send_quote_email(quote_id: str, body: dict, current_user: User = Depends(get_current_user_with_access)):
    if not RESEND_API_KEY:
        raise HTTPException(500, "Email service not configured")

    quote = db.quotes.find_one({"id": quote_id, "user_id": current_user.id}, {"_id": 0})
    if not quote:
        raise HTTPException(404, "Quote not found")
    settings = db.company_settings.find_one({"user_id": current_user.id}, {"_id": 0}) or {}
    client_info = db.clients.find_one({"id": quote.get("client_id"), "user_id": current_user.id}, {"_id": 0})
    products = list(db.products.find({"user_id": current_user.id}, {"_id": 0}))

    to_email = body.get("to_email") or (client_info or {}).get("email")
    if not to_email:
        raise HTTPException(400, "Adresse email du destinataire requise")

    pdf_buffer = generate_document_pdf("quote", quote, settings, client_info, products)
    pdf_bytes = pdf_buffer.read()
    pdf_b64 = base64.b64encode(pdf_bytes).decode()

    comp_name = settings.get('company_name', 'FacturePro')
    quote_num = quote.get('quote_number', 'N/A')
    subject = body.get("subject", f"Soumission {quote_num} - {comp_name}")
    message = body.get("message", f"Bonjour,\n\nVeuillez trouver ci-joint la soumission {quote_num}.\n\nCordialement,\n{comp_name}")

    params = {
        "from": SENDER_EMAIL,
        "to": [to_email],
        "subject": subject,
        "text": message,
        "attachments": [{"filename": f"soumission_{quote_num}.pdf", "content": pdf_b64}]
    }
    try:
        r = resend.Emails.send(params)
        db.quotes.update_one({"id": quote_id}, {"$set": {"status": "sent", "sent_at": datetime.now(timezone.utc).isoformat(), "sent_to": to_email}})
        return {"message": f"Soumission envoyee a {to_email}", "email_id": r.get("id") if isinstance(r, dict) else str(r)}
    except Exception as e:
        raise HTTPException(500, f"Erreur envoi email: {str(e)}")

@app.post("/api/invoices/{invoice_id}/send")
def send_invoice_email(invoice_id: str, body: dict, current_user: User = Depends(get_current_user_with_access)):
    if not RESEND_API_KEY:
        raise HTTPException(500, "Email service not configured")

    invoice = db.invoices.find_one({"id": invoice_id, "user_id": current_user.id}, {"_id": 0})
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    settings = db.company_settings.find_one({"user_id": current_user.id}, {"_id": 0}) or {}
    client_info = db.clients.find_one({"id": invoice.get("client_id"), "user_id": current_user.id}, {"_id": 0})
    products = list(db.products.find({"user_id": current_user.id}, {"_id": 0}))

    to_email = body.get("to_email") or (client_info or {}).get("email")
    if not to_email:
        raise HTTPException(400, "Adresse email du destinataire requise")

    pdf_buffer = generate_document_pdf("invoice", invoice, settings, client_info, products)
    pdf_bytes = pdf_buffer.read()
    pdf_b64 = base64.b64encode(pdf_bytes).decode()

    comp_name = settings.get('company_name', 'FacturePro')
    inv_num = invoice.get('invoice_number', 'N/A')
    subject = body.get("subject", f"Facture {inv_num} - {comp_name}")
    message = body.get("message", f"Bonjour,\n\nVeuillez trouver ci-joint la facture {inv_num}.\n\nCordialement,\n{comp_name}")

    params = {
        "from": SENDER_EMAIL,
        "to": [to_email],
        "subject": subject,
        "text": message,
        "attachments": [{"filename": f"facture_{inv_num}.pdf", "content": pdf_b64}]
    }
    try:
        r = resend.Emails.send(params)
        db.invoices.update_one({"id": invoice_id}, {"$set": {"status": "sent", "sent_at": datetime.now(timezone.utc).isoformat(), "sent_to": to_email}})
        return {"message": f"Facture envoyee a {to_email}", "email_id": r.get("id") if isinstance(r, dict) else str(r)}
    except Exception as e:
        raise HTTPException(500, f"Erreur envoi email: {str(e)}")


# ─── Stripe Subscription ───
@app.get("/api/subscription/current")
def get_subscription(current_user: User = Depends(get_current_user_with_access)):
    user_doc = db.users.find_one({"id": current_user.id}, {"_id": 0})
    sub_status = user_doc.get("subscription_status", "trial")
    trial_end = user_doc.get("trial_end_date")
    is_exempt = user_doc.get("email") in EXEMPT_USERS
    if sub_status == "trial" and trial_end and not is_exempt:
        try:
            trial_end_dt = datetime.fromisoformat(trial_end)
            if datetime.now(timezone.utc) > trial_end_dt:
                sub_status = "expired"
        except Exception:
            pass
    last_tx = db.payment_transactions.find_one(
        {"user_id": current_user.id, "payment_status": "paid"},
        {"_id": 0},
        sort=[("created_at", -1)]
    )
    return {
        "subscription_status": "active" if is_exempt else sub_status,
        "trial_end_date": trial_end,
        "is_exempt": is_exempt,
        "last_payment": last_tx
    }


@app.post("/api/subscription/create-checkout")
async def create_subscription_checkout(body: dict, request: Request, current_user: User = Depends(get_current_user_with_access)):
    if not STRIPE_API_KEY:
        raise HTTPException(500, "Stripe non configure")
    origin_url = body.get("origin_url", "")
    if not origin_url:
        raise HTTPException(400, "origin_url requis")
    success_url = f"{origin_url}/subscription?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin_url}/subscription"
    host_url = str(request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    checkout_request = CheckoutSessionRequest(
        amount=SUBSCRIPTION_PRICE_CAD,
        currency="cad",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "user_id": current_user.id,
            "email": current_user.email,
            "plan": "facturepro_monthly"
        }
    )
    session = await stripe_checkout.create_checkout_session(checkout_request)
    tx_doc = {
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "session_id": session.session_id,
        "amount": SUBSCRIPTION_PRICE_CAD,
        "currency": "cad",
        "payment_status": "pending",
        "status": "initiated",
        "metadata": {"plan": "facturepro_monthly", "email": current_user.email},
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    db.payment_transactions.insert_one(tx_doc)
    return {"url": session.url, "session_id": session.session_id}


@app.get("/api/subscription/checkout-status/{session_id}")
async def check_subscription_status(session_id: str, request: Request, current_user: User = Depends(get_current_user_with_access)):
    if not STRIPE_API_KEY:
        raise HTTPException(500, "Stripe non configure")
    host_url = str(request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    checkout_status = await stripe_checkout.get_checkout_status(session_id)
    tx = db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if tx and tx.get("payment_status") != "paid" and checkout_status.payment_status == "paid":
        db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {
                "payment_status": "paid",
                "status": "complete",
                "paid_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        db.users.update_one(
            {"id": current_user.id},
            {"$set": {
                "subscription_status": "active",
                "subscription_started_at": datetime.now(timezone.utc).isoformat()
            }}
        )
    return {
        "status": checkout_status.status,
        "payment_status": checkout_status.payment_status,
        "amount_total": checkout_status.amount_total,
        "currency": checkout_status.currency
    }


@app.post("/api/webhook/stripe")
async def stripe_webhook(request: Request):
    if not STRIPE_API_KEY:
        raise HTTPException(500, "Stripe non configure")
    body = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    host_url = str(request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    try:
        stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
        event = await stripe_checkout.handle_webhook(body, sig)
        if event.payment_status == "paid":
            tx = db.payment_transactions.find_one({"session_id": event.session_id}, {"_id": 0})
            if tx and tx.get("payment_status") != "paid":
                db.payment_transactions.update_one(
                    {"session_id": event.session_id},
                    {"$set": {"payment_status": "paid", "status": "complete", "paid_at": datetime.now(timezone.utc).isoformat()}}
                )
                user_id = tx.get("user_id") or (event.metadata or {}).get("user_id")
                if user_id:
                    db.users.update_one(
                        {"id": user_id},
                        {"$set": {"subscription_status": "active", "subscription_started_at": datetime.now(timezone.utc).isoformat()}}
                    )
        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}


# ─── Startup Seed ───
@app.on_event("startup")
def seed_data():
    try:
        client.admin.command('ping')
        print("MongoDB connected successfully")

        # Create indexes for faster queries
        db.users.create_index("email", unique=True)
        db.users.create_index("id", unique=True)
        db.user_passwords.create_index("user_id", unique=True)
        db.clients.create_index([("user_id", 1)])
        db.products.create_index([("user_id", 1), ("is_active", 1)])
        db.invoices.create_index([("user_id", 1)])
        db.quotes.create_index([("user_id", 1)])
        db.employees.create_index([("user_id", 1), ("is_active", 1)])
        db.expenses.create_index([("user_id", 1)])
        db.company_settings.create_index("user_id", unique=True)
        db.files.create_index("id", unique=True)
        db.payment_transactions.create_index("session_id", unique=True)
        db.payment_transactions.create_index([("user_id", 1)])
        print("Database indexes created")

        try:
            init_storage()
            print("Object storage initialized")
        except Exception as e:
            print(f"Storage init warning (uploads disabled): {e}")

        existing = db.users.find_one({"email": "gussdub@gmail.com"})
        if existing:
            uid = existing["id"]
            pwd_doc = db.user_passwords.find_one({"user_id": uid})
            if not pwd_doc:
                db.user_passwords.insert_one({"user_id": uid, "hashed_password": hash_password("testpass123")})
                print("Created missing password for gussdub@gmail.com")
            elif not verify_password("testpass123", pwd_doc["hashed_password"]):
                db.user_passwords.update_one({"user_id": uid}, {"$set": {"hashed_password": hash_password("testpass123")}})
                print("Fixed password for gussdub@gmail.com")
            print("gussdub@gmail.com ready")
        else:
            user_id = str(uuid.uuid4())
            trial_end = (datetime.now(timezone.utc) + timedelta(days=3650)).isoformat()
            db.users.insert_one({
                "id": user_id, "email": "gussdub@gmail.com", "company_name": "ProFireManager",
                "is_active": True, "subscription_status": "trial", "trial_end_date": trial_end,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            db.user_passwords.insert_one({"user_id": user_id, "hashed_password": hash_password("testpass123")})
            db.company_settings.insert_one({
                "id": str(uuid.uuid4()), "user_id": user_id,
                "company_name": "ProFireManager", "email": "gussdub@gmail.com",
                "phone": "", "address": "", "city": "", "postal_code": "", "country": "Canada",
                "logo_url": "", "primary_color": "#00A08C", "secondary_color": "#1F2937",
                "default_due_days": 30, "gst_number": "123456789", "pst_number": "1234567890", "hst_number": ""
            })
            db.clients.insert_one({
                "id": str(uuid.uuid4()), "user_id": user_id,
                "name": "Client Test", "email": "test@client.com", "phone": "514-123-4567",
                "address": "123 Rue Test", "city": "Montreal", "postal_code": "H1A 1A1",
                "country": "Canada", "created_at": datetime.now(timezone.utc).isoformat()
            })
            db.products.insert_one({
                "id": str(uuid.uuid4()), "user_id": user_id,
                "name": "Consultation", "description": "Consultation professionnelle",
                "unit_price": 100.0, "unit": "heure", "category": "Services",
                "is_active": True, "created_at": datetime.now(timezone.utc).isoformat()
            })
            print("Seeded gussdub@gmail.com account with sample data")
    except Exception as e:
        print(f"Startup error: {e}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
