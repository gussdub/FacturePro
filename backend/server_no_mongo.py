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
        raise HTTPException(400, "Utilisateur introuvable")
    
    # Update password
    new_hashed_password = hash_password(request.new_password)
    users_db[f"{user_id}_password"] = new_hashed_password
    
    # Remove used token
    del reset_tokens[request.token]
    
    return {"message": "Mot de passe réinitialisé avec succès"}

# Invoice Models and Endpoints
class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent" 
    PAID = "paid"
    OVERDUE = "overdue"

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

# In-memory storage for invoices
invoices_db = {}

def calculate_taxes(subtotal, province):
    """Calculate Canadian taxes based on province"""
    if province == "QC":  # Quebec
        gst = subtotal * 0.05    # 5% GST
        pst = subtotal * 0.09975 # 9.975% PST (TVQ)
        hst = 0
        apply_gst, apply_pst, apply_hst = True, True, False
    elif province == "ON":  # Ontario
        gst = 0
        pst = 0
        hst = subtotal * 0.13    # 13% HST
        apply_gst, apply_pst, apply_hst = False, False, True
    else:  # Other provinces - just GST for now
        gst = subtotal * 0.05
        pst = 0
        hst = 0
        apply_gst, apply_pst, apply_hst = True, False, False
    
    total_tax = gst + pst + hst
    return gst, pst, hst, total_tax, apply_gst, apply_pst, apply_hst

def generate_invoice_number():
    """Generate next invoice number"""
    existing_numbers = []
    for invoice in invoices_db.values():
        if isinstance(invoice, dict) and "invoice_number" in invoice:
            try:
                num = int(invoice["invoice_number"].replace("INV-", ""))
                existing_numbers.append(num)
            except:
                pass
    
    next_num = max(existing_numbers) + 1 if existing_numbers else 1
    return f"INV-{next_num:04d}"

@app.get("/api/invoices")
async def get_invoices(current_user: User = Depends(get_current_user)):
    user_invoices = []
    for inv in invoices_db.values():
        if isinstance(inv, dict) and inv.get("user_id") == current_user.id:
            user_invoices.append(inv)
    return user_invoices

@app.post("/api/invoices")
async def create_invoice(invoice_data: dict, current_user: User = Depends(get_current_user)):
    # Calculate totals
    items = invoice_data.get("items", [])
    subtotal = sum(item["quantity"] * item["unit_price"] for item in items)
    
    province = invoice_data.get("province", "QC")
    gst, pst, hst, total_tax, apply_gst, apply_pst, apply_hst = calculate_taxes(subtotal, province)
    
    total = subtotal + total_tax
    
    # Generate invoice number
    invoice_number = generate_invoice_number()
    
    # Create invoice
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
    if invoice_id in invoices_db and invoices_db[invoice_id].get("user_id") == current_user.id:
        del invoices_db[invoice_id]
        return {"message": "Facture supprimée avec succès"}
    raise HTTPException(404, "Facture non trouvée")

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