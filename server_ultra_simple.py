from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, EmailStr
from typing import List, Optional
import uuid

# Simple configuration
app = FastAPI(title="FacturePro API", version="1.0.0")

# Environment variables (will be set in Render)
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017/facturepro')
JWT_SECRET = os.environ.get('JWT_SECRET', 'default-secret')

# MongoDB
client = AsyncIOMotorClient(MONGO_URL)
db = client.facturepro

# Security
security = HTTPBearer()

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

# Auth functions
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(hours=24)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

async def get_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
        
        user_data = await db.users.find_one({"id": user_id})
        if not user_data:
            raise HTTPException(401, "User not found")
        return User(**user_data)
    except:
        raise HTTPException(401, "Invalid token")

# Routes
@app.get("/")
async def root():
    return {"message": "FacturePro API", "status": "running"}

@app.get("/api/health")
async def health():
    return {"status": "healthy"}

@app.post("/api/auth/register")
async def register(user_data: UserCreate):
    # Check if user exists
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(400, "Email already exists")
    
    # Create user
    user_id = str(uuid.uuid4())
    hashed_pwd = hash_password(user_data.password)
    
    new_user = {
        "id": user_id,
        "email": user_data.email,
        "hashed_password": hashed_pwd,
        "company_name": user_data.company_name,
        "is_active": True,
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.users.insert_one(new_user)
    
    # Create token
    token = create_token(user_id)
    
    return {"access_token": token, "token_type": "bearer", "user": User(**new_user)}

@app.post("/api/auth/login")
async def login(credentials: UserLogin):
    user = await db.users.find_one({"email": credentials.email})
    
    if not user or not verify_password(credentials.password, user["hashed_password"]):
        raise HTTPException(401, "Invalid credentials")
    
    token = create_token(user["id"])
    return {"access_token": token, "token_type": "bearer", "user": User(**user)}

# Protected routes
@app.get("/api/user/me")
async def get_me(current_user: User = Depends(get_user)):
    return current_user

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)