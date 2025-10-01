from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, File, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import jwt
from enum import Enum
import asyncio
from bson import ObjectId
import hashlib
import secrets
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionResponse, CheckoutStatusResponse, CheckoutSessionRequest
from fastapi import Request

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]  # Use database name from environment

# Stripe configuration
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY')

# Security
security = HTTPBearer()
SECRET_KEY = os.environ.get("JWT_SECRET", "votre-cle-secrete-jwt-changez-en-production")
ALGORITHM = "HS256"

# Create the main app
app = FastAPI(title="Logiciel de Facturation", version="1.0.0")
api_router = APIRouter(prefix="/api")

# Enums
class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"

class RecurrenceType(str, Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    CUSTOM = "custom"

# Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    hashed_password: str
    company_name: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Subscription fields
    subscription_status: str = "trial"  # trial, active, inactive, cancelled
    trial_end_date: Optional[datetime] = None
    subscription_id: Optional[str] = None
    current_period_end: Optional[datetime] = None
    last_payment_date: Optional[datetime] = None

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    company_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class UserResponse(BaseModel):
    id: str
    email: str
    company_name: str
    is_active: bool
    created_at: datetime

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class Client(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ClientCreate(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None

class InvoiceItem(BaseModel):
    description: str
    quantity: float = 1.0
    unit_price: float
    total: float

class InvoiceItemCreate(BaseModel):
    description: str
    quantity: float = 1.0
    unit_price: float

class TaxConfig(BaseModel):
    gst_rate: float = 5.0  # GST fédérale 5%
    pst_rate: float = 0.0  # PST provinciale (varie selon province)
    hst_rate: float = 0.0  # HST (certaines provinces)
    apply_gst: bool = True
    apply_pst: bool = False
    apply_hst: bool = False

class Product(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    name: str
    description: str
    unit_price: float
    unit: str = "unité"  # unité, heure, kg, etc.
    category: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ProductCreate(BaseModel):
    name: str
    description: str
    unit_price: float
    unit: str = "unité"
    category: Optional[str] = None

class PaymentInfo(BaseModel):
    payment_date: datetime
    payment_method: str  # virement, cheque, argent, interac, carte
    amount_paid: float
    notes: Optional[str] = None

class Invoice(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    client_id: str
    invoice_number: str
    issue_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    due_date: datetime
    items: List[InvoiceItem] = []
    subtotal: float = 0.0
    gst_rate: float = 5.0
    pst_rate: float = 0.0
    hst_rate: float = 0.0
    gst_amount: float = 0.0
    pst_amount: float = 0.0
    hst_amount: float = 0.0
    total_tax: float = 0.0
    total: float = 0.0
    apply_gst: bool = True
    apply_pst: bool = False
    apply_hst: bool = False
    status: InvoiceStatus = InvoiceStatus.DRAFT
    payment_info: Optional[PaymentInfo] = None
    notes: Optional[str] = None
    province: str = "QC"  # Province par défaut Québec
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class InvoiceCreate(BaseModel):
    client_id: str
    due_date: Optional[datetime] = None  # Optionnel, utilise default_due_days si non fourni
    invoice_number: Optional[str] = None  # Optionnel, auto-généré si non fourni
    items: List[InvoiceItemCreate]
    gst_rate: float = 5.0
    pst_rate: float = 9.975  # TVQ Québec par défaut
    hst_rate: float = 0.0
    apply_gst: bool = True
    apply_pst: bool = True
    apply_hst: bool = False
    province: str = "QC"
    notes: Optional[str] = None

class Quote(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    client_id: str
    quote_number: str
    issue_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    valid_until: datetime
    items: List[InvoiceItem] = []
    subtotal: float = 0.0
    gst_rate: float = 5.0
    pst_rate: float = 0.0
    hst_rate: float = 0.0
    gst_amount: float = 0.0
    pst_amount: float = 0.0
    hst_amount: float = 0.0
    total_tax: float = 0.0
    total: float = 0.0
    apply_gst: bool = True
    apply_pst: bool = False
    apply_hst: bool = False
    province: str = "QC"
    status: str = "pending"  # pending, accepted, rejected, expired
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class QuoteCreate(BaseModel):
    client_id: str
    valid_until: datetime
    quote_number: Optional[str] = None  # Optionnel, auto-généré si non fourni
    items: List[InvoiceItemCreate]
    gst_rate: float = 5.0
    pst_rate: float = 9.975  # TVQ Québec par défaut
    hst_rate: float = 0.0
    apply_gst: bool = True
    apply_pst: bool = True
    apply_hst: bool = False
    province: str = "QC"
    notes: Optional[str] = None

class RecurringInvoice(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    client_id: str
    template_invoice_id: str
    recurrence_type: RecurrenceType
    recurrence_interval: int = 1  # every X weeks/months/etc
    start_date: datetime
    end_date: Optional[datetime] = None
    next_invoice_date: datetime
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class RecurringInvoiceCreate(BaseModel):
    client_id: str
    template_invoice_id: str
    recurrence_type: RecurrenceType
    recurrence_interval: int = 1
    start_date: datetime
    end_date: Optional[datetime] = None

class CompanySettings(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
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
    default_due_days: int = 30  # Jours d'échéance par défaut
    next_invoice_number: int = 1
    next_quote_number: int = 1
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CompanySettingsUpdate(BaseModel):
    company_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    default_due_days: Optional[int] = None

# Utility functions
def get_password_hash(password):
    # Generate salt and hash with PBKDF2
    salt = secrets.token_hex(32)
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return salt + password_hash.hex()

def verify_password(plain_password, hashed_password):
    # Extract salt and verify password
    salt = hashed_password[:64]
    stored_hash = hashed_password[64:]
    password_hash = hashlib.pbkdf2_hmac('sha256', plain_password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return password_hash.hex() == stored_hash

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    
    user = await db.users.find_one({"id": user_id})
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return User(**user)

async def check_subscription_access(user: User):
    """Check if user has valid subscription access"""
    
    # Exempt users (always free access)
    EXEMPT_USERS = ["gussdub@gmail.com"]
    if user.email in EXEMPT_USERS:
        return True  # Always grant access to exempt users
    
    now = datetime.now(timezone.utc)
    
    # If user is in trial period
    if user.subscription_status == "trial":
        if user.trial_end_date:
            # Ensure both datetimes are timezone-aware for comparison
            trial_end = user.trial_end_date
            if trial_end.tzinfo is None:
                trial_end = trial_end.replace(tzinfo=timezone.utc)
            if now < trial_end:
                return True  # Trial is still valid
            else:
                # Trial has expired, check if they have an active subscription
                await db.users.update_one(
                    {"id": user.id}, 
                    {"$set": {"subscription_status": "inactive", "is_active": False}}
                )
                return False
    
    # If user has active subscription
    if user.subscription_status == "active":
        if user.current_period_end:
            # Ensure both datetimes are timezone-aware for comparison
            period_end = user.current_period_end
            if period_end.tzinfo is None:
                period_end = period_end.replace(tzinfo=timezone.utc)
            if now < period_end:
                return True  # Subscription is active
            else:
                # Subscription period ended, deactivate account
                await db.users.update_one(
                    {"id": user.id}, 
                    {"$set": {"subscription_status": "inactive", "is_active": False}}
                )
                return False
    
    # If user has been cancelled but period not ended
    if user.subscription_status == "cancelled":
        if user.current_period_end:
            # Ensure both datetimes are timezone-aware for comparison
            period_end = user.current_period_end
            if period_end.tzinfo is None:
                period_end = period_end.replace(tzinfo=timezone.utc)
            if now < period_end:
                return True  # Still has access until end of paid period
            else:
                await db.users.update_one(
                    {"id": user.id}, 
                    {"$set": {"subscription_status": "inactive", "is_active": False}}
                )
                return False
    
    return False  # No valid access

async def get_current_user_with_subscription(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user and check subscription access"""
    user = await get_current_user(credentials)
    
    # Check subscription access
    has_access = await check_subscription_access(user)
    if not has_access:
        raise HTTPException(
            status_code=403, 
            detail="Votre abonnement a expiré. Veuillez renouveler votre abonnement pour continuer à utiliser FacturePro."
        )
    
    return user

def calculate_invoice_totals(items: List[InvoiceItemCreate], gst_rate: float = 5.0, pst_rate: float = 0.0, 
                          hst_rate: float = 0.0, apply_gst: bool = True, apply_pst: bool = False, apply_hst: bool = False):
    invoice_items = []
    subtotal = 0.0
    
    for item in items:
        total = item.quantity * item.unit_price
        subtotal += total
        invoice_items.append(InvoiceItem(
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total=total
        ))
    
    # Calculate Canadian taxes
    gst_amount = subtotal * (gst_rate / 100) if apply_gst else 0.0
    pst_amount = subtotal * (pst_rate / 100) if apply_pst else 0.0
    hst_amount = subtotal * (hst_rate / 100) if apply_hst else 0.0
    
    total_tax = gst_amount + pst_amount + hst_amount
    total = subtotal + total_tax
    
    return invoice_items, subtotal, gst_amount, pst_amount, hst_amount, total_tax, total

async def generate_invoice_number(user_id: str, custom_number: Optional[str] = None):
    if custom_number:
        return custom_number
    
    # Get company settings for next number
    settings = await db.company_settings.find_one({"user_id": user_id})
    if settings and "next_invoice_number" in settings:
        next_num = settings["next_invoice_number"]
    else:
        # Fallback: count existing invoices
        count = await db.invoices.count_documents({"user_id": user_id})
        next_num = count + 1
    
    # Update next number in settings
    await db.company_settings.update_one(
        {"user_id": user_id},
        {"$inc": {"next_invoice_number": 1}},
        upsert=True
    )
    
    return f"INV-{next_num:05d}"

async def generate_quote_number(user_id: str, custom_number: Optional[str] = None):
    if custom_number:
        return custom_number
    
    # Get company settings for next number
    settings = await db.company_settings.find_one({"user_id": user_id})
    if settings and "next_quote_number" in settings:
        next_num = settings["next_quote_number"]
    else:
        # Fallback: count existing quotes
        count = await db.quotes.count_documents({"user_id": user_id})
        next_num = count + 1
    
    # Update next number in settings
    await db.company_settings.update_one(
        {"user_id": user_id},
        {"$inc": {"next_quote_number": 1}},
        upsert=True
    )
    
    return f"QTE-{next_num:05d}"

# Authentication routes
@api_router.post("/auth/register", response_model=Token)
async def register(user: UserCreate):
    # Check if user already exists
    existing_user = await db.users.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Calculate trial end date (14 days from now)
    trial_end = datetime.now(timezone.utc) + timedelta(days=14)
    
    # Create new user with trial setup
    hashed_password = get_password_hash(user.password)
    new_user = User(
        email=user.email,
        hashed_password=hashed_password,
        company_name=user.company_name,
        subscription_status="trial",
        trial_end_date=trial_end
    )
    
    # Save to database
    await db.users.insert_one(new_user.dict())
    
    # Create default company settings
    company_settings = CompanySettings(
        user_id=new_user.id,
        company_name=user.company_name,
        email=user.email,
        default_due_days=30,
        next_invoice_number=1,
        next_quote_number=1
    )
    await db.company_settings.insert_one(company_settings.dict())
    
    # Create access token
    access_token = create_access_token(data={"sub": new_user.id})
    user_response = UserResponse(**new_user.dict())
    
    return Token(access_token=access_token, user=user_response)

@api_router.post("/auth/login", response_model=Token)
async def login(user_credentials: UserLogin):
    user = await db.users.find_one({"email": user_credentials.email})
    if not user or not verify_password(user_credentials.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    access_token = create_access_token(data={"sub": user["id"]})
    user_response = UserResponse(**user)
    
    return Token(access_token=access_token, user=user_response)

@api_router.put("/auth/change-password")
async def change_password(password_data: PasswordChange, current_user: User = Depends(get_current_user)):
    # Verify current password
    user = await db.users.find_one({"id": current_user.id})
    if not user or not verify_password(password_data.current_password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")
    
    # Hash new password
    new_hashed_password = get_password_hash(password_data.new_password)
    
    # Update password
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {"hashed_password": new_hashed_password}}
    )
    
    return {"message": "Mot de passe modifié avec succès"}

@api_router.post("/auth/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    # Find user by email
    user = await db.users.find_one({"email": request.email})
    if not user:
        # For security, don't reveal if email exists or not
        return {"message": "Si cette adresse email existe, un code de récupération a été généré"}
    
    # Generate reset token (simple approach - in production, use time-limited tokens)
    reset_token = secrets.token_urlsafe(32)
    
    # Store reset token in user document (expires in 1 hour)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    await db.users.update_one(
        {"email": request.email},
        {
            "$set": {
                "reset_token": reset_token,
                "reset_token_expires": expires_at
            }
        }
    )
    
    # In a real app, you'd send this by email. For now, return it directly
    return {
        "message": "Code de récupération généré",
        "reset_token": reset_token
    }

@api_router.post("/auth/reset-password")
async def reset_password(request: ResetPasswordRequest):
    # Find user with valid reset token
    user = await db.users.find_one({
        "reset_token": request.token,
        "reset_token_expires": {"$gt": datetime.now(timezone.utc)}
    })
    
    if not user:
        raise HTTPException(status_code=400, detail="Code de récupération invalide ou expiré")
    
    # Hash new password
    new_hashed_password = get_password_hash(request.new_password)
    
    # Update password and remove reset token
    await db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {"hashed_password": new_hashed_password},
            "$unset": {"reset_token": "", "reset_token_expires": ""}
        }
    )
    
    return {"message": "Mot de passe réinitialisé avec succès"}

# Client routes
@api_router.get("/clients", response_model=List[Client])
async def get_clients(current_user: User = Depends(get_current_user_with_subscription)):
    clients = await db.clients.find({"user_id": current_user.id}).to_list(1000)
    return [Client(**client) for client in clients]

@api_router.post("/clients", response_model=Client)
async def create_client(client: ClientCreate, current_user: User = Depends(get_current_user_with_subscription)):
    new_client = Client(**client.dict(), user_id=current_user.id)
    await db.clients.insert_one(new_client.dict())
    return new_client

@api_router.get("/clients/{client_id}", response_model=Client)
async def get_client(client_id: str, current_user: User = Depends(get_current_user_with_subscription)):
    client = await db.clients.find_one({"id": client_id, "user_id": current_user.id})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return Client(**client)

@api_router.put("/clients/{client_id}", response_model=Client)
async def update_client(client_id: str, client_update: ClientCreate, current_user: User = Depends(get_current_user_with_subscription)):
    client = await db.clients.find_one({"id": client_id, "user_id": current_user.id})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    update_data = client_update.dict()
    await db.clients.update_one({"id": client_id}, {"$set": update_data})
    
    updated_client = await db.clients.find_one({"id": client_id})
    return Client(**updated_client)

@api_router.delete("/clients/{client_id}")
async def delete_client(client_id: str, current_user: User = Depends(get_current_user_with_subscription)):
    result = await db.clients.delete_one({"id": client_id, "user_id": current_user.id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"message": "Client deleted successfully"}

# Invoice routes
@api_router.get("/invoices", response_model=List[Invoice])
async def get_invoices(current_user: User = Depends(get_current_user_with_subscription)):
    invoices = await db.invoices.find({"user_id": current_user.id}).to_list(1000)
    return [Invoice(**invoice) for invoice in invoices]

@api_router.post("/invoices", response_model=Invoice)
async def create_invoice(invoice: InvoiceCreate, current_user: User = Depends(get_current_user_with_subscription)):
    # Calculate totals with Canadian taxes
    items, subtotal, gst_amount, pst_amount, hst_amount, total_tax, total = calculate_invoice_totals(
        invoice.items, invoice.gst_rate, invoice.pst_rate, invoice.hst_rate,
        invoice.apply_gst, invoice.apply_pst, invoice.apply_hst
    )
    
    # Generate invoice number (custom or auto)
    invoice_number = await generate_invoice_number(current_user.id, invoice.invoice_number)
    
    # Handle due date - use provided or default from settings
    due_date = invoice.due_date
    if not due_date:
        settings = await db.company_settings.find_one({"user_id": current_user.id})
        default_days = settings.get("default_due_days", 30) if settings else 30
        due_date = datetime.now(timezone.utc) + timedelta(days=default_days)
    
    new_invoice = Invoice(
        user_id=current_user.id,
        client_id=invoice.client_id,
        invoice_number=invoice_number,
        due_date=due_date,
        items=items,
        subtotal=subtotal,
        gst_rate=invoice.gst_rate,
        pst_rate=invoice.pst_rate,
        hst_rate=invoice.hst_rate,
        gst_amount=gst_amount,
        pst_amount=pst_amount,
        hst_amount=hst_amount,
        total_tax=total_tax,
        total=total,
        apply_gst=invoice.apply_gst,
        apply_pst=invoice.apply_pst,
        apply_hst=invoice.apply_hst,
        province=invoice.province,
        notes=invoice.notes
    )
    
    await db.invoices.insert_one(new_invoice.dict())
    return new_invoice

@api_router.get("/invoices/{invoice_id}", response_model=Invoice)
async def get_invoice(invoice_id: str, current_user: User = Depends(get_current_user_with_subscription)):
    invoice = await db.invoices.find_one({"id": invoice_id, "user_id": current_user.id})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return Invoice(**invoice)

@api_router.put("/invoices/{invoice_id}", response_model=Invoice)
async def update_invoice(invoice_id: str, invoice_update: InvoiceCreate, current_user: User = Depends(get_current_user_with_subscription)):
    invoice = await db.invoices.find_one({"id": invoice_id, "user_id": current_user.id})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Calculate totals with Canadian taxes
    items, subtotal, gst_amount, pst_amount, hst_amount, total_tax, total = calculate_invoice_totals(
        invoice_update.items, invoice_update.gst_rate, invoice_update.pst_rate, invoice_update.hst_rate,
        invoice_update.apply_gst, invoice_update.apply_pst, invoice_update.apply_hst
    )
    
    update_data = {
        "client_id": invoice_update.client_id,
        "due_date": invoice_update.due_date,
        "items": [item.dict() for item in items],
        "subtotal": subtotal,
        "gst_rate": invoice_update.gst_rate,
        "pst_rate": invoice_update.pst_rate,
        "hst_rate": invoice_update.hst_rate,
        "gst_amount": gst_amount,
        "pst_amount": pst_amount,
        "hst_amount": hst_amount,
        "total_tax": total_tax,
        "total": total,
        "apply_gst": invoice_update.apply_gst,
        "apply_pst": invoice_update.apply_pst,
        "apply_hst": invoice_update.apply_hst,
        "province": invoice_update.province,
        "notes": invoice_update.notes
    }
    
    await db.invoices.update_one({"id": invoice_id}, {"$set": update_data})
    updated_invoice = await db.invoices.find_one({"id": invoice_id})
    return Invoice(**updated_invoice)

class PaymentUpdate(BaseModel):
    status: InvoiceStatus
    payment_date: Optional[datetime] = None
    payment_method: Optional[str] = None
    amount_paid: Optional[float] = None
    payment_notes: Optional[str] = None

# Subscription and Payment Models
class SubscriptionStatus(str, Enum):
    active = "active"
    trial = "trial"
    canceled = "canceled"
    past_due = "past_due"
    suspended = "suspended"

class SubscriptionPlan(str, Enum):
    monthly = "monthly"
    annual = "annual"

class Subscription(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    plan: SubscriptionPlan
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    trial_end: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    canceled_at: Optional[datetime] = None
    stripe_subscription_id: Optional[str] = None

class PaymentTransaction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    session_id: str
    payment_id: Optional[str] = None
    amount: float
    currency: str = "usd"
    status: str = "initiated"  # initiated, pending, paid, failed, expired
    payment_status: str = "unpaid"  # unpaid, paid, failed
    metadata: Optional[dict] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CheckoutRequest(BaseModel):
    plan: SubscriptionPlan

@api_router.put("/invoices/{invoice_id}/status")
async def update_invoice_status(invoice_id: str, payment_data: PaymentUpdate, current_user: User = Depends(get_current_user_with_subscription)):
    invoice = await db.invoices.find_one({"id": invoice_id, "user_id": current_user.id})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    update_data = {"status": payment_data.status.value}
    
    # If marking as paid, add payment info
    if payment_data.status == InvoiceStatus.PAID and payment_data.payment_date:
        payment_info = PaymentInfo(
            payment_date=payment_data.payment_date,
            payment_method=payment_data.payment_method or "non_specifie",
            amount_paid=payment_data.amount_paid or invoice["total"],
            notes=payment_data.payment_notes
        )
        update_data["payment_info"] = payment_info.dict()
    
    result = await db.invoices.update_one(
        {"id": invoice_id, "user_id": current_user.id},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {"message": "Invoice status updated successfully"}

@api_router.delete("/invoices/{invoice_id}")
async def delete_invoice(invoice_id: str, current_user: User = Depends(get_current_user_with_subscription)):
    result = await db.invoices.delete_one({"id": invoice_id, "user_id": current_user.id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {"message": "Invoice deleted successfully"}

# Quote routes
@api_router.get("/quotes", response_model=List[Quote])
async def get_quotes(current_user: User = Depends(get_current_user_with_subscription)):
    quotes = await db.quotes.find({"user_id": current_user.id}).to_list(1000)
    return [Quote(**quote) for quote in quotes]

@api_router.post("/quotes", response_model=Quote)
async def create_quote(quote: QuoteCreate, current_user: User = Depends(get_current_user_with_subscription)):
    # Calculate totals with Canadian taxes
    items, subtotal, gst_amount, pst_amount, hst_amount, total_tax, total = calculate_invoice_totals(
        quote.items, quote.gst_rate, quote.pst_rate, quote.hst_rate,
        quote.apply_gst, quote.apply_pst, quote.apply_hst
    )
    
    # Generate quote number (custom or auto)
    quote_number = await generate_quote_number(current_user.id, quote.quote_number)
    
    new_quote = Quote(
        user_id=current_user.id,
        client_id=quote.client_id,
        quote_number=quote_number,
        valid_until=quote.valid_until,
        items=items,
        subtotal=subtotal,
        gst_rate=quote.gst_rate,
        pst_rate=quote.pst_rate,
        hst_rate=quote.hst_rate,
        gst_amount=gst_amount,
        pst_amount=pst_amount,
        hst_amount=hst_amount,
        total_tax=total_tax,
        total=total,
        apply_gst=quote.apply_gst,
        apply_pst=quote.apply_pst,
        apply_hst=quote.apply_hst,
        province=quote.province,
        notes=quote.notes
    )
    
    await db.quotes.insert_one(new_quote.dict())
    return new_quote

@api_router.post("/quotes/{quote_id}/convert", response_model=Invoice)
async def convert_quote_to_invoice(quote_id: str, due_date: datetime, current_user: User = Depends(get_current_user_with_subscription)):
    quote = await db.quotes.find_one({"id": quote_id, "user_id": current_user.id})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    quote_obj = Quote(**quote)
    
    # Generate invoice number
    invoice_number = await generate_invoice_number(current_user.id)
    
    # Create invoice from quote
    new_invoice = Invoice(
        user_id=current_user.id,
        client_id=quote_obj.client_id,
        invoice_number=invoice_number,
        due_date=due_date,
        items=quote_obj.items,
        subtotal=quote_obj.subtotal,
        gst_rate=quote_obj.gst_rate,
        pst_rate=quote_obj.pst_rate,
        hst_rate=quote_obj.hst_rate,
        gst_amount=quote_obj.gst_amount,
        pst_amount=quote_obj.pst_amount,
        hst_amount=quote_obj.hst_amount,
        total_tax=quote_obj.total_tax,
        total=quote_obj.total,
        apply_gst=quote_obj.apply_gst,
        apply_pst=quote_obj.apply_pst,
        apply_hst=quote_obj.apply_hst,
        province=quote_obj.province,
        notes=quote_obj.notes
    )
    
    await db.invoices.insert_one(new_invoice.dict())
    
    # Update quote status
    await db.quotes.update_one({"id": quote_id}, {"$set": {"status": "accepted"}})
    
    return new_invoice

@api_router.delete("/quotes/{quote_id}")
async def delete_quote(quote_id: str, current_user: User = Depends(get_current_user_with_subscription)):
    result = await db.quotes.delete_one({"id": quote_id, "user_id": current_user.id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Quote not found")
    return {"message": "Quote deleted successfully"}

# Company settings routes
@api_router.get("/settings/company", response_model=CompanySettings)
async def get_company_settings(current_user: User = Depends(get_current_user_with_subscription)):
    settings = await db.company_settings.find_one({"user_id": current_user.id})
    if not settings:
        # Create default settings
        settings = CompanySettings(
            user_id=current_user.id,
            company_name=current_user.company_name,
            email=current_user.email,
            default_due_days=30,
            next_invoice_number=1,
            next_quote_number=1
        )
        await db.company_settings.insert_one(settings.dict())
    return CompanySettings(**settings)

@api_router.put("/settings/company", response_model=CompanySettings)
async def update_company_settings(settings_update: CompanySettingsUpdate, current_user: User = Depends(get_current_user_with_subscription)):
    settings = await db.company_settings.find_one({"user_id": current_user.id})
    if not settings:
        raise HTTPException(status_code=404, detail="Company settings not found")
    
    update_data = {k: v for k, v in settings_update.dict().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    await db.company_settings.update_one({"user_id": current_user.id}, {"$set": update_data})
    updated_settings = await db.company_settings.find_one({"user_id": current_user.id})
    return CompanySettings(**updated_settings)

# Product routes
@api_router.get("/products", response_model=List[Product])
async def get_products(current_user: User = Depends(get_current_user_with_subscription)):
    products = await db.products.find({"user_id": current_user.id, "is_active": True}).to_list(1000)
    return [Product(**product) for product in products]

@api_router.post("/products", response_model=Product)
async def create_product(product: ProductCreate, current_user: User = Depends(get_current_user_with_subscription)):
    new_product = Product(**product.dict(), user_id=current_user.id)
    await db.products.insert_one(new_product.dict())
    return new_product

@api_router.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: str, current_user: User = Depends(get_current_user_with_subscription)):
    product = await db.products.find_one({"id": product_id, "user_id": current_user.id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return Product(**product)

@api_router.put("/products/{product_id}", response_model=Product)
async def update_product(product_id: str, product_update: ProductCreate, current_user: User = Depends(get_current_user_with_subscription)):
    product = await db.products.find_one({"id": product_id, "user_id": current_user.id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    update_data = product_update.dict()
    await db.products.update_one({"id": product_id}, {"$set": update_data})
    
    updated_product = await db.products.find_one({"id": product_id})
    return Product(**updated_product)

@api_router.delete("/products/{product_id}")
async def delete_product(product_id: str, current_user: User = Depends(get_current_user_with_subscription)):
    result = await db.products.update_one(
        {"id": product_id, "user_id": current_user.id}, 
        {"$set": {"is_active": False}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Product deleted successfully"}

# Export routes
@api_router.get("/export/statistics")
async def export_statistics(
    start_date: str = None,
    end_date: str = None,
    period: str = "month",  # week, month, year
    current_user: User = Depends(get_current_user_with_subscription)
):
    # Parse dates
    if start_date:
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
    else:
        # Default to start of current month
        now = datetime.now(timezone.utc)
        start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    if end_date:
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    else:
        end_dt = datetime.now(timezone.utc)
    
    # Get invoices in date range
    invoices = await db.invoices.find({
        "user_id": current_user.id,
        "issue_date": {"$gte": start_dt, "$lte": end_dt}
    }).to_list(1000)
    
    # Calculate statistics
    total_invoices = len(invoices)
    paid_invoices = [inv for inv in invoices if inv.get("status") == "paid"]
    pending_invoices = [inv for inv in invoices if inv.get("status") in ["sent", "draft"]]
    overdue_invoices = [inv for inv in invoices if inv.get("status") == "overdue"]
    
    total_revenue = sum(inv.get("total", 0) for inv in paid_invoices)
    pending_amount = sum(inv.get("total", 0) for inv in pending_invoices)
    overdue_amount = sum(inv.get("total", 0) for inv in overdue_invoices)
    
    # Group by period
    period_data = {}
    for invoice in invoices:
        invoice_date = datetime.fromisoformat(invoice["issue_date"].replace('Z', '+00:00'))
        
        if period == "week":
            # Get week number
            week_start = invoice_date - timedelta(days=invoice_date.weekday())
            period_key = week_start.strftime("%Y-W%U")
        elif period == "month":
            period_key = invoice_date.strftime("%Y-%m")
        elif period == "year":
            period_key = invoice_date.strftime("%Y")
        else:
            period_key = invoice_date.strftime("%Y-%m-%d")
        
        if period_key not in period_data:
            period_data[period_key] = {
                "period": period_key,
                "total_invoices": 0,
                "paid_count": 0,
                "pending_count": 0,
                "total_amount": 0,
                "paid_amount": 0,
                "pending_amount": 0
            }
        
        period_data[period_key]["total_invoices"] += 1
        period_data[period_key]["total_amount"] += invoice.get("total", 0)
        
        if invoice.get("status") == "paid":
            period_data[period_key]["paid_count"] += 1
            period_data[period_key]["paid_amount"] += invoice.get("total", 0)
        elif invoice.get("status") in ["sent", "draft"]:
            period_data[period_key]["pending_count"] += 1
            period_data[period_key]["pending_amount"] += invoice.get("total", 0)
    
    return {
        "period": period,
        "start_date": start_dt.isoformat(),
        "end_date": end_dt.isoformat(),
        "summary": {
            "total_invoices": total_invoices,
            "paid_invoices": len(paid_invoices),
            "pending_invoices": len(pending_invoices),
            "overdue_invoices": len(overdue_invoices),
            "total_revenue": total_revenue,
            "pending_amount": pending_amount,
            "overdue_amount": overdue_amount,
            "collection_rate": (len(paid_invoices) / total_invoices * 100) if total_invoices > 0 else 0
        },
        "period_breakdown": list(period_data.values())
    }

@api_router.get("/export/invoices")
async def export_invoices_data(
    status: str = None,
    start_date: str = None,
    end_date: str = None,
    current_user: User = Depends(get_current_user_with_subscription)
):
    query = {"user_id": current_user.id}
    
    if status:
        query["status"] = status
    
    if start_date:
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if "issue_date" not in query:
            query["issue_date"] = {}
        query["issue_date"]["$gte"] = start_dt
    
    if end_date:
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        if "issue_date" not in query:
            query["issue_date"] = {}
        query["issue_date"]["$lte"] = end_dt
    
    invoices = await db.invoices.find(query).to_list(1000)
    clients_dict = {client["id"]: client for client in await db.clients.find({"user_id": current_user.id}).to_list(1000)}
    
    # Format for export
    export_data = []
    for invoice in invoices:
        client = clients_dict.get(invoice["client_id"], {})
        export_data.append({
            "invoice_number": invoice["invoice_number"],
            "client_name": client.get("name", "Client inconnu"),
            "client_email": client.get("email", ""),
            "issue_date": invoice["issue_date"],
            "due_date": invoice["due_date"],
            "status": invoice["status"],
            "subtotal": invoice.get("subtotal", 0),
            "gst_amount": invoice.get("gst_amount", 0),
            "pst_amount": invoice.get("pst_amount", 0),
            "hst_amount": invoice.get("hst_amount", 0),
            "total": invoice.get("total", 0),
            "payment_method": invoice.get("payment_info", {}).get("payment_method") if invoice.get("payment_info") else None,
            "payment_date": invoice.get("payment_info", {}).get("payment_date") if invoice.get("payment_info") else None,
            "notes": invoice.get("notes", "")
        })
    
    return {
        "invoices": export_data,
        "total_count": len(export_data),
        "export_date": datetime.now(timezone.utc).isoformat()
    }

# Dashboard stats
@api_router.get("/dashboard/stats")
async def get_dashboard_stats(current_user: User = Depends(get_current_user_with_subscription)):
    # Get counts
    total_clients = await db.clients.count_documents({"user_id": current_user.id})
    total_invoices = await db.invoices.count_documents({"user_id": current_user.id})
    total_quotes = await db.quotes.count_documents({"user_id": current_user.id})
    
    # Get pending invoices
    pending_invoices = await db.invoices.count_documents({
        "user_id": current_user.id,
        "status": {"$in": [InvoiceStatus.SENT.value, InvoiceStatus.OVERDUE.value]}
    })
    
    # Calculate total revenue (paid invoices)
    paid_invoices = await db.invoices.find({
        "user_id": current_user.id,
        "status": InvoiceStatus.PAID.value
    }).to_list(1000)
    
    total_revenue = sum(invoice.get("total", 0) for invoice in paid_invoices)
    
    return {
        "total_clients": total_clients,
        "total_invoices": total_invoices,
        "total_quotes": total_quotes,
        "pending_invoices": pending_invoices,
        "total_revenue": total_revenue
    }

# Add health endpoint
@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

@api_router.get("/debug/user/{email}")
async def debug_user_exists(email: str):
    """Debug endpoint to check if user exists (temporary)"""
    user = await db.users.find_one({"email": email})
    if user:
        return {
            "exists": True,
            "email": user["email"],
            "company": user["company_name"],
            "created_at": user["created_at"],
            "subscription_status": user.get("subscription_status", "unknown")
        }
    return {"exists": False, "email": email}

# CORS middleware
allowed_origins = [
    "https://facturepro.ca",
    "https://facture-wizard.preview.emergentagent.com",
    "http://localhost:3000",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Subscription plans pricing (CAD)
SUBSCRIPTION_PLANS = {
    "monthly": {"amount": 15.00, "name": "FacturePro Monthly"},  # 15$ CAD per month
    "annual": {"amount": 150.00, "name": "FacturePro Annual"}   # 150$ CAD per year (2 months free)
}

# Stripe routes
@api_router.post("/subscription/checkout")
async def create_subscription_checkout(
    request: CheckoutRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user)
):
    try:
        # Get plan details
        if request.plan not in SUBSCRIPTION_PLANS:
            raise HTTPException(status_code=400, detail="Invalid subscription plan")
        
        plan_details = SUBSCRIPTION_PLANS[request.plan]
        
        # Initialize Stripe checkout
        host_url = str(http_request.base_url).rstrip('/')
        webhook_url = f"{host_url}/api/webhook/stripe"
        stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
        
        # Create checkout session
        origin_url = http_request.headers.get("origin", host_url)
        success_url = f"{origin_url}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{origin_url}/subscription/cancel"
        
        checkout_request = CheckoutSessionRequest(
            amount=plan_details["amount"],
            currency="cad",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "user_id": current_user.id,
                "plan": request.plan,
                "subscription_type": "facturepro"
            }
        )
        
        session = await stripe_checkout.create_checkout_session(checkout_request)
        
        # Create payment transaction record
        transaction = PaymentTransaction(
            user_id=current_user.id,
            session_id=session.session_id,
            amount=plan_details["amount"],
            currency="cad",
            status="initiated",
            payment_status="unpaid",
            metadata={
                "plan": request.plan,
                "plan_name": plan_details["name"]
            }
        )
        
        await db.payment_transactions.insert_one(transaction.dict())
        
        return {"checkout_url": session.url, "session_id": session.session_id}
        
    except Exception as e:
        logger.error(f"Error creating checkout session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")

@api_router.get("/subscription/status/{session_id}")
async def get_subscription_status(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    try:
        # Initialize Stripe checkout
        stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url="")
        
        # Get checkout status from Stripe
        checkout_status = await stripe_checkout.get_checkout_status(session_id)
        
        # Update payment transaction
        transaction = await db.payment_transactions.find_one({"session_id": session_id})
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
            
        # Update transaction status
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "status": checkout_status.status,
                    "payment_status": checkout_status.payment_status,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        # If payment is successful, create/update subscription
        if checkout_status.payment_status == "paid":
            await process_successful_subscription(transaction, current_user.id)
        
        return {
            "status": checkout_status.status,
            "payment_status": checkout_status.payment_status,
            "amount_total": checkout_status.amount_total,
            "currency": checkout_status.currency
        }
        
    except Exception as e:
        logger.error(f"Error checking subscription status: {e}")
        raise HTTPException(status_code=500, detail="Failed to check subscription status")

@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    try:
        body = await request.body()
        signature = request.headers.get("Stripe-Signature")
        
        if not signature:
            raise HTTPException(status_code=400, detail="Missing Stripe signature")
        
        # Initialize Stripe checkout
        stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url="")
        
        # Handle webhook
        webhook_response = await stripe_checkout.handle_webhook(body, signature)
        
        if webhook_response.event_type == "checkout.session.completed":
            # Find and update transaction
            await db.payment_transactions.update_one(
                {"session_id": webhook_response.session_id},
                {
                    "$set": {
                        "status": "completed",
                        "payment_status": webhook_response.payment_status,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            # Process subscription if payment successful
            if webhook_response.payment_status == "paid":
                transaction = await db.payment_transactions.find_one({"session_id": webhook_response.session_id})
                if transaction and transaction.get("metadata", {}).get("user_id"):
                    await process_successful_subscription(transaction, transaction["metadata"]["user_id"])
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

@api_router.get("/subscription/current")
async def get_current_subscription(current_user: User = Depends(get_current_user)):
    try:
        subscription = await db.subscriptions.find_one({"user_id": current_user.id})
        if not subscription:
            return {"subscription": None, "trial_days_left": 14}  # New user gets 14 day trial
        
        # Calculate trial days left
        trial_days_left = 0
        if subscription.get("status") == "trial" and subscription.get("trial_end"):
            trial_end = subscription["trial_end"]
            if isinstance(trial_end, str):
                trial_end = datetime.fromisoformat(trial_end.replace('Z', '+00:00'))
            days_left = (trial_end - datetime.now(timezone.utc)).days
            trial_days_left = max(0, days_left)
        
        return {
            "subscription": subscription,
            "trial_days_left": trial_days_left
        }
        
    except Exception as e:
        logger.error(f"Error getting subscription: {e}")
        raise HTTPException(status_code=500, detail="Failed to get subscription")

async def process_successful_subscription(transaction, user_id):
    """Process a successful subscription payment"""
    try:
        # Get transaction details
        plan = transaction["metadata"]["plan"]
        now = datetime.now(timezone.utc)
        
        # Calculate subscription end date
        if plan == "monthly":
            end_date = now + timedelta(days=30)
        else:  # annual
            end_date = now + timedelta(days=365)
        
        # Update user subscription status
        await db.users.update_one(
            {"id": user_id},
            {
                "$set": {
                    "subscription_status": "active",
                    "current_period_end": end_date,
                    "last_payment_date": now,
                    "is_active": True
                }
            }
        )
        
        # Create or update subscription record
        subscription = Subscription(
            user_id=user_id,
            plan=SubscriptionPlan(plan),
            status=SubscriptionStatus.active,
            current_period_start=now,
            current_period_end=end_date
        )
        
        # Check if subscription already exists
        existing_subscription = await db.subscriptions.find_one({"user_id": user_id})
        if existing_subscription:
            await db.subscriptions.update_one(
                {"user_id": user_id},
                {"$set": subscription.dict(exclude={"id"})}
            )
        else:
            await db.subscriptions.insert_one(subscription.dict())
            
        logger.info(f"Successfully processed subscription for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error processing successful subscription: {e}")
        raise

@api_router.post("/subscription/cancel")
async def cancel_subscription(current_user: User = Depends(get_current_user)):
    """Cancel user's subscription (they keep access until end of current period)"""
    try:
        # Update user subscription status to cancelled
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": {"subscription_status": "cancelled"}}
        )
        
        # Update subscription record
        await db.subscriptions.update_one(
            {"user_id": current_user.id},
            {
                "$set": {
                    "status": SubscriptionStatus.canceled,
                    "canceled_at": datetime.now(timezone.utc)
                }
            }
        )
        
        return {"message": "Abonnement annulé. Vous conservez l'accès jusqu'à la fin de votre période de facturation."}
        
    except Exception as e:
        logger.error(f"Error cancelling subscription: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel subscription")

@api_router.get("/subscription/user-status")
async def get_user_subscription_status(current_user: User = Depends(get_current_user)):
    """Get detailed user subscription status"""
    try:
        now = datetime.now(timezone.utc)
        
        # Check access status
        has_access = await check_subscription_access(current_user)
        
        # Calculate remaining days
        days_remaining = 0
        if current_user.subscription_status == "trial" and current_user.trial_end_date:
            trial_end = current_user.trial_end_date
            if trial_end.tzinfo is None:
                trial_end = trial_end.replace(tzinfo=timezone.utc)
            days_remaining = max(0, (trial_end - now).days)
        elif current_user.current_period_end:
            period_end = current_user.current_period_end
            if period_end.tzinfo is None:
                period_end = period_end.replace(tzinfo=timezone.utc)
            days_remaining = max(0, (period_end - now).days)
        
        return {
            "subscription_status": current_user.subscription_status,
            "has_access": has_access,
            "trial_end_date": current_user.trial_end_date.isoformat() if current_user.trial_end_date else None,
            "current_period_end": current_user.current_period_end.isoformat() if current_user.current_period_end else None,
            "days_remaining": days_remaining,
            "last_payment_date": current_user.last_payment_date.isoformat() if current_user.last_payment_date else None
        }
        
    except Exception as e:
        logger.error(f"Error getting user subscription status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get subscription status")

# Include the router in the main app (must be after all route definitions)
app.include_router(api_router)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()