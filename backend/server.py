from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import asyncpg
import os
import jwt
import bcrypt
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from typing import Optional, List
import uuid
import secrets
import json
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configuration
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://user:password@localhost/facturepro')
JWT_SECRET = os.environ.get('JWT_SECRET', 'default-secret')

# FastAPI app
app = FastAPI(title="FacturePro API", version="2.0.0")
security = HTTPBearer()

# Database connection
db_pool = None

# Models
class User(BaseModel):
    id: str
    email: str
    company_name: str
    is_active: bool = True
    subscription_status: str = "trial"
    trial_end_date: Optional[datetime] = None

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
        
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
            if not row:
                raise HTTPException(401, "User not found")
            
            return User(
                id=row['id'],
                email=row['email'],
                company_name=row['company_name'],
                is_active=row['is_active'],
                subscription_status=row.get('subscription_status', 'trial')
            )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Auth error: {e}")
        raise HTTPException(401, "Invalid token")

async def get_current_user_with_access(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = await get_current_user(credentials)
    
    # Exempt users
    EXEMPT_USERS = ["gussdub@gmail.com"]
    if user.email in EXEMPT_USERS:
        return user
    
    return user

# Database initialization
async def init_database():
    global db_pool
    try:
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
        
        # Create tables
        async with db_pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id VARCHAR PRIMARY KEY,
                    email VARCHAR UNIQUE NOT NULL,
                    company_name VARCHAR NOT NULL,
                    is_active BOOLEAN DEFAULT true,
                    subscription_status VARCHAR DEFAULT 'trial',
                    trial_end_date TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS user_passwords (
                    user_id VARCHAR PRIMARY KEY,
                    hashed_password VARCHAR NOT NULL
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS clients (
                    id VARCHAR PRIMARY KEY,
                    user_id VARCHAR NOT NULL,
                    name VARCHAR NOT NULL,
                    email VARCHAR NOT NULL,
                    phone VARCHAR,
                    address VARCHAR,
                    city VARCHAR,
                    postal_code VARCHAR,
                    country VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS company_settings (
                    id VARCHAR PRIMARY KEY,
                    user_id VARCHAR UNIQUE NOT NULL,
                    company_name VARCHAR NOT NULL,
                    email VARCHAR NOT NULL,
                    phone VARCHAR,
                    address VARCHAR,
                    city VARCHAR,
                    postal_code VARCHAR,
                    country VARCHAR,
                    logo_url VARCHAR,
                    primary_color VARCHAR DEFAULT '#3B82F6',
                    secondary_color VARCHAR DEFAULT '#1F2937',
                    gst_number VARCHAR,
                    pst_number VARCHAR,
                    hst_number VARCHAR,
                    default_due_days INTEGER DEFAULT 30,
                    next_invoice_number INTEGER DEFAULT 1,
                    next_quote_number INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id VARCHAR PRIMARY KEY,
                    user_id VARCHAR NOT NULL,
                    name VARCHAR NOT NULL,
                    description TEXT,
                    unit_price DECIMAL(10,2) NOT NULL,
                    unit VARCHAR DEFAULT 'unité',
                    category VARCHAR,
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS invoices (
                    id VARCHAR PRIMARY KEY,
                    user_id VARCHAR NOT NULL,
                    client_id VARCHAR NOT NULL,
                    invoice_number VARCHAR NOT NULL,
                    issue_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    due_date DATE NOT NULL,
                    items JSONB,
                    subtotal DECIMAL(10,2) DEFAULT 0,
                    gst_amount DECIMAL(10,2) DEFAULT 0,
                    pst_amount DECIMAL(10,2) DEFAULT 0,
                    hst_amount DECIMAL(10,2) DEFAULT 0,
                    total_tax DECIMAL(10,2) DEFAULT 0,
                    total DECIMAL(10,2) DEFAULT 0,
                    province VARCHAR DEFAULT 'QC',
                    status VARCHAR DEFAULT 'draft',
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS quotes (
                    id VARCHAR PRIMARY KEY,
                    user_id VARCHAR NOT NULL,
                    client_id VARCHAR NOT NULL,
                    quote_number VARCHAR NOT NULL,
                    issue_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    valid_until DATE NOT NULL,
                    items JSONB,
                    subtotal DECIMAL(10,2) DEFAULT 0,
                    total DECIMAL(10,2) DEFAULT 0,
                    province VARCHAR DEFAULT 'QC',
                    status VARCHAR DEFAULT 'pending',
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        
        print("✅ PostgreSQL tables created successfully")
        
        # Create gussdub account if not exists
        async with db_pool.acquire() as conn:
            existing = await conn.fetchrow("SELECT id FROM users WHERE email = $1", "gussdub@gmail.com")
            
            if not existing:
                user_id = str(uuid.uuid4())
                trial_end = datetime.now(timezone.utc) + timedelta(days=3650)  # 10 years
                
                await conn.execute('''
                    INSERT INTO users (id, email, company_name, is_active, subscription_status, trial_end_date)
                    VALUES ($1, $2, $3, $4, $5, $6)
                ''', user_id, "gussdub@gmail.com", "ProFireManager", True, "trial", trial_end)
                
                await conn.execute('''
                    INSERT INTO user_passwords (user_id, hashed_password)
                    VALUES ($1, $2)
                ''', user_id, hash_password("testpass123"))
                
                await conn.execute('''
                    INSERT INTO company_settings (id, user_id, company_name, email, gst_number, pst_number)
                    VALUES ($1, $2, $3, $4, $5, $6)
                ''', str(uuid.uuid4()), user_id, "ProFireManager", "gussdub@gmail.com", "123456789", "1234567890")
                
                # Create sample client
                await conn.execute('''
                    INSERT INTO clients (id, user_id, name, email, phone, address, city, postal_code, country)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ''', str(uuid.uuid4()), user_id, "Client Test", "test@client.com", 
                   "514-123-4567", "123 Rue Test", "Montréal", "H1A 1A1", "Canada")
                
                print("✅ Account gussdub@gmail.com created with sample data")
            else:
                print("✅ Account gussdub@gmail.com already exists")
                
    except Exception as e:
        print(f"❌ Database initialization error: {e}")

# Routes
@app.get("/")
async def root():
    return {"message": "FacturePro API v2.0", "status": "running", "database": "PostgreSQL"}

@app.get("/api/health")
async def health():
    try:
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow("SELECT version() as version")
            return {"status": "healthy", "database": "connected", "postgresql_version": result["version"]}
    except Exception as e:
        return {"status": "unhealthy", "database": "error", "error": str(e)}

# Auth Routes
@app.post("/api/auth/register", response_model=Token)
async def register(user_data: UserCreate):
    try:
        async with db_pool.acquire() as conn:
            # Check if exists
            existing = await conn.fetchrow("SELECT id FROM users WHERE email = $1", user_data.email)
            if existing:
                raise HTTPException(400, "Email already registered")
            
            # Create user
            user_id = str(uuid.uuid4())
            trial_end = datetime.now(timezone.utc) + timedelta(days=14)
            
            await conn.execute('''
                INSERT INTO users (id, email, company_name, is_active, subscription_status, trial_end_date)
                VALUES ($1, $2, $3, $4, $5, $6)
            ''', user_id, user_data.email, user_data.company_name, True, "trial", trial_end)
            
            await conn.execute('''
                INSERT INTO user_passwords (user_id, hashed_password)
                VALUES ($1, $2)
            ''', user_id, hash_password(user_data.password))
            
            # Create default settings
            await conn.execute('''
                INSERT INTO company_settings (id, user_id, company_name, email)
                VALUES ($1, $2, $3, $4)
            ''', str(uuid.uuid4()), user_id, user_data.company_name, user_data.email)
            
            new_user = User(
                id=user_id,
                email=user_data.email,
                company_name=user_data.company_name,
                is_active=True,
                subscription_status="trial",
                trial_end_date=trial_end
            )
            
            token = create_token(user_id)
            return Token(access_token=token, token_type="bearer", user=new_user)
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Register error: {e}")
        raise HTTPException(500, "Registration failed")

@app.post("/api/auth/login", response_model=Token)
async def login(credentials: UserLogin):
    try:
        async with db_pool.acquire() as conn:
            user_row = await conn.fetchrow("SELECT * FROM users WHERE email = $1", credentials.email)
            if not user_row:
                raise HTTPException(401, "Incorrect email or password")
            
            password_row = await conn.fetchrow("SELECT hashed_password FROM user_passwords WHERE user_id = $1", user_row["id"])
            if not password_row or not verify_password(credentials.password, password_row["hashed_password"]):
                raise HTTPException(401, "Incorrect email or password")
            
            user = User(
                id=user_row['id'],
                email=user_row['email'],
                company_name=user_row['company_name'],
                is_active=user_row['is_active'],
                subscription_status=user_row.get('subscription_status', 'trial')
            )
            
            token = create_token(user_row["id"])
            return Token(access_token=token, token_type="bearer", user=user)
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(500, "Login failed")

# Password Reset
reset_tokens = {}

@app.post("/api/auth/forgot-password")
async def forgot_password(request: dict):
    try:
        email = request.get("email")
        async with db_pool.acquire() as conn:
            user = await conn.fetchrow("SELECT id, email FROM users WHERE email = $1", email)
            
            if not user:
                return {"message": "Si cette adresse email existe, un code de récupération a été généré"}
            
            reset_token = secrets.token_urlsafe(32)
            reset_tokens[reset_token] = {
                "user_id": user["id"],
                "email": user["email"],
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)
            }
            
            return {"message": "Code généré", "reset_token": reset_token}
    except Exception as e:
        print(f"Forgot password error: {e}")
        raise HTTPException(500, "Error generating reset code")

@app.post("/api/auth/reset-password")
async def reset_password(request: dict):
    try:
        token = request.get("token")
        new_password = request.get("new_password")
        
        token_data = reset_tokens.get(token)
        if not token_data or datetime.now(timezone.utc) > token_data["expires_at"]:
            raise HTTPException(400, "Code invalide ou expiré")
        
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE user_passwords SET hashed_password = $1 WHERE user_id = $2",
                hash_password(new_password), token_data["user_id"]
            )
        
        del reset_tokens[token]
        return {"message": "Mot de passe réinitialisé"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Reset password error: {e}")
        raise HTTPException(500, "Error resetting password")

# Client Routes
@app.get("/api/clients")
async def get_clients(current_user: User = Depends(get_current_user_with_access)):
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM clients WHERE user_id = $1", current_user.id)
            return [Client(**dict(row)) for row in rows]
    except Exception as e:
        print(f"Get clients error: {e}")
        return []

@app.post("/api/clients")
async def create_client(client_data: dict, current_user: User = Depends(get_current_user_with_access)):
    try:
        client_id = str(uuid.uuid4())
        async with db_pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO clients (id, user_id, name, email, phone, address, city, postal_code, country)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ''', client_id, current_user.id, client_data["name"], client_data["email"],
                client_data.get("phone"), client_data.get("address"), client_data.get("city"),
                client_data.get("postal_code"), client_data.get("country"))
            
            row = await conn.fetchrow("SELECT * FROM clients WHERE id = $1", client_id)
            return Client(**dict(row))
    except Exception as e:
        print(f"Create client error: {e}")
        raise HTTPException(500, "Error creating client")

@app.put("/api/clients/{client_id}")
async def update_client(client_id: str, client_data: dict, current_user: User = Depends(get_current_user_with_access)):
    try:
        async with db_pool.acquire() as conn:
            # Build update query dynamically
            fields = []
            values = []
            idx = 1
            
            for key, value in client_data.items():
                if key in ['name', 'email', 'phone', 'address', 'city', 'postal_code', 'country']:
                    fields.append(f"{key} = ${idx}")
                    values.append(value)
                    idx += 1
            
            if fields:
                query = f"UPDATE clients SET {', '.join(fields)} WHERE id = ${idx} AND user_id = ${idx+1}"
                values.extend([client_id, current_user.id])
                
                result = await conn.execute(query, *values)
                if result == "UPDATE 0":
                    raise HTTPException(404, "Client not found")
            
            row = await conn.fetchrow("SELECT * FROM clients WHERE id = $1", client_id)
            return Client(**dict(row))
    except HTTPException:
        raise
    except Exception as e:
        print(f"Update client error: {e}")
        raise HTTPException(500, "Error updating client")

@app.delete("/api/clients/{client_id}")
async def delete_client(client_id: str, current_user: User = Depends(get_current_user_with_access)):
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute("DELETE FROM clients WHERE id = $1 AND user_id = $2", client_id, current_user.id)
            if result == "DELETE 0":
                raise HTTPException(404, "Client not found")
            return {"message": "Client deleted"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Delete client error: {e}")
        raise HTTPException(500, "Error deleting client")

# Settings Routes
@app.get("/api/settings/company")
async def get_settings(current_user: User = Depends(get_current_user_with_access)):
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM company_settings WHERE user_id = $1", current_user.id)
            if not row:
                # Create default settings
                settings_id = str(uuid.uuid4())
                await conn.execute('''
                    INSERT INTO company_settings (id, user_id, company_name, email)
                    VALUES ($1, $2, $3, $4)
                ''', settings_id, current_user.id, current_user.company_name, current_user.email)
                
                row = await conn.fetchrow("SELECT * FROM company_settings WHERE user_id = $1", current_user.id)
            
            return dict(row)
    except Exception as e:
        print(f"Get settings error: {e}")
        return {
            "id": str(uuid.uuid4()),
            "user_id": current_user.id,
            "company_name": current_user.company_name,
            "email": current_user.email,
            "logo_url": "",
            "gst_number": "",
            "pst_number": "",
            "hst_number": ""
        }

@app.put("/api/settings/company")
async def update_settings(settings_data: dict, current_user: User = Depends(get_current_user_with_access)):
    try:
        async with db_pool.acquire() as conn:
            # Build update query
            fields = []
            values = []
            idx = 1
            
            for key, value in settings_data.items():
                if key in ['company_name', 'email', 'phone', 'address', 'city', 'postal_code', 'country', 
                          'logo_url', 'primary_color', 'secondary_color', 'gst_number', 'pst_number', 'hst_number']:
                    fields.append(f"{key} = ${idx}")
                    values.append(value)
                    idx += 1
            
            if fields:
                query = f"UPDATE company_settings SET {', '.join(fields)} WHERE user_id = ${idx}"
                values.append(current_user.id)
                await conn.execute(query, *values)
            
            row = await conn.fetchrow("SELECT * FROM company_settings WHERE user_id = $1", current_user.id)
            return dict(row)
    except Exception as e:
        print(f"Update settings error: {e}")
        raise HTTPException(500, "Error updating settings")

@app.post("/api/settings/company/upload-logo")
async def upload_logo(logo_data: dict, current_user: User = Depends(get_current_user_with_access)):
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE company_settings SET logo_url = $1 WHERE user_id = $2",
                logo_data.get("logo_url"), current_user.id
            )
        return {"message": "Logo saved", "logo_url": logo_data.get("logo_url")}
    except Exception as e:
        print(f"Upload logo error: {e}")
        raise HTTPException(500, "Error saving logo")

# Dashboard Stats
@app.get("/api/dashboard/stats")
async def get_stats(current_user: User = Depends(get_current_user_with_access)):
    try:
        async with db_pool.acquire() as conn:
            clients_count = await conn.fetchval("SELECT COUNT(*) FROM clients WHERE user_id = $1", current_user.id)
            invoices_count = await conn.fetchval("SELECT COUNT(*) FROM invoices WHERE user_id = $1", current_user.id)
            quotes_count = await conn.fetchval("SELECT COUNT(*) FROM quotes WHERE user_id = $1", current_user.id)
            products_count = await conn.fetchval("SELECT COUNT(*) FROM products WHERE user_id = $1 AND is_active = true", current_user.id)
            
            return {
                "total_clients": clients_count or 0,
                "total_invoices": invoices_count or 0,
                "total_quotes": quotes_count or 0,
                "total_products": products_count or 0,
                "total_revenue": 0,
                "pending_invoices": 0
            }
    except Exception as e:
        print(f"Dashboard stats error: {e}")
        return {"total_clients": 0, "total_invoices": 0, "total_quotes": 0, "total_products": 0, "total_revenue": 0, "pending_invoices": 0}

# Product Routes (basic for now)
@app.get("/api/products")
async def get_products(current_user: User = Depends(get_current_user_with_access)):
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM products WHERE user_id = $1 AND is_active = true", current_user.id)
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"Get products error: {e}")
        return []

@app.post("/api/products")
async def create_product(product_data: dict, current_user: User = Depends(get_current_user_with_access)):
    try:
        product_id = str(uuid.uuid4())
        async with db_pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO products (id, user_id, name, description, unit_price, unit, category, is_active)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ''', product_id, current_user.id, product_data["name"], product_data.get("description", ""),
                float(product_data["unit_price"]), product_data.get("unit", "unité"), 
                product_data.get("category", ""), True)
            
            row = await conn.fetchrow("SELECT * FROM products WHERE id = $1", product_id)
            return dict(row)
    except Exception as e:
        print(f"Create product error: {e}")
        raise HTTPException(500, "Error creating product")

# Invoice routes (basic for now)
@app.get("/api/invoices")
async def get_invoices(current_user: User = Depends(get_current_user_with_access)):
    return []  # Will implement later

@app.post("/api/invoices")
async def create_invoice(invoice_data: dict, current_user: User = Depends(get_current_user_with_access)):
    return {"message": "Invoice creation - coming soon"}

# Quote routes (basic for now)  
@app.get("/api/quotes")
async def get_quotes(current_user: User = Depends(get_current_user_with_access)):
    return []  # Will implement later

@app.post("/api/quotes")
async def create_quote(quote_data: dict, current_user: User = Depends(get_current_user_with_access)):
    return {"message": "Quote creation - coming soon"}

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup
@app.on_event("startup")
async def startup():
    await init_database()

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))