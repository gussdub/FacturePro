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

class SubscriptionRequest(BaseModel):
    plan: str  # "monthly" or "yearly"

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
        
        # Check if user is gussdub@gmail.com for lifetime free
        is_lifetime_free = user_data.email == "gussdub@gmail.com"
        
        new_user = {
            "id": user_id,
            "email": user_data.email,
            "company_name": user_data.company_name,
            "hashed_password": hash_password(user_data.password),
            "is_active": True,
            "subscription_status": "active" if is_lifetime_free else "trial",
            "trial_end_date": None if is_lifetime_free else trial_end,
            "subscription_plan": "lifetime" if is_lifetime_free else None,
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
            background_tasks.add_task(
                send_email,
                user_data.email,
                "Bienvenue sur FacturePro !",
                f"""
                <html>
                    <body style="font-family: Arial, sans-serif;">
                        <h2>Bienvenue sur FacturePro !</h2>
                        <p>Votre période d'essai gratuite de 14 jours commence maintenant.</p>
                        <p>Vous pouvez créer vos factures, gérer vos clients et bien plus encore.</p>
                        <p>Votre essai se termine le : <strong>{trial_end.strftime('%d/%m/%Y')}</strong></p>
                    </body>
                </html>
                """
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

# Placeholder routes (will be fully implemented)
@app.get("/api/invoices")
async def get_invoices(current_user: User = Depends(get_current_user)):
    return []

@app.get("/api/quotes") 
async def get_quotes(current_user: User = Depends(get_current_user)):
    return []

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
