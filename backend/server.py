from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
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
import secrets
from dotenv import load_dotenv
import bcrypt

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection - MÊME CONFIGURATION QUE VOTRE APP QUI MARCHE
mongo_url = os.environ['MONGO_URL']

# Configuration SSL/TLS comme dans votre app
if 'mongodb+srv' in mongo_url or 'ssl=true' in mongo_url.lower():
    if 'tlsAllowInvalidCertificates' not in mongo_url:
        separator = '&' if '?' in mongo_url else '?'
        mongo_url += f'{separator}tlsAllowInvalidCertificates=false'

# Client MongoDB avec timeouts comme votre app
client = AsyncIOMotorClient(
    mongo_url,
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=10000,
    socketTimeoutMS=45000
)

# Database name
db_name = os.environ.get('DB_NAME', 'facturepro')
db = client[db_name]

# Security
security = HTTPBearer()
SECRET_KEY = os.environ.get("JWT_SECRET", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60  # 24 heures

# Create the main app - MÊME STYLE QUE VOTRE APP
app = FastAPI(title="FacturePro API", version="2.0")
api_router = APIRouter(prefix="/api")

# Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
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

class ProductCreate(BaseModel):
    name: str
    description: str
    unit_price: float
    unit: str = "unité"
    category: Optional[str] = None

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

# Security functions - MÊME STYLE QUE VOTRE APP
def get_password_hash(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
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

# Routes
@api_router.post("/auth/register", response_model=Token)
async def register(user: UserCreate):
    # Check if user already exists
    existing_user = await db.users.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    new_user = User(
        email=user.email,
        company_name=user.company_name
    )
    
    # Save to database with password
    user_doc = new_user.dict()
    user_doc["hashed_password"] = hashed_password
    await db.users.insert_one(user_doc)
    
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

# Password Reset
@api_router.post("/auth/forgot-password")
async def forgot_password(request: dict):
    email = request.get("email")
    user = await db.users.find_one({"email": email})
    
    if not user:
        return {"message": "Si cette adresse email existe, un code de récupération a été généré"}
    
    # Generate reset token
    reset_token = secrets.token_urlsafe(32)
    
    # Store token in user document
    await db.users.update_one(
        {"email": email},
        {
            "$set": {
                "reset_token": reset_token,
                "reset_token_expires": datetime.now(timezone.utc) + timedelta(hours=1)
            }
        }
    )
    
    return {"message": "Code de récupération généré", "reset_token": reset_token}

@api_router.post("/auth/reset-password")
async def reset_password(request: dict):
    token = request.get("token")
    new_password = request.get("new_password")
    
    # Find user with valid reset token
    user = await db.users.find_one({
        "reset_token": token,
        "reset_token_expires": {"$gt": datetime.now(timezone.utc)}
    })
    
    if not user:
        raise HTTPException(status_code=400, detail="Code de récupération invalide ou expiré")
    
    # Update password and remove reset token
    new_hashed_password = get_password_hash(new_password)
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
async def get_clients(current_user: User = Depends(get_current_user)):
    clients = await db.clients.find({"user_id": current_user.id}).to_list(length=None)
    return [Client(**client) for client in clients]

@api_router.post("/clients", response_model=Client)
async def create_client(client: ClientCreate, current_user: User = Depends(get_current_user)):
    new_client = Client(user_id=current_user.id, **client.dict())
    await db.clients.insert_one(new_client.dict())
    return new_client

@api_router.put("/clients/{client_id}", response_model=Client)
async def update_client(client_id: str, client_update: ClientCreate, current_user: User = Depends(get_current_user)):
    client = await db.clients.find_one({"id": client_id, "user_id": current_user.id})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    updated_data = client_update.dict()
    await db.clients.update_one({"id": client_id}, {"$set": updated_data})
    
    updated_client = await db.clients.find_one({"id": client_id})
    return Client(**updated_client)

@api_router.delete("/clients/{client_id}")
async def delete_client(client_id: str, current_user: User = Depends(get_current_user)):
    result = await db.clients.delete_one({"id": client_id, "user_id": current_user.id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"message": "Client deleted successfully"}

# Product routes
@api_router.get("/products", response_model=List[Product])
async def get_products(current_user: User = Depends(get_current_user)):
    products = await db.products.find({"user_id": current_user.id, "is_active": True}).to_list(length=None)
    return [Product(**product) for product in products]

@api_router.post("/products", response_model=Product)
async def create_product(product: ProductCreate, current_user: User = Depends(get_current_user)):
    new_product = Product(user_id=current_user.id, **product.dict())
    await db.products.insert_one(new_product.dict())
    return new_product

# Company settings routes
@api_router.get("/settings/company", response_model=CompanySettings)
async def get_company_settings(current_user: User = Depends(get_current_user)):
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
async def update_company_settings(settings_update: CompanySettingsUpdate, current_user: User = Depends(get_current_user)):
    settings = await db.company_settings.find_one({"user_id": current_user.id})
    if not settings:
        raise HTTPException(status_code=404, detail="Company settings not found")
    
    update_data = {k: v for k, v in settings_update.dict().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    await db.company_settings.update_one({"user_id": current_user.id}, {"$set": update_data})
    updated_settings = await db.company_settings.find_one({"user_id": current_user.id})
    return CompanySettings(**updated_settings)

@api_router.post("/settings/company/upload-logo")
async def upload_logo(logo_data: dict, current_user: User = Depends(get_current_user)):
    logo_url = logo_data.get("logo_url")
    if not logo_url:
        raise HTTPException(status_code=400, detail="Logo URL required")
    
    await db.company_settings.update_one(
        {"user_id": current_user.id},
        {"$set": {"logo_url": logo_url, "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {"message": "Logo saved successfully", "logo_url": logo_url}

# Dashboard stats
@api_router.get("/dashboard/stats")
async def get_dashboard_stats(current_user: User = Depends(get_current_user)):
    # Get counts
    total_clients = await db.clients.count_documents({"user_id": current_user.id})
    total_products = await db.products.count_documents({"user_id": current_user.id, "is_active": True})
    total_invoices = await db.invoices.count_documents({"user_id": current_user.id}) if hasattr(db, 'invoices') else 0
    total_quotes = await db.quotes.count_documents({"user_id": current_user.id}) if hasattr(db, 'quotes') else 0
    
    return {
        "total_clients": total_clients,
        "total_invoices": total_invoices,
        "total_quotes": total_quotes,
        "total_products": total_products,
        "total_revenue": 0,
        "pending_invoices": 0
    }

# Health check
@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

# Include the router in the main app
app.include_router(api_router)

# CORS middleware - MÊME CONFIG QUE VOTRE APP
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Startup event
@app.on_event("startup")
async def startup_db_client():
    # Test the MongoDB connection
    try:
        await client.admin.command('ping')
        logger.info("MongoDB connection successful")
        
        # Create gussdub account if doesn't exist
        existing_user = await db.users.find_one({"email": "gussdub@gmail.com"})
        if not existing_user:
            # Create gussdub account with exemption
            hashed_password = get_password_hash("testpass123")
            new_user = User(
                email="gussdub@gmail.com",
                company_name="ProFireManager"
            )
            
            user_doc = new_user.dict()
            user_doc["hashed_password"] = hashed_password
            await db.users.insert_one(user_doc)
            
            # Create default settings
            company_settings = CompanySettings(
                user_id=new_user.id,
                company_name="ProFireManager",
                email="gussdub@gmail.com",
                gst_number="123456789",
                pst_number="1234567890"
            )
            await db.company_settings.insert_one(company_settings.dict())
            
            logger.info("Account gussdub@gmail.com created successfully")
        else:
            logger.info("Account gussdub@gmail.com already exists")
            
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()