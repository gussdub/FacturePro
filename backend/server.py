from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import os
import jwt
import bcrypt
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict
import uuid
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import resend
import stripe as stripe_lib

# Load environment
load_dotenv()

# Configuration
MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'facturepro')
JWT_SECRET = os.environ.get('JWT_SECRET', 'default-secret')
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY')
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'noreply@facturepro.ca')

# Initialize Resend
resend.api_key = RESEND_API_KEY

# Initialize Stripe
stripe_lib.api_key = STRIPE_API_KEY

# FastAPI app
app = FastAPI(title="FacturePro API", version="3.0.0")
security = HTTPBearer()

# MongoDB client
mongo_client = None
db = None

# Subscription Plans
PLANS = {
    "monthly": {
        "price": 15.00,
        "interval": "month",
        "name": "Abonnement Mensuel"
    },
    "yearly": {
        "price": 162.00,  # $15 * 12 * 0.90 = $162 (10% discount)
        "interval": "year",
        "name": "Abonnement Annuel (10% rabais)"
    }
}

# Models
class User(BaseModel):
    id: str
    email: str
    company_name: str
    is_active: bool = True
    subscription_status: str = "trial"  # trial, active, expired, cancelled
    trial_end_date: Optional[datetime] = None
    subscription_plan: Optional[str] = None  # monthly, yearly
    is_lifetime_free: bool = False

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    company_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    reset_code: str
    new_password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User

class CancellationRequest(BaseModel):
    reason: Optional[str] = None
    feedback: Optional[str] = None

class GrantFreeAccessRequest(BaseModel):
    email: EmailStr
    free_until: Optional[str] = None  # ISO date string or "lifetime"
    reason: Optional[str] = None

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

class SubscriptionRequest(BaseModel):
    plan: str  # "monthly" or "yearly"

class InvoiceItem(BaseModel):
    description: str
    quantity: float
    unit_price: float
    tax_rate: float = 0.0

class Invoice(BaseModel):
    id: str
    user_id: str
    invoice_number: str
    client_id: str
    client_name: str
    client_email: str
    client_address: Optional[str] = None
    items: List[InvoiceItem]
    subtotal: float
    tax_total: float
    discount: float = 0.0
    total: float
    status: str = "draft"  # draft, sent, paid, overdue
    issue_date: datetime
    due_date: datetime
    notes: Optional[str] = None
    created_at: datetime
    is_recurring: bool = False
    frequency: Optional[str] = None  # weekly, monthly, quarterly, yearly
    next_generation_date: Optional[datetime] = None
    parent_invoice_id: Optional[str] = None  # For tracking recurring invoices

class Quote(BaseModel):
    id: str
    user_id: str
    quote_number: str
    client_id: str
    client_name: str
    client_email: str
    client_address: Optional[str] = None
    items: List[InvoiceItem]
    subtotal: float
    tax_total: float
    discount: float = 0.0
    total: float
    status: str = "draft"  # draft, sent, accepted, rejected
    valid_until: datetime
    notes: Optional[str] = None
    created_at: datetime

class Employee(BaseModel):
    id: str
    user_id: str
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    position: Optional[str] = None
    salary: Optional[float] = None
    hire_date: Optional[datetime] = None
    is_active: bool = True

class Expense(BaseModel):
    id: str
    user_id: str
    category: str
    amount: float
    description: str
    date: datetime
    receipt_url: Optional[str] = None

# Email Service
async def send_email(to_email: str, subject: str, html_content: str):
    """Send email via Resend"""
    try:
        params = {
            "from": SENDER_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html_content
        }
        
        email = resend.Emails.send(params)
        print(f"✅ Email sent to {to_email}: {email}")
        return True
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return False

async def send_trial_end_notification(user_email: str, days_remaining: int):
    """Send trial end notification"""
    subject = f"Votre période d'essai se termine dans {days_remaining} jours"
    
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2563eb;">Votre période d'essai se termine bientôt</h2>
                
                <p>Bonjour,</p>
                
                <p>Votre période d'essai gratuite de 14 jours se termine dans <strong>{days_remaining} jours</strong>.</p>
                
                <p>Pour continuer à utiliser FacturePro sans interruption, veuillez choisir un abonnement :</p>
                
                <ul>
                    <li><strong>Mensuel :</strong> 15 $ / mois (sans engagement)</li>
                    <li><strong>Annuel :</strong> 162 $ / an (économisez 10%)</li>
                </ul>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="https://app.facturepro.ca/subscription" 
                       style="background-color: #2563eb; color: white; padding: 12px 30px; 
                              text-decoration: none; border-radius: 5px; display: inline-block;">
                        Choisir un abonnement
                    </a>
                </div>
                
                <p>Merci de votre confiance,</p>
                <p><strong>L'équipe FacturePro</strong></p>
            </div>
        </body>
    </html>
    """
    
    await send_email(user_email, subject, html_content)

async def send_payment_success_email(user_email: str, plan_name: str, amount: float):
    """Send payment confirmation"""
    subject = "Confirmation de paiement - FacturePro"
    
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #10b981;">Paiement confirmé !</h2>
                
                <p>Bonjour,</p>
                
                <p>Nous avons bien reçu votre paiement pour FacturePro.</p>
                
                <div style="background-color: #f3f4f6; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <p><strong>Plan :</strong> {plan_name}</p>
                    <p><strong>Montant :</strong> {amount:.2f} $</p>
                    <p><strong>Date :</strong> {datetime.now().strftime('%d/%m/%Y')}</p>
                </div>
                
                <p>Votre abonnement est maintenant actif.</p>
                
                <p>Merci de votre confiance,</p>
                <p><strong>L'équipe FacturePro</strong></p>
            </div>
        </body>
    </html>
    """
    
    await send_email(user_email, subject, html_content)

# Utility functions
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(hours=24)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

# MongoDB helpers
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
        
        user_doc = await db.users.find_one({"id": user_id})
        if not user_doc:
            raise HTTPException(401, "User not found")
        
        return User(
            id=user_doc["id"],
            email=user_doc["email"],
            company_name=user_doc["company_name"],
            is_active=user_doc.get("is_active", True),
            subscription_status=user_doc.get("subscription_status", "trial"),
            trial_end_date=user_doc.get("trial_end_date"),
            subscription_plan=user_doc.get("subscription_plan"),
            is_lifetime_free=user_doc.get("is_lifetime_free", False)
        )
    except Exception as e:
        print(f"Auth error: {e}")
        raise HTTPException(401, "Invalid token")

def is_super_admin(user: User) -> bool:
    """Check if user is super admin"""
    return user.email == "gussdub@gmail.com"

async def get_super_admin(current_user: User = Depends(get_current_user)):
    """Dependency to ensure user is super admin"""
    if not is_super_admin(current_user):
        raise HTTPException(403, "Accès refusé : Super-Admin uniquement")
    return current_user

# Routes
@app.get("/")
async def root():
    return {
        "message": "FacturePro API v3.0", 
        "status": "running", 
        "database": "MongoDB",
        "features": ["Stripe Payments", "SendGrid Emails"]
    }

@app.get("/api/health")
async def health():
    try:
        await db.command('ping')
        users_count = await db.users.count_documents({})
        return {
            "status": "healthy", 
            "database": "connected", 
            "users_count": users_count,
            "stripe": "configured" if STRIPE_API_KEY else "not configured",
            "resend": "configured" if RESEND_API_KEY else "not configured"
        }
    except Exception as e:
        return {"status": "unhealthy", "database": "error", "error": str(e)}

# Auth Routes
@app.post("/api/auth/register", response_model=Token)
async def register(user_data: UserCreate, background_tasks: BackgroundTasks):
    try:
        # Check if exists
        existing = await db.users.find_one({"email": user_data.email})
        if existing:
            raise HTTPException(400, "Email déjà enregistré")
        
        # Create user with 14-day trial
        user_id = str(uuid.uuid4())
        trial_end = datetime.now(timezone.utc) + timedelta(days=14)
        
        # Check for special free access
        is_lifetime_free = user_data.email == "gussdub@gmail.com"
        
        # Check for extended free access until end of 2026
        extended_free_emails = {
            "gignacarthur@gmail.com": datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        }
        extended_free_until = extended_free_emails.get(user_data.email)
        
        if is_lifetime_free:
            subscription_status = "active"
            trial_end_date = None
            subscription_plan = "lifetime"
        elif extended_free_until:
            subscription_status = "active"
            trial_end_date = extended_free_until
            subscription_plan = "free_extended"
        else:
            subscription_status = "trial"
            trial_end_date = trial_end
            subscription_plan = None
        
        new_user = {
            "id": user_id,
            "email": user_data.email,
            "company_name": user_data.company_name,
            "hashed_password": hash_password(user_data.password),
            "is_active": True,
            "subscription_status": subscription_status,
            "trial_end_date": trial_end_date,
            "subscription_plan": subscription_plan,
            "is_lifetime_free": is_lifetime_free,
            "created_at": datetime.now(timezone.utc)
        }
        
        await db.users.insert_one(new_user)
        
        # Create default settings
        settings = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "company_name": user_data.company_name,
            "email": user_data.email,
            "logo_url": "",
            "gst_number": "",
            "pst_number": "",
            "hst_number": ""
        }
        await db.company_settings.insert_one(settings)
        
        # Send welcome email (background task)
        if not is_lifetime_free:
            if extended_free_until:
                welcome_message = f"""
                <html>
                    <body style="font-family: Arial, sans-serif;">
                        <h2>Bienvenue sur FacturePro !</h2>
                        <p>Vous bénéficiez d'un accès gratuit jusqu'au <strong>{extended_free_until.strftime('%d/%m/%Y')}</strong>.</p>
                        <p>Vous pouvez créer vos factures, gérer vos clients et bien plus encore.</p>
                        <p>Profitez pleinement de toutes les fonctionnalités !</p>
                    </body>
                </html>
                """
            else:
                welcome_message = f"""
                <html>
                    <body style="font-family: Arial, sans-serif;">
                        <h2>Bienvenue sur FacturePro !</h2>
                        <p>Votre période d'essai gratuite de 14 jours commence maintenant.</p>
                        <p>Vous pouvez créer vos factures, gérer vos clients et bien plus encore.</p>
                        <p>Votre essai se termine le : <strong>{trial_end.strftime('%d/%m/%Y')}</strong></p>
                    </body>
                </html>
                """
            
            background_tasks.add_task(
                send_email,
                user_data.email,
                "Bienvenue sur FacturePro !",
                welcome_message
            )
        
        user_obj = User(
            id=user_id,
            email=user_data.email,
            company_name=user_data.company_name,
            is_active=True,
            subscription_status="active" if is_lifetime_free else "trial",
            trial_end_date=None if is_lifetime_free else trial_end,
            subscription_plan="lifetime" if is_lifetime_free else None,
            is_lifetime_free=is_lifetime_free
        )
        
        token = create_token(user_id)
        return Token(access_token=token, token_type="bearer", user=user_obj)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Register error: {e}")
        raise HTTPException(500, "Échec de l'inscription")

@app.post("/api/auth/login", response_model=Token)
async def login(credentials: UserLogin):
    try:
        user = await db.users.find_one({"email": credentials.email})
        if not user:
            raise HTTPException(401, "Email ou mot de passe incorrect")
        
        if not verify_password(credentials.password, user["hashed_password"]):
            raise HTTPException(401, "Email ou mot de passe incorrect")
        
        # Check trial expiration
        if (user.get("subscription_status") == "trial" and 
            user.get("trial_end_date") and 
            user.get("trial_end_date") < datetime.now(timezone.utc)):
            # Update status to expired
            await db.users.update_one(
                {"id": user["id"]},
                {"$set": {"subscription_status": "expired", "is_active": False}}
            )
            raise HTTPException(403, "Votre période d'essai est expirée. Veuillez choisir un abonnement.")
        
        user_obj = User(
            id=user["id"],
            email=user["email"],
            company_name=user["company_name"],
            is_active=user.get("is_active", True),
            subscription_status=user.get("subscription_status", "trial"),
            trial_end_date=user.get("trial_end_date"),
            subscription_plan=user.get("subscription_plan"),
            is_lifetime_free=user.get("is_lifetime_free", False)
        )
        
        token = create_token(user["id"])
        return Token(access_token=token, token_type="bearer", user=user_obj)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(500, "Échec de la connexion")

@app.post("/api/auth/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    """Send password reset code via email"""
    try:
        user = await db.users.find_one({"email": request.email})
        if not user:
            # Don't reveal if email exists or not for security
            return {"message": "Si l'email existe, un code de réinitialisation a été envoyé"}
        
        # Generate 6-digit reset code
        reset_code = str(uuid.uuid4().int)[:6]
        reset_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        
        # Store reset code in database
        await db.password_resets.update_one(
            {"email": request.email},
            {
                "$set": {
                    "reset_code": reset_code,
                    "expiry": reset_expiry,
                    "used": False
                }
            },
            upsert=True
        )
        
        # Send email with reset code
        try:
            resend.Emails.send({
                "from": SENDER_EMAIL,
                "to": request.email,
                "subject": "Code de réinitialisation - FacturePro",
                "html": f"""
                <div style="font-family: Arial, sans-serif; padding: 20px; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #0d9488;">Réinitialisation de mot de passe</h2>
                    <p>Vous avez demandé la réinitialisation de votre mot de passe FacturePro.</p>
                    <p>Votre code de réinitialisation est :</p>
                    <div style="background: #f0fdfa; padding: 20px; border-radius: 8px; text-align: center; margin: 20px 0;">
                        <h1 style="color: #0d9488; letter-spacing: 8px; margin: 0;">{reset_code}</h1>
                    </div>
                    <p>Ce code expirera dans 1 heure.</p>
                    <p>Si vous n'avez pas demandé cette réinitialisation, ignorez cet email.</p>
                    <hr style="margin: 30px 0; border: none; border-top: 1px solid #e5e7eb;">
                    <p style="color: #6b7280; font-size: 12px;">FacturePro - Solution de facturation</p>
                </div>
                """
            })
        except Exception as e:
            print(f"Error sending reset email: {e}")
            raise HTTPException(500, "Erreur lors de l'envoi de l'email")
        
        return {"message": "Si l'email existe, un code de réinitialisation a été envoyé"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Forgot password error: {e}")
        raise HTTPException(500, "Erreur lors de la génération du code")

@app.post("/api/auth/reset-password")
async def reset_password(request: ResetPasswordRequest):
    """Reset password using code"""
    try:
        # Find reset code
        reset_record = await db.password_resets.find_one({
            "email": request.email,
            "reset_code": request.reset_code,
            "used": False
        })
        
        if not reset_record:
            raise HTTPException(400, "Code invalide ou expiré")
        
        # Check expiry
        if reset_record["expiry"] < datetime.now(timezone.utc):
            raise HTTPException(400, "Code expiré")
        
        # Update password
        hashed = hash_password(request.new_password)
        await db.users.update_one(
            {"email": request.email},
            {"$set": {"hashed_password": hashed}}
        )
        
        # Mark reset code as used
        await db.password_resets.update_one(
            {"email": request.email, "reset_code": request.reset_code},
            {"$set": {"used": True}}
        )
        
        return {"message": "Mot de passe réinitialisé avec succès"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Reset password error: {e}")
        raise HTTPException(500, "Erreur lors de la réinitialisation")

# Super-Admin Routes
@app.get("/api/admin/stats")
async def get_admin_stats(admin: User = Depends(get_super_admin)):
    """Get admin dashboard statistics"""
    try:
        # Total users
        total_users = await db.users.count_documents({})
        
        # Active subscribers
        active_subs = await db.users.count_documents({
            "subscription_status": "active",
            "is_lifetime_free": False,
            "subscription_plan": {"$in": ["monthly", "yearly"]}
        })
        
        # Trial users
        trial_users = await db.users.count_documents({"subscription_status": "trial"})
        
        # Cancelled users
        cancelled_users = await db.users.count_documents({"subscription_status": "cancelled"})
        
        # Free users (lifetime + extended)
        free_users = await db.users.count_documents({
            "$or": [
                {"is_lifetime_free": True},
                {"subscription_plan": "free_extended"}
            ]
        })
        
        # Calculate revenue
        monthly_subs = await db.users.count_documents({"subscription_plan": "monthly", "subscription_status": "active"})
        yearly_subs = await db.users.count_documents({"subscription_plan": "yearly", "subscription_status": "active"})
        
        mrr = monthly_subs * 15  # Monthly Recurring Revenue
        arr = (monthly_subs * 15 * 12) + (yearly_subs * 162)  # Annual Recurring Revenue
        
        # Recent signups (last 7 days)
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        recent_signups = await db.users.count_documents({
            "created_at": {"$gte": seven_days_ago}
        })
        
        # Recent cancellations (last 30 days)
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        recent_cancellations = await db.users.count_documents({
            "subscription_status": "cancelled",
            "cancelled_at": {"$gte": thirty_days_ago}
        })
        
        # Get list of free access users
        free_access_users = await db.users.find({
            "$or": [
                {"is_lifetime_free": True},
                {"subscription_plan": "free_extended"}
            ]
        }).to_list(length=100)
        
        free_list = []
        for user in free_access_users:
            free_list.append({
                "email": user["email"],
                "company_name": user["company_name"],
                "type": "Lifetime" if user.get("is_lifetime_free") else "Extended",
                "expires": user.get("trial_end_date").isoformat() if user.get("trial_end_date") else None,
                "created_at": user.get("created_at").isoformat() if user.get("created_at") else None
            })
        
        return {
            "total_users": total_users,
            "active_subscribers": active_subs,
            "trial_users": trial_users,
            "cancelled_users": cancelled_users,
            "free_users": free_users,
            "mrr": mrr,
            "arr": arr,
            "recent_signups": recent_signups,
            "recent_cancellations": recent_cancellations,
            "free_access_list": free_list
        }
        
    except Exception as e:
        print(f"Error getting admin stats: {e}")
        raise HTTPException(500, "Erreur lors de la récupération des statistiques")

@app.get("/api/admin/users")
async def search_users(
    search: Optional[str] = None,
    status: Optional[str] = None,
    admin: User = Depends(get_super_admin)
):
    """Search and filter users"""
    try:
        query = {}
        
        if search:
            query["$or"] = [
                {"email": {"$regex": search, "$options": "i"}},
                {"company_name": {"$regex": search, "$options": "i"}}
            ]
        
        if status:
            if status == "free":
                query["$or"] = [
                    {"is_lifetime_free": True},
                    {"subscription_plan": "free_extended"}
                ]
            else:
                query["subscription_status"] = status
        
        users = await db.users.find(query).sort("created_at", -1).limit(100).to_list(length=100)
        
        user_list = []
        for user in users:
            user_list.append({
                "id": user["id"],
                "email": user["email"],
                "company_name": user["company_name"],
                "subscription_status": user.get("subscription_status", "trial"),
                "subscription_plan": user.get("subscription_plan"),
                "is_lifetime_free": user.get("is_lifetime_free", False),
                "trial_end_date": user.get("trial_end_date").isoformat() if user.get("trial_end_date") else None,
                "created_at": user.get("created_at").isoformat() if user.get("created_at") else None
            })
        
        return {"users": user_list}
        
    except Exception as e:
        print(f"Error searching users: {e}")
        raise HTTPException(500, "Erreur lors de la recherche")

@app.post("/api/admin/grant-free-access")
async def grant_free_access(
    request: GrantFreeAccessRequest,
    admin: User = Depends(get_super_admin)
):
    """Grant free access to a user"""
    try:
        user = await db.users.find_one({"email": request.email})
        if not user:
            raise HTTPException(404, "Utilisateur non trouvé")
        
        update_data = {}
        
        if request.free_until == "lifetime":
            update_data = {
                "is_lifetime_free": True,
                "subscription_status": "active",
                "subscription_plan": "lifetime",
                "trial_end_date": None
            }
        elif request.free_until:
            # Parse date
            try:
                expiry_date = datetime.fromisoformat(request.free_until.replace('Z', '+00:00'))
                update_data = {
                    "subscription_status": "active",
                    "subscription_plan": "free_extended",
                    "trial_end_date": expiry_date,
                    "is_lifetime_free": False
                }
            except:
                raise HTTPException(400, "Format de date invalide")
        else:
            raise HTTPException(400, "Date d'expiration ou 'lifetime' requis")
        
        await db.users.update_one(
            {"email": request.email},
            {"$set": update_data}
        )
        
        # Log the action
        await db.admin_actions.insert_one({
            "action": "grant_free_access",
            "admin_email": admin.email,
            "target_email": request.email,
            "free_until": request.free_until,
            "reason": request.reason,
            "timestamp": datetime.now(timezone.utc)
        })
        
        return {"message": f"Accès gratuit accordé à {request.email}"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error granting free access: {e}")
        raise HTTPException(500, "Erreur lors de l'attribution de la gratuité")

# Subscription & Payment Routes
@app.post("/api/subscription/create-checkout")
async def create_checkout_session(
    request: Request,
    subscription_request: SubscriptionRequest,
    current_user: User = Depends(get_current_user)
):
    """Create Stripe checkout session for subscription"""
    try:
        # Check if user is lifetime free
        if current_user.is_lifetime_free:
            raise HTTPException(400, "Vous avez un accès gratuit à vie")
        
        # Check if user has extended free access
        if current_user.subscription_plan == "free_extended":
            trial_end = current_user.trial_end_date
            if trial_end and trial_end > datetime.now(timezone.utc):
                end_date = trial_end.strftime('%d/%m/%Y')
                raise HTTPException(400, f"Vous avez un accès gratuit jusqu'au {end_date}")
        
        # Validate plan
        if subscription_request.plan not in PLANS:
            raise HTTPException(400, "Plan invalide")
        
        plan = PLANS[subscription_request.plan]
        
        # Get origin from request
        origin = request.headers.get("origin", "http://localhost:3000")
        
        # Create success and cancel URLs
        success_url = f"{origin}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{origin}/subscription"
        
        # Create Stripe checkout session using official API
        session = stripe_lib.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'cad',
                    'unit_amount': int(plan["price"] * 100),  # Convert to cents
                    'product_data': {
                        'name': plan["name"],
                        'description': f'{plan["interval"]}ly subscription'
                    }
                },
                'quantity': 1
            }],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "user_id": current_user.id,
                "user_email": current_user.email,
                "plan": subscription_request.plan
            }
        )
        
        # Create payment transaction record
        transaction = {
            "id": str(uuid.uuid4()),
            "session_id": session.id,
            "user_id": current_user.id,
            "user_email": current_user.email,
            "amount": plan["price"],
            "currency": "cad",
            "plan": subscription_request.plan,
            "payment_status": "pending",
            "status": "initiated",
            "created_at": datetime.now(timezone.utc)
        }
        
        await db.payment_transactions.insert_one(transaction)
        
        return {"url": session.url, "session_id": session.id}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Checkout error: {e}")
        raise HTTPException(500, f"Erreur lors de la création du paiement: {str(e)}")

@app.get("/api/subscription/checkout-status/{session_id}")
async def get_checkout_status(
    session_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Check Stripe checkout session status"""
    try:
        # Get status from Stripe using official API
        session = stripe_lib.checkout.Session.retrieve(session_id)
        
        # Find transaction
        transaction = await db.payment_transactions.find_one({"session_id": session_id})
        
        if not transaction:
            raise HTTPException(404, "Transaction non trouvée")
        
        # If payment is successful and not already processed
        if (session.payment_status == "paid" and 
            transaction.get("payment_status") != "paid"):
            
            # Update transaction
            await db.payment_transactions.update_one(
                {"session_id": session_id},
                {"$set": {
                    "payment_status": "paid",
                    "status": "completed",
                    "paid_at": datetime.now(timezone.utc)
                }}
            )
            
            # Update user subscription
            plan = transaction.get("plan")
            await db.users.update_one(
                {"id": current_user.id},
                {"$set": {
                    "subscription_status": "active",
                    "subscription_plan": plan,
                    "is_active": True,
                    "trial_end_date": None
                }}
            )
            
            # Send confirmation email
            plan_info = PLANS.get(plan, {})
            background_tasks.add_task(
                send_payment_success_email,
                current_user.email,
                plan_info.get("name", "Abonnement"),
                transaction.get("amount", 0)
            )
        
        return {
            "status": session.status,
            "payment_status": session.payment_status,
            "amount_total": session.amount_total,
            "currency": session.currency
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Status check error: {e}")
        raise HTTPException(500, f"Erreur lors de la vérification: {str(e)}")

@app.post("/api/webhook/stripe")
async def stripe_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle Stripe webhooks"""
    try:
        body = await request.body()
        signature = request.headers.get("Stripe-Signature")
        
        # Note: For production, you should verify the webhook signature
        # For now, we'll just parse the event
        import json
        event = json.loads(body)
        
        # Handle checkout.session.completed event
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            session_id = session['id']
            
            # Find transaction
            transaction = await db.payment_transactions.find_one({"session_id": session_id})
            
            if transaction and transaction.get("payment_status") != "paid":
                # Update transaction
                await db.payment_transactions.update_one(
                    {"session_id": session_id},
                    {"$set": {
                        "payment_status": "paid",
                        "status": "completed",
                        "paid_at": datetime.now(timezone.utc)
                    }}
                )
                
                # Update user
                user_id = session['metadata'].get("user_id")
                plan = session['metadata'].get("plan")
                
                if user_id:
                    await db.users.update_one(
                        {"id": user_id},
                        {"$set": {
                            "subscription_status": "active",
                            "subscription_plan": plan,
                            "is_active": True
                        }}
                    )
        
        return {"status": "success"}
        
    except Exception as e:
        print(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}

# Client Routes
@app.get("/api/clients")
async def get_clients(current_user: User = Depends(get_current_user)):
    clients = []
    cursor = db.clients.find({"user_id": current_user.id})
    async for client in cursor:
        client.pop('_id', None)
        clients.append(Client(**client))
    return clients

@app.post("/api/clients")
async def create_client(client_data: dict, current_user: User = Depends(get_current_user)):
    client_id = str(uuid.uuid4())
    new_client = {
        "id": client_id,
        "user_id": current_user.id,
        **client_data,
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.clients.insert_one(new_client)
    new_client.pop('_id', None)
    return Client(**new_client)

@app.put("/api/clients/{client_id}")
async def update_client(
    client_id: str,
    client_data: dict,
    current_user: User = Depends(get_current_user)
):
    """Update client"""
    await db.clients.update_one(
        {"id": client_id, "user_id": current_user.id},
        {"$set": client_data}
    )
    
    client = await db.clients.find_one({"id": client_id, "user_id": current_user.id})
    if not client:
        raise HTTPException(404, "Client non trouvé")
    
    client.pop('_id', None)
    return client

@app.delete("/api/clients/{client_id}")
async def delete_client(client_id: str, current_user: User = Depends(get_current_user)):
    await db.clients.delete_one({"id": client_id, "user_id": current_user.id})
    return {"message": "Client supprimé"}

# Settings Routes
@app.get("/api/settings/company")
async def get_settings(current_user: User = Depends(get_current_user)):
    settings = await db.company_settings.find_one({"user_id": current_user.id})
    
    if not settings:
        default = {
            "id": str(uuid.uuid4()),
            "user_id": current_user.id,
            "company_name": current_user.company_name,
            "email": current_user.email,
            "logo_url": "",
            "gst_number": "",
            "pst_number": "",
            "hst_number": ""
        }
        await db.company_settings.insert_one(default)
        default.pop('_id', None)
        return default
    
    settings.pop('_id', None)
    return settings

@app.put("/api/settings/company")
async def update_settings(settings_data: dict, current_user: User = Depends(get_current_user)):
    await db.company_settings.update_one(
        {"user_id": current_user.id},
        {"$set": settings_data}
    )
    
    settings = await db.company_settings.find_one({"user_id": current_user.id})
    settings.pop('_id', None)
    return settings

@app.post("/api/settings/company/upload-logo")
async def upload_logo(logo_data: dict, current_user: User = Depends(get_current_user)):
    await db.company_settings.update_one(
        {"user_id": current_user.id},
        {"$set": {"logo_url": logo_data.get("logo_url")}}
    )
    
    return {"message": "Logo enregistré", "logo_url": logo_data.get("logo_url")}

# Dashboard Stats
@app.get("/api/dashboard/stats")
async def get_stats(current_user: User = Depends(get_current_user)):
    clients_count = await db.clients.count_documents({"user_id": current_user.id})
    products_count = await db.products.count_documents({"user_id": current_user.id})
    
    return {
        "total_clients": clients_count,
        "total_invoices": 0,
        "total_quotes": 0,
        "total_products": products_count,
        "total_revenue": 0,
        "pending_invoices": 0
    }

# Product routes
@app.get("/api/products")
async def get_products(current_user: User = Depends(get_current_user)):
    products = []
    cursor = db.products.find({"user_id": current_user.id})
    async for product in cursor:
        product.pop('_id', None)
        products.append(product)
    return products

@app.post("/api/products")
async def create_product(product_data: dict, current_user: User = Depends(get_current_user)):
    product_id = str(uuid.uuid4())
    new_product = {
        "id": product_id,
        "user_id": current_user.id,
        **product_data,
        "is_active": True,
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.products.insert_one(new_product)
    new_product.pop('_id', None)
    return new_product

@app.put("/api/products/{product_id}")
async def update_product(
    product_id: str,
    product_data: dict,
    current_user: User = Depends(get_current_user)
):
    """Update product"""
    await db.products.update_one(
        {"id": product_id, "user_id": current_user.id},
        {"$set": product_data}
    )
    
    product = await db.products.find_one({"id": product_id, "user_id": current_user.id})
    if not product:
        raise HTTPException(404, "Produit non trouvé")
    
    product.pop('_id', None)
    return product

@app.delete("/api/products/{product_id}")
async def delete_product(product_id: str, current_user: User = Depends(get_current_user)):
    """Delete product"""
    await db.products.delete_one({"id": product_id, "user_id": current_user.id})
    return {"message": "Produit supprimé"}

# Password Change Route
@app.post("/api/auth/change-password")
async def change_password(
    password_data: dict,
    current_user: User = Depends(get_current_user)
):
    """Change user password"""
    try:
        old_password = password_data.get("old_password")
        new_password = password_data.get("new_password")
        
        if not old_password or not new_password:
            raise HTTPException(400, "Ancien et nouveau mot de passe requis")
        
        # Get user from DB
        user = await db.users.find_one({"id": current_user.id})
        if not user:
            raise HTTPException(404, "Utilisateur non trouvé")
        
        # Verify old password
        if not verify_password(old_password, user["hashed_password"]):
            raise HTTPException(401, "Ancien mot de passe incorrect")
        
        # Update password
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": {"hashed_password": hash_password(new_password)}}
        )
        
        return {"message": "Mot de passe modifié avec succès"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Change password error: {e}")
        raise HTTPException(500, "Erreur lors du changement de mot de passe")

# Invoice Routes
@app.get("/api/invoices")
async def get_invoices(current_user: User = Depends(get_current_user)):
    """Get all invoices for current user"""
    invoices = []
    cursor = db.invoices.find({"user_id": current_user.id})
    async for invoice in cursor:
        invoice.pop('_id', None)
        invoices.append(invoice)
    return invoices

@app.get("/api/invoices/{invoice_id}")
async def get_invoice(invoice_id: str, current_user: User = Depends(get_current_user)):
    """Get specific invoice"""
    invoice = await db.invoices.find_one({"id": invoice_id, "user_id": current_user.id})
    if not invoice:
        raise HTTPException(404, "Facture non trouvée")
    invoice.pop('_id', None)
    return invoice

@app.post("/api/invoices")
async def create_invoice(invoice_data: dict, current_user: User = Depends(get_current_user)):
    """Create new invoice"""
    # Generate invoice number
    count = await db.invoices.count_documents({"user_id": current_user.id})
    invoice_number = f"INV-{count + 1:05d}"
    
    # Calculate totals
    items = invoice_data.get("items", [])
    subtotal = sum(item["quantity"] * item["unit_price"] for item in items)
    tax_total = sum(item["quantity"] * item["unit_price"] * item.get("tax_rate", 0) / 100 for item in items)
    discount = invoice_data.get("discount", 0)
    total = subtotal + tax_total - discount
    
    invoice_id = str(uuid.uuid4())
    new_invoice = {
        "id": invoice_id,
        "user_id": current_user.id,
        "invoice_number": invoice_number,
        "client_id": invoice_data.get("client_id"),
        "client_name": invoice_data.get("client_name"),
        "client_email": invoice_data.get("client_email"),
        "client_address": invoice_data.get("client_address"),
        "items": items,
        "subtotal": subtotal,
        "tax_total": tax_total,
        "discount": discount,
        "total": total,
        "status": invoice_data.get("status", "draft"),
        "issue_date": datetime.fromisoformat(invoice_data.get("issue_date")) if invoice_data.get("issue_date") else datetime.now(timezone.utc),
        "due_date": datetime.fromisoformat(invoice_data.get("due_date")) if invoice_data.get("due_date") else datetime.now(timezone.utc) + timedelta(days=30),
        "notes": invoice_data.get("notes"),
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.invoices.insert_one(new_invoice)
    new_invoice.pop('_id', None)
    return new_invoice

@app.put("/api/invoices/{invoice_id}")
async def update_invoice(
    invoice_id: str,
    invoice_data: dict,
    current_user: User = Depends(get_current_user)
):
    """Update invoice"""
    # Recalculate totals
    items = invoice_data.get("items", [])
    subtotal = sum(item["quantity"] * item["unit_price"] for item in items)
    tax_total = sum(item["quantity"] * item["unit_price"] * item.get("tax_rate", 0) / 100 for item in items)
    discount = invoice_data.get("discount", 0)
    total = subtotal + tax_total - discount
    
    update_data = {
        **invoice_data,
        "subtotal": subtotal,
        "tax_total": tax_total,
        "total": total
    }
    
    await db.invoices.update_one(
        {"id": invoice_id, "user_id": current_user.id},
        {"$set": update_data}
    )
    
    invoice = await db.invoices.find_one({"id": invoice_id})
    invoice.pop('_id', None)
    return invoice

@app.delete("/api/invoices/{invoice_id}")
async def delete_invoice(invoice_id: str, current_user: User = Depends(get_current_user)):
    """Delete invoice"""
    await db.invoices.delete_one({"id": invoice_id, "user_id": current_user.id})
    return {"message": "Facture supprimée"}

@app.post("/api/invoices/{invoice_id}/send-email")
async def send_invoice_email(
    invoice_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Send invoice by email"""
    invoice = await db.invoices.find_one({"id": invoice_id, "user_id": current_user.id})
    if not invoice:
        raise HTTPException(404, "Facture non trouvée")
    
    # Get company settings for sender info
    settings = await db.company_settings.find_one({"user_id": current_user.id})
    
    # Build email HTML
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>Facture #{invoice['invoice_number']}</h2>
            <p>Bonjour {invoice['client_name']},</p>
            <p>Veuillez trouver ci-joint votre facture.</p>
            
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <thead>
                    <tr style="background: #f3f4f6;">
                        <th style="padding: 10px; text-align: left;">Description</th>
                        <th style="padding: 10px; text-align: right;">Quantité</th>
                        <th style="padding: 10px; text-align: right;">Prix unitaire</th>
                        <th style="padding: 10px; text-align: right;">Total</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for item in invoice['items']:
        html_content += f"""
                    <tr>
                        <td style="padding: 10px; border-top: 1px solid #e5e7eb;">{item['description']}</td>
                        <td style="padding: 10px; border-top: 1px solid #e5e7eb; text-align: right;">{item['quantity']}</td>
                        <td style="padding: 10px; border-top: 1px solid #e5e7eb; text-align: right;">{item['unit_price']:.2f} $</td>
                        <td style="padding: 10px; border-top: 1px solid #e5e7eb; text-align: right;">{item['quantity'] * item['unit_price']:.2f} $</td>
                    </tr>
        """
    
    html_content += f"""
                </tbody>
            </table>
            
            <div style="text-align: right; margin: 20px 0;">
                <p><strong>Sous-total:</strong> {invoice['subtotal']:.2f} $</p>
                <p><strong>Taxes:</strong> {invoice['tax_total']:.2f} $</p>
                <p><strong>Total:</strong> {invoice['total']:.2f} $</p>
            </div>
            
            <p>Merci de votre confiance !</p>
            <p><strong>{settings.get('company_name', current_user.company_name) if settings else current_user.company_name}</strong></p>
        </body>
    </html>
    """
    
    # Send email
    background_tasks.add_task(
        send_email,
        invoice['client_email'],
        f"Facture #{invoice['invoice_number']} - {current_user.company_name}",
        html_content
    )
    
    # Update invoice status to "sent"
    await db.invoices.update_one(
        {"id": invoice_id},
        {"$set": {"status": "sent"}}
    )
    
    return {"message": "Facture envoyée par email"}

@app.post("/api/invoices/generate-recurring")
async def generate_recurring_invoices(current_user: User = Depends(get_current_user)):
    """Generate recurring invoices that are due"""
    try:
        now = datetime.now(timezone.utc)
        
        # Find all recurring invoices that need to be generated
        recurring_invoices = await db.invoices.find({
            "user_id": current_user.id,
            "is_recurring": True,
            "next_generation_date": {"$lte": now}
        }).to_list(length=None)
        
        generated_count = 0
        
        for template_invoice in recurring_invoices:
            # Calculate next invoice number
            last_invoice = await db.invoices.find_one(
                {"user_id": current_user.id},
                sort=[("invoice_number", -1)]
            )
            
            next_number = 1
            if last_invoice and last_invoice.get("invoice_number"):
                try:
                    last_num = int(last_invoice["invoice_number"].split("-")[1])
                    next_number = last_num + 1
                except:
                    pass
            
            # Create new invoice
            new_invoice = {
                "id": str(uuid.uuid4()),
                "user_id": current_user.id,
                "invoice_number": f"INV-{str(next_number).zfill(4)}",
                "client_id": template_invoice["client_id"],
                "client_name": template_invoice["client_name"],
                "client_email": template_invoice["client_email"],
                "client_address": template_invoice.get("client_address"),
                "items": template_invoice["items"],
                "subtotal": template_invoice["subtotal"],
                "tax_total": template_invoice["tax_total"],
                "discount": template_invoice.get("discount", 0.0),
                "total": template_invoice["total"],
                "status": "draft",
                "issue_date": now,
                "due_date": now + timedelta(days=30),
                "notes": template_invoice.get("notes"),
                "created_at": now,
                "is_recurring": False,
                "parent_invoice_id": template_invoice["id"]
            }
            
            await db.invoices.insert_one(new_invoice)
            
            # Send email automatically
            try:
                settings = await db.company_settings.find_one({"user_id": current_user.id})
                
                html_content = f"""
                <html>
                    <body style="font-family: Arial, sans-serif; padding: 20px; max-width: 800px; margin: 0 auto;">
                        <div style="background: linear-gradient(135deg, #0d9488, #06b6d4); padding: 30px; border-radius: 12px 12px 0 0;">
                            <h1 style="color: white; margin: 0;">Facture #{new_invoice['invoice_number']}</h1>
                            <p style="color: white; margin: 10px 0 0 0;">Date: {now.strftime('%d/%m/%Y')}</p>
                        </div>
                        
                        <div style="padding: 30px; background: white; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                            <p style="font-size: 16px;">Bonjour {new_invoice['client_name']},</p>
                            <p>Veuillez trouver ci-dessous votre facture récurrente.</p>
                            
                            <table style="width: 100%; border-collapse: collapse; margin: 30px 0;">
                                <thead>
                                    <tr style="background: #f0fdfa; border-bottom: 2px solid #0d9488;">
                                        <th style="padding: 12px; text-align: left; color: #0d9488;">Description</th>
                                        <th style="padding: 12px; text-align: center; color: #0d9488;">Qté</th>
                                        <th style="padding: 12px; text-align: right; color: #0d9488;">Prix unitaire</th>
                                        <th style="padding: 12px; text-align: right; color: #0d9488;">Total</th>
                                    </tr>
                                </thead>
                                <tbody>
                """
                
                for item in new_invoice['items']:
                    item_total = item['quantity'] * item['unit_price']
                    html_content += f"""
                                    <tr style="border-bottom: 1px solid #e5e7eb;">
                                        <td style="padding: 12px;">{item['description']}</td>
                                        <td style="padding: 12px; text-align: center;">{item['quantity']}</td>
                                        <td style="padding: 12px; text-align: right;">{item['unit_price']:.2f} $</td>
                                        <td style="padding: 12px; text-align: right;">{item_total:.2f} $</td>
                                    </tr>
                    """
                
                html_content += f"""
                                </tbody>
                            </table>
                            
                            <div style="text-align: right; margin: 30px 0; padding: 20px; background: #f9fafb; border-radius: 8px;">
                                <p style="margin: 5px 0;"><strong>Sous-total:</strong> {new_invoice['subtotal']:.2f} $</p>
                                <p style="margin: 5px 0;"><strong>Taxes:</strong> {new_invoice['tax_total']:.2f} $</p>
                                <p style="margin: 10px 0 0 0; font-size: 20px; color: #0d9488;"><strong>Total:</strong> {new_invoice['total']:.2f} $</p>
                            </div>
                            
                            <p style="margin-top: 30px;">Date d'échéance: <strong>{new_invoice['due_date'].strftime('%d/%m/%Y')}</strong></p>
                            
                            <hr style="margin: 30px 0; border: none; border-top: 1px solid #e5e7eb;">
                            
                            <p style="margin-top: 30px;">Merci de votre confiance !</p>
                            <p style="color: #0d9488; font-weight: bold; font-size: 18px;">
                                {settings.get('company_name', current_user.company_name) if settings else current_user.company_name}
                            </p>
                        </div>
                    </body>
                </html>
                """
                
                resend.Emails.send({
                    "from": SENDER_EMAIL,
                    "to": new_invoice['client_email'],
                    "subject": f"Facture #{new_invoice['invoice_number']} - {current_user.company_name}",
                    "html": html_content
                })
                
                # Update invoice status to sent
                await db.invoices.update_one(
                    {"id": new_invoice["id"]},
                    {"$set": {"status": "sent"}}
                )
                
            except Exception as e:
                print(f"Error sending recurring invoice email: {e}")
            
            # Calculate next generation date based on frequency
            frequency = template_invoice.get("frequency", "monthly")
            if frequency == "weekly":
                next_date = now + timedelta(weeks=1)
            elif frequency == "monthly":
                next_date = now + timedelta(days=30)
            elif frequency == "quarterly":
                next_date = now + timedelta(days=90)
            elif frequency == "yearly":
                next_date = now + timedelta(days=365)
            else:
                next_date = now + timedelta(days=30)
            
            # Update template invoice with next generation date
            await db.invoices.update_one(
                {"id": template_invoice["id"]},
                {"$set": {"next_generation_date": next_date}}
            )
            
            generated_count += 1
        
        return {
            "message": f"{generated_count} facture(s) récurrente(s) générée(s) et envoyée(s)",
            "generated_count": generated_count
        }
        
    except Exception as e:
        print(f"Error generating recurring invoices: {e}")
        raise HTTPException(500, "Erreur lors de la génération des factures récurrentes")

# Quote Routes
@app.get("/api/quotes")
async def get_quotes(current_user: User = Depends(get_current_user)):
    """Get all quotes for current user"""
    quotes = []
    cursor = db.quotes.find({"user_id": current_user.id})
    async for quote in cursor:
        quote.pop('_id', None)
        quotes.append(quote)
    return quotes

@app.post("/api/quotes")
async def create_quote(quote_data: dict, current_user: User = Depends(get_current_user)):
    """Create new quote"""
    # Generate quote number
    count = await db.quotes.count_documents({"user_id": current_user.id})
    quote_number = f"QUO-{count + 1:05d}"
    
    # Calculate totals
    items = quote_data.get("items", [])
    subtotal = sum(item["quantity"] * item["unit_price"] for item in items)
    tax_total = sum(item["quantity"] * item["unit_price"] * item.get("tax_rate", 0) / 100 for item in items)
    discount = quote_data.get("discount", 0)
    total = subtotal + tax_total - discount
    
    quote_id = str(uuid.uuid4())
    new_quote = {
        "id": quote_id,
        "user_id": current_user.id,
        "quote_number": quote_number,
        "client_id": quote_data.get("client_id"),
        "client_name": quote_data.get("client_name"),
        "client_email": quote_data.get("client_email"),
        "client_address": quote_data.get("client_address"),
        "items": items,
        "subtotal": subtotal,
        "tax_total": tax_total,
        "discount": discount,
        "total": total,
        "status": quote_data.get("status", "draft"),
        "valid_until": datetime.fromisoformat(quote_data.get("valid_until")) if quote_data.get("valid_until") else datetime.now(timezone.utc) + timedelta(days=30),
        "notes": quote_data.get("notes"),
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.quotes.insert_one(new_quote)
    new_quote.pop('_id', None)
    return new_quote

@app.put("/api/quotes/{quote_id}")
async def update_quote(
    quote_id: str,
    quote_data: dict,
    current_user: User = Depends(get_current_user)
):
    """Update quote"""
    # Recalculate totals
    items = quote_data.get("items", [])
    subtotal = sum(item["quantity"] * item["unit_price"] for item in items)
    taxTotal = sum(item["quantity"] * item["unit_price"] * item.get("tax_rate", 0) / 100 for item in items)
    discount = quote_data.get("discount", 0)
    total = subtotal + taxTotal - discount
    
    update_data = {
        **quote_data,
        "subtotal": subtotal,
        "tax_total": taxTotal,
        "total": total
    }
    
    await db.quotes.update_one(
        {"id": quote_id, "user_id": current_user.id},
        {"$set": update_data}
    )
    
    quote = await db.quotes.find_one({"id": quote_id})
    quote.pop('_id', None)
    return quote

@app.delete("/api/quotes/{quote_id}")
async def delete_quote(quote_id: str, current_user: User = Depends(get_current_user)):
    """Delete quote"""
    await db.quotes.delete_one({"id": quote_id, "user_id": current_user.id})
    return {"message": "Soumission supprimée"}

@app.post("/api/quotes/{quote_id}/convert-to-invoice")
async def convert_quote_to_invoice(
    quote_id: str,
    current_user: User = Depends(get_current_user)
):
    """Convert a quote to an invoice"""
    try:
        # Get the quote
        quote = await db.quotes.find_one({"id": quote_id, "user_id": current_user.id})
        if not quote:
            raise HTTPException(404, "Soumission non trouvée")
        
        # Generate invoice number
        last_invoice = await db.invoices.find_one(
            {"user_id": current_user.id},
            sort=[("invoice_number", -1)]
        )
        
        next_number = 1
        if last_invoice and last_invoice.get("invoice_number"):
            try:
                last_num = int(last_invoice["invoice_number"].split("-")[1])
                next_number = last_num + 1
            except:
                pass
        
        invoice_number = f"INV-{str(next_number).zfill(4)}"
        
        # Create invoice from quote
        now = datetime.now(timezone.utc)
        new_invoice = {
            "id": str(uuid.uuid4()),
            "user_id": current_user.id,
            "invoice_number": invoice_number,
            "client_id": quote.get("client_id"),
            "client_name": quote.get("client_name"),
            "client_email": quote.get("client_email"),
            "client_address": quote.get("client_address"),
            "items": quote.get("items"),
            "subtotal": quote.get("subtotal"),
            "tax_total": quote.get("tax_total"),
            "discount": quote.get("discount", 0.0),
            "total": quote.get("total"),
            "status": "draft",
            "issue_date": now,
            "due_date": now + timedelta(days=30),
            "notes": quote.get("notes"),
            "created_at": now,
            "is_recurring": False,
            "frequency": None,
            "next_generation_date": None,
            "parent_invoice_id": None
        }
        
        await db.invoices.insert_one(new_invoice)
        
        # Update quote status to "accepted"
        await db.quotes.update_one(
            {"id": quote_id},
            {"$set": {"status": "accepted"}}
        )
        
        new_invoice.pop('_id', None)
        return {"message": "Soumission convertie en facture", "invoice": new_invoice}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error converting quote to invoice: {e}")
        raise HTTPException(500, "Erreur lors de la conversion")

@app.post("/api/quotes/{quote_id}/send-email")
async def send_quote_email(
    quote_id: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Send quote by email with acceptance link"""
    try:
        quote = await db.quotes.find_one({"id": quote_id, "user_id": current_user.id})
        if not quote:
            raise HTTPException(404, "Soumission non trouvée")
        
        # Get company settings
        settings = await db.company_settings.find_one({"user_id": current_user.id})
        company_name = settings.get('company_name', current_user.company_name) if settings else current_user.company_name
        
        # Generate acceptance token (valid for 30 days)
        accept_token = str(uuid.uuid4())
        accept_expiry = datetime.now(timezone.utc) + timedelta(days=30)
        
        # Store acceptance token
        await db.quote_tokens.update_one(
            {"quote_id": quote_id},
            {
                "$set": {
                    "token": accept_token,
                    "expiry": accept_expiry,
                    "used": False
                }
            },
            upsert=True
        )
        
        # Get origin for acceptance link
        origin = request.headers.get("origin", "http://localhost:3000")
        accept_url = f"{origin}/accept-quote/{accept_token}"
        
        # Build email HTML
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; padding: 20px; max-width: 800px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #0d9488, #06b6d4); padding: 30px; border-radius: 12px 12px 0 0;">
                    <h1 style="color: white; margin: 0;">Soumission #{quote['quote_number']}</h1>
                    <p style="color: white; margin: 10px 0 0 0;">De: {company_name}</p>
                </div>
                
                <div style="padding: 30px; background: white; border: 1px solid #e5e7eb; border-top: none;">
                    <p style="font-size: 16px;">Bonjour {quote['client_name']},</p>
                    <p>Veuillez trouver ci-dessous votre soumission.</p>
                    
                    <table style="width: 100%; border-collapse: collapse; margin: 30px 0;">
                        <thead>
                            <tr style="background: #f0fdfa; border-bottom: 2px solid #0d9488;">
                                <th style="padding: 12px; text-align: left; color: #0d9488;">Description</th>
                                <th style="padding: 12px; text-align: center; color: #0d9488;">Qté</th>
                                <th style="padding: 12px; text-align: right; color: #0d9488;">Prix unitaire</th>
                                <th style="padding: 12px; text-align: right; color: #0d9488;">Total</th>
                            </tr>
                        </thead>
                        <tbody>
        """
        
        for item in quote['items']:
            item_total = item['quantity'] * item['unit_price']
            html_content += f"""
                            <tr style="border-bottom: 1px solid #e5e7eb;">
                                <td style="padding: 12px;">{item['description']}</td>
                                <td style="padding: 12px; text-align: center;">{item['quantity']}</td>
                                <td style="padding: 12px; text-align: right;">{item['unit_price']:.2f} $</td>
                                <td style="padding: 12px; text-align: right;">{item_total:.2f} $</td>
                            </tr>
            """
        
        valid_until_str = quote['valid_until'].strftime('%d/%m/%Y') if isinstance(quote['valid_until'], datetime) else 'N/A'
        
        html_content += f"""
                        </tbody>
                    </table>
                    
                    <div style="text-align: right; margin: 30px 0; padding: 20px; background: #f9fafb; border-radius: 8px;">
                        <p style="margin: 5px 0;"><strong>Sous-total:</strong> {quote['subtotal']:.2f} $</p>
                        <p style="margin: 5px 0;"><strong>Taxes:</strong> {quote['tax_total']:.2f} $</p>
                        <p style="margin: 10px 0 0 0; font-size: 20px; color: #0d9488;"><strong>Total:</strong> {quote['total']:.2f} $</p>
                    </div>
                    
                    <p style="margin-top: 30px;">Valide jusqu'au: <strong>{valid_until_str}</strong></p>
                    
                    <div style="text-align: center; margin: 40px 0;">
                        <a href="{accept_url}" style="display: inline-block; background: linear-gradient(135deg, #0d9488, #06b6d4); color: white; padding: 16px 40px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 16px; box-shadow: 0 4px 12px rgba(13,148,136,0.4);">
                            ✅ Accepter cette soumission
                        </a>
                    </div>
                    
                    <p style="font-size: 14px; color: #6b7280; text-align: center;">En cliquant sur ce bouton, vous acceptez les termes de cette soumission.</p>
                    
                    <hr style="margin: 30px 0; border: none; border-top: 1px solid #e5e7eb;">
                    
                    <p style="margin-top: 30px;">Merci de votre confiance !</p>
                    <p style="color: #0d9488; font-weight: bold; font-size: 18px;">{company_name}</p>
                </div>
            </body>
        </html>
        """
        
        # Send email
        resend.Emails.send({
            "from": SENDER_EMAIL,
            "to": quote['client_email'],
            "subject": f"Soumission #{quote['quote_number']} - {company_name}",
            "html": html_content
        })
        
        # Update quote status to "sent"
        await db.quotes.update_one(
            {"id": quote_id},
            {"$set": {"status": "sent"}}
        )
        
        return {"message": "Soumission envoyée par email"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error sending quote email: {e}")
        raise HTTPException(500, "Erreur lors de l'envoi de l'email")

@app.get("/api/quotes/accept/{token}")
async def accept_quote_by_token(token: str):
    """Public endpoint to accept a quote via email link"""
    try:
        # Find token
        token_record = await db.quote_tokens.find_one({"token": token, "used": False})
        if not token_record:
            raise HTTPException(404, "Lien invalide ou expiré")
        
        # Check expiry
        if token_record["expiry"] < datetime.now(timezone.utc):
            raise HTTPException(400, "Ce lien a expiré")
        
        # Get the quote
        quote = await db.quotes.find_one({"id": token_record["quote_id"]})
        if not quote:
            raise HTTPException(404, "Soumission non trouvée")
        
        # Update quote status
        await db.quotes.update_one(
            {"id": token_record["quote_id"]},
            {"$set": {"status": "accepted"}}
        )
        
        # Mark token as used
        await db.quote_tokens.update_one(
            {"token": token},
            {"$set": {"used": True}}
        )
        
        # Get user info for confirmation email
        user = await db.users.find_one({"id": quote["user_id"]})
        if user:
            # Send confirmation email to business owner
            settings = await db.company_settings.find_one({"user_id": quote["user_id"]})
            company_name = settings.get('company_name', user['company_name']) if settings else user['company_name']
            
            confirmation_html = f"""
            <html>
                <body style="font-family: Arial, sans-serif; padding: 20px; max-width: 600px; margin: 0 auto;">
                    <div style="background: linear-gradient(135deg, #10b981, #059669); padding: 30px; border-radius: 12px 12px 0 0;">
                        <h1 style="color: white; margin: 0;">🎉 Soumission Acceptée !</h1>
                    </div>
                    
                    <div style="padding: 30px; background: white; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                        <p style="font-size: 16px;">Bonjour {company_name},</p>
                        <p>Excellente nouvelle ! Votre client <strong>{quote['client_name']}</strong> a accepté la soumission suivante :</p>
                        
                        <div style="background: #f0fdf4; padding: 20px; border-radius: 8px; border-left: 4px solid #10b981; margin: 20px 0;">
                            <p style="margin: 5px 0;"><strong>Numéro:</strong> {quote['quote_number']}</p>
                            <p style="margin: 5px 0;"><strong>Client:</strong> {quote['client_name']}</p>
                            <p style="margin: 5px 0;"><strong>Email:</strong> {quote['client_email']}</p>
                            <p style="margin: 5px 0;"><strong>Montant:</strong> {quote['total']:.2f} $</p>
                        </div>
                        
                        <p style="margin-top: 30px;">Vous pouvez maintenant convertir cette soumission en facture depuis votre tableau de bord.</p>
                        
                        <hr style="margin: 30px 0; border: none; border-top: 1px solid #e5e7eb;">
                        
                        <p style="color: #6b7280; font-size: 12px;">FacturePro - Solution de facturation</p>
                    </div>
                </body>
            </html>
            """
            
            try:
                resend.Emails.send({
                    "from": SENDER_EMAIL,
                    "to": user['email'],
                    "subject": f"✅ Soumission {quote['quote_number']} acceptée par {quote['client_name']}",
                    "html": confirmation_html
                })
            except Exception as e:
                print(f"Error sending confirmation email: {e}")
        
        return {
            "message": "Soumission acceptée avec succès !",
            "quote_number": quote['quote_number'],
            "client_name": quote['client_name']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error accepting quote: {e}")
        raise HTTPException(500, "Erreur lors de l'acceptation de la soumission")

# Employee Routes
@app.get("/api/employees")
async def get_employees(current_user: User = Depends(get_current_user)):
    """Get all employees"""
    employees = []
    cursor = db.employees.find({"user_id": current_user.id})
    async for employee in cursor:
        employee.pop('_id', None)
        employees.append(employee)
    return employees

@app.post("/api/employees")
async def create_employee(employee_data: dict, current_user: User = Depends(get_current_user)):
    """Create new employee"""
    employee_id = str(uuid.uuid4())
    new_employee = {
        "id": employee_id,
        "user_id": current_user.id,
        **employee_data,
        "is_active": employee_data.get("is_active", True),
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.employees.insert_one(new_employee)
    new_employee.pop('_id', None)
    return new_employee

@app.put("/api/employees/{employee_id}")
async def update_employee(
    employee_id: str,
    employee_data: dict,
    current_user: User = Depends(get_current_user)
):
    """Update employee"""
    await db.employees.update_one(
        {"id": employee_id, "user_id": current_user.id},
        {"$set": employee_data}
    )
    employee = await db.employees.find_one({"id": employee_id})
    employee.pop('_id', None)
    return employee

@app.delete("/api/employees/{employee_id}")
async def delete_employee(employee_id: str, current_user: User = Depends(get_current_user)):
    """Delete employee"""
    await db.employees.delete_one({"id": employee_id, "user_id": current_user.id})
    return {"message": "Employé supprimé"}

# Expense Routes
@app.get("/api/expenses")
async def get_expenses(current_user: User = Depends(get_current_user)):
    """Get all expenses"""
    expenses = []
    cursor = db.expenses.find({"user_id": current_user.id})
    async for expense in cursor:
        expense.pop('_id', None)
        expenses.append(expense)
    return expenses

@app.post("/api/expenses")
async def create_expense(expense_data: dict, current_user: User = Depends(get_current_user)):
    """Create new expense"""
    expense_id = str(uuid.uuid4())
    new_expense = {
        "id": expense_id,
        "user_id": current_user.id,
        **expense_data,
        "date": datetime.fromisoformat(expense_data.get("date")) if expense_data.get("date") else datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.expenses.insert_one(new_expense)
    new_expense.pop('_id', None)
    return new_expense

@app.put("/api/expenses/{expense_id}")
async def update_expense(
    expense_id: str,
    expense_data: dict,
    current_user: User = Depends(get_current_user)
):
    """Update expense"""
    if expense_data.get('date'):
        expense_data['date'] = datetime.fromisoformat(expense_data['date'])
    
    await db.expenses.update_one(
        {"id": expense_id, "user_id": current_user.id},
        {"$set": expense_data}
    )
    expense = await db.expenses.find_one({"id": expense_id})
    expense.pop('_id', None)
    return expense

@app.delete("/api/expenses/{expense_id}")
async def delete_expense(expense_id: str, current_user: User = Depends(get_current_user)):
    """Delete expense"""
    await db.expenses.delete_one({"id": expense_id, "user_id": current_user.id})
    return {"message": "Dépense supprimée"}

# Trial Expiration Checker
@app.post("/api/admin/check-trial-expirations")
async def check_trial_expirations(background_tasks: BackgroundTasks):
    """Check for trials expiring in 7 days and send reminders"""
    try:
        # Get users with trials expiring in 7 days
        seven_days_from_now = datetime.now(timezone.utc) + timedelta(days=7)
        seven_days_range_start = seven_days_from_now.replace(hour=0, minute=0, second=0, microsecond=0)
        seven_days_range_end = seven_days_range_start + timedelta(days=1)
        
        users_to_notify = []
        cursor = db.users.find({
            "subscription_status": "trial",
            "trial_end_date": {
                "$gte": seven_days_range_start,
                "$lt": seven_days_range_end
            },
            "is_lifetime_free": False
        })
        
        async for user in cursor:
            users_to_notify.append(user)
            
        # Send reminder emails
        for user in users_to_notify:
            days_remaining = 7
            background_tasks.add_task(
                send_trial_end_notification,
                user['email'],
                days_remaining
            )
        
        return {
            "message": f"{len(users_to_notify)} reminder(s) sent",
            "users_notified": len(users_to_notify)
        }
        
    except Exception as e:
        print(f"Trial check error: {e}")
        return {"error": str(e)}

# Get subscription info for current user
@app.get("/api/subscription/info")
async def get_subscription_info(current_user: User = Depends(get_current_user)):
    """Get current user's subscription information"""
    return {
        "subscription_status": current_user.subscription_status,
        "subscription_plan": current_user.subscription_plan,
        "trial_end_date": current_user.trial_end_date.isoformat() if current_user.trial_end_date else None,
        "is_lifetime_free": current_user.is_lifetime_free,
        "plans_available": PLANS
    }

# CORS Configuration
CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*')
if CORS_ORIGINS == '*':
    allowed_origins = ["*"]
else:
    allowed_origins = [origin.strip() for origin in CORS_ORIGINS.split(',')]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup
@app.on_event("startup")
async def startup():
    global mongo_client, db
    
    print("🚀 FacturePro starting...")
    
    try:
        # Connect to MongoDB
        mongo_client = AsyncIOMotorClient(MONGO_URL)
        db = mongo_client[DB_NAME]
        
        # Test connection
        await db.command('ping')
        print("✅ MongoDB connected")
        
        # Create indexes
        await db.users.create_index("email", unique=True)
        await db.users.create_index("id", unique=True)
        await db.clients.create_index([("user_id", 1)])
        await db.products.create_index([("user_id", 1)])
        await db.company_settings.create_index([("user_id", 1)])
        await db.payment_transactions.create_index([("session_id", 1)])
        await db.payment_transactions.create_index([("user_id", 1)])
        await db.invoices.create_index([("user_id", 1)])
        await db.invoices.create_index([("invoice_number", 1)])
        await db.quotes.create_index([("user_id", 1)])
        await db.employees.create_index([("user_id", 1)])
        await db.expenses.create_index([("user_id", 1)])
        print("✅ Indexes created")
        
        # Test Stripe
        if STRIPE_API_KEY:
            print("✅ Stripe configured")
        
        # Test Resend
        if RESEND_API_KEY:
            print("✅ Resend configured")
        
        print(f"✅ Server started successfully")
        print(f"📧 Sender email: {SENDER_EMAIL}")
        
    except Exception as e:
        print(f"❌ Startup error: {e}")

@app.on_event("shutdown")
async def shutdown():
    if mongo_client:
        mongo_client.close()
        print("MongoDB connection closed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8001)))
