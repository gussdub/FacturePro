from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import os
import jwt
import bcrypt
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from typing import Optional
import uuid

# Simple FastAPI app
app = FastAPI(title="FacturePro API", version="1.0.0")

# Configuration from environment
JWT_SECRET = os.environ.get('JWT_SECRET', 'default-secret')
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017/facturepro')

# Security
security = HTTPBearer()

# In-memory storage for testing (replace with real DB later)
users_db = {}
settings_db = {}

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
    return {"status": "healthy", "users_count": len(users_db)}

@app.post("/api/auth/register", response_model=Token)
async def register(user_data: UserCreate):
    # Check if user exists
    for user in users_db.values():
        if user.email == user_data.email:
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
    
    # Store user (with password separate for security)
    users_db[user_id] = new_user
    users_db[f"{user_id}_password"] = hashed_pwd
    
    # Create default settings
    settings_db[user_id] = {
        "company_name": user_data.company_name,
        "email": user_data.email,
        "logo_url": None
    }
    
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

# Protected routes
@app.get("/api/user/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@app.get("/api/settings/company")
async def get_settings(current_user: User = Depends(get_current_user)):
    return settings_db.get(current_user.id, {"company_name": current_user.company_name, "email": current_user.email})

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Special endpoint for gussdub
@app.post("/api/admin/create-gussdub")
async def create_gussdub():
    """Special endpoint to create gussdub account"""
    user_id = str(uuid.uuid4())
    hashed_pwd = hash_password("testpass123")
    
    gussdub_user = User(
        id=user_id,
        email="gussdub@gmail.com",
        company_name="ProFireManager",
        is_active=True
    )
    
    users_db[user_id] = gussdub_user
    users_db[f"{user_id}_password"] = hashed_pwd
    settings_db[user_id] = {
        "company_name": "ProFireManager",
        "email": "gussdub@gmail.com",
        "logo_url": None
    }
    
    return {"message": "Gussdub account created", "user": gussdub_user}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))