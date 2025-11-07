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
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'facturepro')
JWT_SECRET = os.environ.get('JWT_SECRET', 'your-jwt-secret-here')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000')

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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ClientCreate(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None

class CompanySettings(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    company_name: str
    email: str
    logo_url: Optional[str] = None
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

# Exemption system for gussdub@gmail.com
async def get_current_user_with_access(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = await get_current_user(credentials)
    
    # Exempt users (always free access)
    EXEMPT_USERS = ["gussdub@gmail.com"]
    if user.email in EXEMPT_USERS:
        return True

    # Simple check - everyone has trial access for now
    return True

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
async def get_clients(current_user: User = Depends(get_current_user_with_access)):
    clients = await db.clients.find({"user_id": current_user.id}).to_list(1000)
    return [Client(**client) for client in clients]

@api_router.post("/clients", response_model=Client)
async def create_client(client: ClientCreate, current_user: User = Depends(get_current_user_with_access)):
    new_client = Client(**client.dict(), user_id=current_user.id)
    await db.clients.insert_one(new_client.dict())
    return new_client

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