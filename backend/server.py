from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, File, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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
import bcrypt
import secrets
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017/facturepro')
DB_NAME = os.environ.get('DB_NAME', 'facturepro')
JWT_SECRET = os.environ.get('JWT_SECRET', 'your-jwt-secret-here')

# MongoDB connection
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# Security
security = HTTPBearer()
ALGORITHM = "HS256"

# Create FastAPI app
app = FastAPI(
    title="FacturePro API",
    version="2.0.0",
    description="Professional Invoicing Solution for Canada"
)

# API Router
api_router = APIRouter(prefix="/api")

# Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    hashed_password: str
    company_name: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    company_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

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
    default_due_days: int = 30
    next_invoice_number: int = 1
    next_quote_number: int = 1
    gst_number: Optional[str] = None
    pst_number: Optional[str] = None
    hst_number: Optional[str] = None
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
    gst_number: Optional[str] = None
    pst_number: Optional[str] = None
    hst_number: Optional[str] = None

# Invoice and Quote Models
class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"

class InvoiceItem(BaseModel):
    description: str
    quantity: float = 1.0
    unit_price: float
    total: float

class Invoice(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    client_id: str
    invoice_number: str
    issue_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    due_date: datetime
    items: List[InvoiceItem] = []
    subtotal: float = 0
    gst_rate: float = 5.0
    pst_rate: float = 9.975
    hst_rate: float = 0.0
    gst_amount: float = 0
    pst_amount: float = 0
    hst_amount: float = 0
    total_tax: float = 0
    total: float = 0
    apply_gst: bool = True
    apply_pst: bool = True
    apply_hst: bool = False
    province: str = "QC"
    status: InvoiceStatus = InvoiceStatus.DRAFT
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Quote(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    client_id: str
    quote_number: str
    issue_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    valid_until: datetime
    items: List[InvoiceItem] = []
    subtotal: float = 0
    gst_rate: float = 5.0
    pst_rate: float = 9.975
    hst_rate: float = 0.0
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
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Product(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    name: str
    description: str
    unit_price: float
    unit: str = "unité"
    category: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Employee(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    name: str
    email: str
    phone: Optional[str] = None
    department: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Utility functions
def get_password_hash(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password using bcrypt"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user from JWT token"""
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except jwt.InvalidTokenError:
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
    
    # Simple check - everyone has trial access for now
    return True

async def get_current_user_with_access(credentials: HTTPAuthorizationCredentials = Depends(security)):
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

# Routes
@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "FacturePro API", "timestamp": datetime.now(timezone.utc).isoformat()}

@api_router.post("/auth/register", response_model=Token)
async def register(user: UserCreate):
    # Check if user exists
    existing_user = await db.users.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    hashed_password = get_password_hash(user.password)
    new_user = User(
        email=user.email,
        hashed_password=hashed_password,
        company_name=user.company_name
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
    
    # Create default company settings
    company_settings = CompanySettings(
        user_id=new_user.id,
        company_name=user.company_name,
        email=user.email
    )
    await db.company_settings.insert_one(company_settings.dict())
    
    # Create token
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
    
    updated_data = client_update.dict()
    await db.clients.update_one({"id": client_id}, {"$set": updated_data})
    
    updated_client = await db.clients.find_one({"id": client_id})
    return Client(**updated_client)

@api_router.delete("/clients/{client_id}")
async def delete_client(client_id: str, current_user: User = Depends(get_current_user_with_subscription)):
    result = await db.clients.delete_one({"id": client_id, "user_id": current_user.id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"message": "Client deleted successfully"}

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

@api_router.post("/settings/company/upload-logo")
async def upload_company_logo(
    logo_data: dict,
    current_user: User = Depends(get_current_user_with_subscription)
):
    # For now, accept logo URL instead of file upload
    # This simplifies deployment without Cloudinary
    
    logo_url = logo_data.get("logo_url")
    if not logo_url:
        raise HTTPException(status_code=400, detail="Logo URL required")
    
    # Update company settings
    await db.company_settings.update_one(
        {"user_id": current_user.id},
        {"$set": {"logo_url": logo_url, "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {
        "message": "Logo URL saved successfully",
        "logo_url": logo_url
    }

# Password Reset Models and Endpoints
class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

# In-memory token storage (temporary)
reset_tokens_db = {}

@api_router.post("/auth/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    # Find user
    user = await db.users.find_one({"email": request.email})
    if not user:
        return {"message": "Si cette adresse email existe, un code de récupération a été généré"}
    
    # Generate reset token
    import secrets
    reset_token = secrets.token_urlsafe(32)
    
    # Store token with expiration
    reset_tokens_db[reset_token] = {
        "user_id": user["id"],
        "email": user["email"], 
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    
    return {
        "message": "Code de récupération généré",
        "reset_token": reset_token,
        "expires_in": "1 heure"
    }

@api_router.post("/auth/reset-password")
async def reset_password(request: ResetPasswordRequest):
    # Check token
    token_data = reset_tokens_db.get(request.token)
    if not token_data:
        raise HTTPException(400, "Code de récupération invalide")
    
    # Check expiration
    if datetime.now(timezone.utc) > token_data["expires_at"]:
        del reset_tokens_db[request.token]
        raise HTTPException(400, "Code de récupération expiré")
    
    # Update password
    user_id = token_data["user_id"]
    new_hashed = get_password_hash(request.new_password)
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"hashed_password": new_hashed}}
    )
    
    # Remove used token
    del reset_tokens_db[request.token]
    
    return {"message": "Mot de passe réinitialisé avec succès"}

# Helper functions for calculations
def calculate_invoice_totals(items, gst_rate, pst_rate, hst_rate, apply_gst, apply_pst, apply_hst):
    """Calculate invoice totals with Canadian taxes"""
    subtotal = sum(item.quantity * item.unit_price for item in items)
    
    gst_amount = subtotal * (gst_rate / 100) if apply_gst else 0
    pst_amount = subtotal * (pst_rate / 100) if apply_pst else 0
    hst_amount = subtotal * (hst_rate / 100) if apply_hst else 0
    
    total_tax = gst_amount + pst_amount + hst_amount
    total = subtotal + total_tax
    
    return subtotal, gst_amount, pst_amount, hst_amount, total_tax, total

async def generate_invoice_number(user_id: str):
    """Generate next invoice number"""
    settings = await db.company_settings.find_one({"user_id": user_id})
    if settings:
        next_num = settings.get("next_invoice_number", 1)
        await db.company_settings.update_one(
            {"user_id": user_id},
            {"$set": {"next_invoice_number": next_num + 1}}
        )
        return f"INV-{next_num:04d}"
    return "INV-0001"

async def generate_quote_number(user_id: str):
    """Generate next quote number"""
    settings = await db.company_settings.find_one({"user_id": user_id})
    if settings:
        next_num = settings.get("next_quote_number", 1)
        await db.company_settings.update_one(
            {"user_id": user_id},
            {"$set": {"next_quote_number": next_num + 1}}
        )
        return f"QUO-{next_num:04d}"
    return "QUO-0001"

# Invoice routes
@api_router.get("/invoices", response_model=List[Invoice])
async def get_invoices(current_user: User = Depends(get_current_user_with_subscription)):
    invoices = await db.invoices.find({"user_id": current_user.id}).to_list(1000)
    return [Invoice(**invoice) for invoice in invoices]

@api_router.post("/invoices", response_model=Invoice)
async def create_invoice(invoice_data: dict, current_user: User = Depends(get_current_user_with_subscription)):
    # Generate invoice number
    invoice_number = await generate_invoice_number(current_user.id)
    
    # Calculate totals
    items = [InvoiceItem(**item) for item in invoice_data.get("items", [])]
    subtotal, gst_amount, pst_amount, hst_amount, total_tax, total = calculate_invoice_totals(
        items,
        invoice_data.get("gst_rate", 5.0),
        invoice_data.get("pst_rate", 9.975),
        invoice_data.get("hst_rate", 0.0),
        invoice_data.get("apply_gst", True),
        invoice_data.get("apply_pst", True),
        invoice_data.get("apply_hst", False)
    )
    
    new_invoice = Invoice(
        user_id=current_user.id,
        client_id=invoice_data["client_id"],
        invoice_number=invoice_number,
        due_date=datetime.fromisoformat(invoice_data["due_date"].replace('Z', '+00:00')),
        items=[item.dict() for item in items],
        subtotal=subtotal,
        gst_amount=gst_amount,
        pst_amount=pst_amount,
        hst_amount=hst_amount,
        total_tax=total_tax,
        total=total,
        gst_rate=invoice_data.get("gst_rate", 5.0),
        pst_rate=invoice_data.get("pst_rate", 9.975),
        hst_rate=invoice_data.get("hst_rate", 0.0),
        apply_gst=invoice_data.get("apply_gst", True),
        apply_pst=invoice_data.get("apply_pst", True),
        apply_hst=invoice_data.get("apply_hst", False),
        province=invoice_data.get("province", "QC"),
        notes=invoice_data.get("notes", "")
    )
    
    await db.invoices.insert_one(new_invoice.dict())
    return new_invoice

# Product routes
@api_router.get("/products", response_model=List[Product])
async def get_products(current_user: User = Depends(get_current_user_with_subscription)):
    products = await db.products.find({"user_id": current_user.id, "is_active": True}).to_list(1000)
    return [Product(**product) for product in products]

@api_router.post("/products", response_model=Product)
async def create_product(product_data: dict, current_user: User = Depends(get_current_user_with_subscription)):
    new_product = Product(**product_data, user_id=current_user.id)
    await db.products.insert_one(new_product.dict())
    return new_product

# Quote routes
@api_router.get("/quotes", response_model=List[Quote])
async def get_quotes(current_user: User = Depends(get_current_user_with_subscription)):
    quotes = await db.quotes.find({"user_id": current_user.id}).to_list(1000)
    return [Quote(**quote) for quote in quotes]

@api_router.post("/quotes", response_model=Quote)
async def create_quote(quote_data: dict, current_user: User = Depends(get_current_user_with_subscription)):
    # Generate quote number
    quote_number = await generate_quote_number(current_user.id)
    
    # Calculate totals (same logic as invoices)
    items = [InvoiceItem(**item) for item in quote_data.get("items", [])]
    subtotal, gst_amount, pst_amount, hst_amount, total_tax, total = calculate_invoice_totals(
        items,
        quote_data.get("gst_rate", 5.0),
        quote_data.get("pst_rate", 9.975),
        quote_data.get("hst_rate", 0.0),
        quote_data.get("apply_gst", True),
        quote_data.get("apply_pst", True),
        quote_data.get("apply_hst", False)
    )
    
    new_quote = Quote(
        user_id=current_user.id,
        client_id=quote_data["client_id"],
        quote_number=quote_number,
        valid_until=datetime.fromisoformat(quote_data["valid_until"].replace('Z', '+00:00')),
        items=[item.dict() for item in items],
        subtotal=subtotal,
        gst_amount=gst_amount,
        pst_amount=pst_amount,
        hst_amount=hst_amount,
        total_tax=total_tax,
        total=total,
        gst_rate=quote_data.get("gst_rate", 5.0),
        pst_rate=quote_data.get("pst_rate", 9.975),
        hst_rate=quote_data.get("hst_rate", 0.0),
        apply_gst=quote_data.get("apply_gst", True),
        apply_pst=quote_data.get("apply_pst", True),
        apply_hst=quote_data.get("apply_hst", False),
        province=quote_data.get("province", "QC"),
        notes=quote_data.get("notes", "")
    )
    
    await db.quotes.insert_one(new_quote.dict())
    return new_quote

# Dashboard stats
@api_router.get("/dashboard/stats")
async def get_dashboard_stats(current_user: User = Depends(get_current_user_with_subscription)):
    # Get counts
    total_clients = await db.clients.count_documents({"user_id": current_user.id})
    total_invoices = await db.invoices.count_documents({"user_id": current_user.id})
    total_quotes = await db.quotes.count_documents({"user_id": current_user.id})
    total_products = await db.products.count_documents({"user_id": current_user.id, "is_active": True})
    
    # Calculate revenue from paid invoices
    paid_invoices = await db.invoices.find({
        "user_id": current_user.id,
        "status": "paid"
    }).to_list(1000)
    
    total_revenue = sum(invoice.get("total", 0) for invoice in paid_invoices)
    
    return {
        "total_clients": total_clients,
        "total_invoices": total_invoices,
        "total_quotes": total_quotes,
        "total_products": total_products,
        "total_revenue": total_revenue,
        "pending_invoices": await db.invoices.count_documents({
            "user_id": current_user.id,
            "status": {"$in": ["sent", "overdue"]}
        })
    }

@api_router.get("/settings/company", response_model=CompanySettings)
async def get_company_settings(current_user: User = Depends(get_current_user_with_access)):
    settings = await db.company_settings.find_one({"user_id": current_user.id})
    if not settings:
        # Create default settings
        settings = CompanySettings(
            user_id=current_user.id,
            company_name=current_user.company_name,
            email=current_user.email
        )
        await db.company_settings.insert_one(settings.dict())
    return CompanySettings(**settings)

@api_router.post("/settings/company/upload-logo")
async def upload_company_logo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_with_access)
):
    # Validate file
    if file.size > 5 * 1024 * 1024:  # 5MB limit
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")
    
    # Create upload directory
    upload_dir = Path("/tmp/logos")  # Use /tmp for Render
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename
    file_extension = Path(file.filename).suffix
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"logo_{current_user.id}_{timestamp}{file_extension}"
    file_path = upload_dir / filename
    
    # Save file
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    # Update settings
    logo_url = f"/api/logos/{filename}"
    await db.company_settings.update_one(
        {"user_id": current_user.id},
        {"$set": {"logo_url": logo_url}}
    )
    
    return {"message": "Logo uploaded successfully", "logo_url": logo_url}

@api_router.get("/logos/{filename}")
async def serve_logo(filename: str):
    file_path = Path(f"/tmp/logos/{filename}")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Logo not found")
    return FileResponse(file_path, filename=filename)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],  # Configure properly in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include router
app.include_router(api_router)

# Root endpoint
@app.get("/")
async def root():
    return {"message": "FacturePro API is running", "version": "2.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))