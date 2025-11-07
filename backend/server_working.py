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

# FastAPI app
app = FastAPI(title="FacturePro API", version="1.0.0")

# Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', 'default-secret')

# Security
security = HTTPBearer()

# In-memory storage (will replace with MongoDB later)
users_db = {}
clients_db = {}
settings_db = {}
products_db = {}
invoices_db = {}

# Models
class UserCreate(BaseModel):
    email: str
    password: str
    company_name: str

class UserLogin(BaseModel):
    email: str
    password: str

class User(BaseModel):
    id: str
    email: str
    company_name: str
    is_active: bool = True

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
        
        if user_id in users_db:
            return users_db[user_id]
        else:
            raise HTTPException(401, "User not found")
    except:
        raise HTTPException(401, "Invalid token")

# Routes
@app.get("/")
async def root():
    return {"message": "FacturePro API", "status": "running", "version": "1.0.0"}

@app.get("/api/health")
async def health():
    return {"status": "healthy", "users_count": len([u for u in users_db.values() if isinstance(u, User)])}

@app.post("/api/auth/register", response_model=Token)
async def register(user_data: UserCreate):
    # Check if user exists
    for user in users_db.values():
        if isinstance(user, User) and user.email == user_data.email:
            raise HTTPException(400, "Email already registered")
    
    # Create user
    user_id = str(uuid.uuid4())
    hashed_pwd = hash_password(user_data.password)
    
    new_user = User(
        id=user_id,
        email=user_data.email,
        company_name=user_data.company_name,
        is_active=True
    )
    
    # Store user and password
    users_db[user_id] = new_user
    users_db[f"{user_id}_password"] = hashed_pwd
    
    # Create default settings
    settings_db[user_id] = CompanySettings(
        id=str(uuid.uuid4()),
        user_id=user_id,
        company_name=user_data.company_name,
        email=user_data.email
    )
    
    # Create token
    token = create_token(user_id)
    
    return Token(access_token=token, token_type="bearer", user=new_user)

@app.post("/api/auth/login", response_model=Token)
async def login(credentials: UserLogin):
    # Find user
    user = None
    user_id = None
    for uid, u in users_db.items():
        if isinstance(u, User) and u.email == credentials.email:
            user = u
            user_id = uid
            break
    
    if not user:
        raise HTTPException(401, "Incorrect email or password")
    
    # Check password
    stored_password = users_db.get(f"{user_id}_password")
    if not stored_password or not verify_password(credentials.password, stored_password):
        raise HTTPException(401, "Incorrect email or password")
    
    # Create token
    token = create_token(user_id)
    
    return Token(access_token=token, token_type="bearer", user=user)

@app.get("/api/clients")
async def get_clients(current_user: User = Depends(get_current_user)):
    user_clients = [client for client in clients_db.values() if isinstance(client, Client) and client.user_id == current_user.id]
    return user_clients

@app.post("/api/clients")
async def create_client(client_data: dict, current_user: User = Depends(get_current_user)):
    client_id = str(uuid.uuid4())
    new_client = Client(
        id=client_id,
        user_id=current_user.id,
        **client_data
    )
    clients_db[client_id] = new_client
    return new_client

@app.delete("/api/clients/{client_id}")
async def delete_client(client_id: str, current_user: User = Depends(get_current_user)):
    if client_id in clients_db and clients_db[client_id].user_id == current_user.id:
        del clients_db[client_id]
        return {"message": "Client deleted"}
    raise HTTPException(404, "Client not found")

@app.get("/api/settings/company")
async def get_settings(current_user: User = Depends(get_current_user)):
    return settings_db.get(current_user.id, CompanySettings(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        company_name=current_user.company_name,
        email=current_user.email
    ))

@app.put("/api/settings/company")
async def update_settings(settings_data: dict, current_user: User = Depends(get_current_user)):
    current_settings = settings_db.get(current_user.id)
    if current_settings:
        for key, value in settings_data.items():
            if hasattr(current_settings, key):
                setattr(current_settings, key, value)
    else:
        settings_db[current_user.id] = CompanySettings(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            **settings_data
        )
    return settings_db[current_user.id]

@app.post("/api/settings/company/upload-logo")
async def upload_logo(logo_data: dict, current_user: User = Depends(get_current_user)):
    if current_user.id in settings_db:
        settings_db[current_user.id].logo_url = logo_data.get("logo_url")
    return {"message": "Logo saved", "logo_url": logo_data.get("logo_url")}

# Password Reset 
class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

# Password reset storage
reset_tokens = {}

@app.post("/api/auth/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    # Find user
    user = None
    for u in users_db.values():
        if isinstance(u, User) and u.email == request.email:
            user = u
            break
    
    if not user:
        return {"message": "Si cette adresse email existe, un code de récupération a été généré"}
    
    # Generate reset token
    import secrets
    reset_token = secrets.token_urlsafe(32)
    
    # Store token (expires in 1 hour)
    reset_tokens[reset_token] = {
        "user_id": user.id,
        "email": user.email,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    
    return {
        "message": "Code de récupération généré", 
        "reset_token": reset_token,
        "expires_in": "1 heure"
    }

@app.post("/api/auth/reset-password")
async def reset_password(request: ResetPasswordRequest):
    # Check token
    token_data = reset_tokens.get(request.token)
    if not token_data:
        raise HTTPException(400, "Code de récupération invalide")
    
    # Check expiration
    if datetime.now(timezone.utc) > token_data["expires_at"]:
        del reset_tokens[request.token]
        raise HTTPException(400, "Code de récupération expiré")
    
    # Update password
    user_id = token_data["user_id"]
    new_hashed_password = hash_password(request.new_password)
    users_db[f"{user_id}_password"] = new_hashed_password
    
    # Remove used token
    del reset_tokens[request.token]
    
    return {"message": "Mot de passe réinitialisé avec succès"}

@app.get("/api/dashboard/stats")
async def get_stats(current_user: User = Depends(get_current_user)):
    user_clients = len([c for c in clients_db.values() if isinstance(c, Client) and c.user_id == current_user.id])
    return {
        "total_clients": user_clients,
        "total_invoices": 0,
        "total_quotes": 0,
        "total_products": 0,
        "total_revenue": 0,
        "pending_invoices": 0
    }

# Password Reset Models
class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

# Password reset storage (in production, use database with expiration)
reset_tokens = {}

@app.post("/api/auth/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    # Find user
    user = None
    for u in users_db.values():
        if isinstance(u, User) and u.email == request.email:
            user = u
            break
    
    if not user:
        # Don't reveal if email exists for security
        return {"message": "Si cette adresse email existe, un code de récupération a été généré"}
    
    # Generate reset token
    import secrets
    reset_token = secrets.token_urlsafe(32)
    
    # Store token (expires in 1 hour)
    reset_tokens[reset_token] = {
        "user_id": user.id,
        "email": user.email,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    
    # In production, this would be sent by email
    # For now, return it directly for demo
    return {
        "message": "Code de récupération généré",
        "reset_token": reset_token,
        "expires_in": "1 heure"
    }

@app.post("/api/auth/reset-password")
async def reset_password(request: ResetPasswordRequest):
    # Check if token exists and is valid
    token_data = reset_tokens.get(request.token)
    if not token_data:
        raise HTTPException(400, "Code de récupération invalide")
    
    # Check if token has expired
    if datetime.now(timezone.utc) > token_data["expires_at"]:
        del reset_tokens[request.token]  # Clean up expired token
        raise HTTPException(400, "Code de récupération expiré")
    
    # Find user
    user_id = token_data["user_id"]
    if user_id not in users_db:
        raise HTTPException(400, "Utilisateur non trouvé")
    
    # Update password
    new_hashed_password = hash_password(request.new_password)
    users_db[f"{user_id}_password"] = new_hashed_password
    
    # Remove used token
    del reset_tokens[request.token]
    
    return {"message": "Mot de passe réinitialisé avec succès"}

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create gussdub account on startup
@app.on_event("startup")
async def create_gussdub():
    user_id = str(uuid.uuid4())
    gussdub_user = User(
        id=user_id,
        email="gussdub@gmail.com",
        company_name="ProFireManager",
        is_active=True
    )
    users_db[user_id] = gussdub_user
    users_db[f"{user_id}_password"] = hash_password("testpass123")
    settings_db[user_id] = CompanySettings(
        id=str(uuid.uuid4()),
        user_id=user_id,
        company_name="ProFireManager",
        email="gussdub@gmail.com",
        gst_number="25357693",
        pst_number="2232323"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))