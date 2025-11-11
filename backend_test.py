"""
Comprehensive Backend Testing for FacturePro PyMongo Async Implementation
Tests MongoDB Atlas connection and all API endpoints
"""

import requests
import json
from datetime import datetime, timedelta

# Configuration
BACKEND_URL = "https://facturepro.preview.emergentagent.com/api"
TEST_EMAIL = "gussdub@gmail.com"
TEST_PASSWORD = "testpass123"

# Test results tracking
test_results = {
    "passed": [],
    "failed": [],
    "warnings": []
}

def log_test(test_name, passed, message=""):
    """Log test result"""
    if passed:
        test_results["passed"].append(f"✅ {test_name}")
        print(f"✅ {test_name}")
    else:
        test_results["failed"].append(f"❌ {test_name}: {message}")
        print(f"❌ {test_name}: {message}")
    if message and passed:
        print(f"   {message}")

def log_warning(test_name, message):
    """Log warning"""
    test_results["warnings"].append(f"⚠️  {test_name}: {message}")
    print(f"⚠️  {test_name}: {message}")

# Global token storage
auth_token = None
test_client_id = None

print("=" * 80)
print("FACTUREPRO PYMONGO ASYNC BACKEND TESTING")
print("=" * 80)
print(f"Backend URL: {BACKEND_URL}")
print(f"Test User: {TEST_EMAIL}")
print("=" * 80)

# Test 1: Health Check with MongoDB Ping
print("\n🔍 TEST 1: Health Check & MongoDB Connection")
try:
    response = requests.get(f"{BACKEND_URL}/health", timeout=10)
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        
        if "database" in data and data["database"] == "connected":
            log_test("Health Check - MongoDB Connected", True, f"Ping result: {data.get('ping', 'N/A')}")
        elif "database" in data and data["database"] == "error":
            log_test("Health Check - MongoDB Connection", False, f"MongoDB Error: {data.get('error', 'Unknown')}")
        else:
            log_warning("Health Check", "MongoDB status unclear")
    else:
        log_test("Health Check", False, f"Status code: {response.status_code}")
except Exception as e:
    log_test("Health Check", False, f"Exception: {str(e)}")

# Test 2: Login with Existing User
print("\n🔍 TEST 2: Login with gussdub@gmail.com")
try:
    response = requests.post(
        f"{BACKEND_URL}/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        auth_token = data.get("access_token")
        user_data = data.get("user", {})
        
        if auth_token:
            log_test("Login - Authentication", True, f"Token received, User: {user_data.get('email')}")
            print(f"   Company: {user_data.get('company_name')}")
            print(f"   User ID: {user_data.get('id')}")
        else:
            log_test("Login - Authentication", False, "No token in response")
    else:
        log_test("Login - Authentication", False, f"Status: {response.status_code}, Response: {response.text}")
except Exception as e:
    log_test("Login - Authentication", False, f"Exception: {str(e)}")

if not auth_token:
    print("\n❌ CRITICAL: Cannot proceed without authentication token")
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    for result in test_results["passed"]:
        print(result)
    for result in test_results["failed"]:
        print(result)
    exit(1)

# Headers for authenticated requests
headers = {"Authorization": f"Bearer {auth_token}"}

# Test 3: Register New User
print("\n🔍 TEST 3: Register New User")
try:
    new_email = f"test_{datetime.now().timestamp()}@facturepro.com"
    response = requests.post(
        f"{BACKEND_URL}/auth/register",
        json={
            "email": new_email,
            "password": "TestPass123!",
            "company_name": "Test Company Inc"
        },
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get("access_token") and data.get("user"):
            log_test("Register - New User Creation", True, f"User created: {new_email}")
            print(f"   User ID: {data['user'].get('id')}")
        else:
            log_test("Register - New User Creation", False, "Missing token or user data")
    else:
        log_test("Register - New User Creation", False, f"Status: {response.status_code}, Response: {response.text}")
except Exception as e:
    log_test("Register - New User Creation", False, f"Exception: {str(e)}")

# Test 4: Forgot Password Workflow
print("\n🔍 TEST 4: Forgot Password Workflow")
try:
    # Step 1: Request reset token
    response = requests.post(
        f"{BACKEND_URL}/auth/forgot-password",
        json={"email": TEST_EMAIL},
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        reset_token = data.get("reset_token")
        
        if reset_token:
            log_test("Forgot Password - Token Generation", True, "Reset token generated")
            
            # Step 2: Reset password
            response2 = requests.post(
                f"{BACKEND_URL}/auth/reset-password",
                json={"token": reset_token, "new_password": TEST_PASSWORD},
                timeout=10
            )
            
            if response2.status_code == 200:
                log_test("Forgot Password - Password Reset", True, "Password reset successful")
            else:
                log_test("Forgot Password - Password Reset", False, f"Status: {response2.status_code}")
        else:
            log_test("Forgot Password - Token Generation", False, "No reset token in response")
    else:
        log_test("Forgot Password - Token Generation", False, f"Status: {response.status_code}")
except Exception as e:
    log_test("Forgot Password Workflow", False, f"Exception: {str(e)}")

# Test 5: Get Clients
print("\n🔍 TEST 5: Get Clients")
try:
    response = requests.get(f"{BACKEND_URL}/clients", headers=headers, timeout=10)
    
    if response.status_code == 200:
        clients = response.json()
        log_test("Get Clients", True, f"Retrieved {len(clients)} clients")
        if clients:
            print(f"   Sample client: {clients[0].get('name')} ({clients[0].get('email')})")
    else:
        log_test("Get Clients", False, f"Status: {response.status_code}, Response: {response.text}")
except Exception as e:
    log_test("Get Clients", False, f"Exception: {str(e)}")

# Test 6: Create Client
print("\n🔍 TEST 6: Create Client")
try:
    client_data = {
        "name": "Test Client PyMongo",
        "email": "pymongo.test@client.com",
        "phone": "514-555-1234",
        "address": "456 Test Avenue",
        "city": "Montréal",
        "postal_code": "H2X 1Y3",
        "country": "Canada"
    }
    
    response = requests.post(
        f"{BACKEND_URL}/clients",
        json=client_data,
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        client = response.json()
        test_client_id = client.get("id")
        log_test("Create Client", True, f"Client created: {client.get('name')}")
        print(f"   Client ID: {test_client_id}")
        print(f"   Email: {client.get('email')}")
    else:
        log_test("Create Client", False, f"Status: {response.status_code}, Response: {response.text}")
except Exception as e:
    log_test("Create Client", False, f"Exception: {str(e)}")

# Test 7: Update Client
if test_client_id:
    print("\n🔍 TEST 7: Update Client")
    try:
        update_data = {
            "name": "Test Client PyMongo UPDATED",
            "email": "pymongo.updated@client.com",
            "phone": "514-555-9999"
        }
        
        response = requests.put(
            f"{BACKEND_URL}/clients/{test_client_id}",
            json=update_data,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            updated_client = response.json()
            log_test("Update Client", True, f"Client updated: {updated_client.get('name')}")
        else:
            log_test("Update Client", False, f"Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        log_test("Update Client", False, f"Exception: {str(e)}")

# Test 8: Dashboard Stats
print("\n🔍 TEST 8: Dashboard Stats")
try:
    response = requests.get(f"{BACKEND_URL}/dashboard/stats", headers=headers, timeout=10)
    
    if response.status_code == 200:
        stats = response.json()
        log_test("Dashboard Stats", True, "Stats retrieved successfully")
        print(f"   Clients: {stats.get('total_clients', 0)}")
        print(f"   Invoices: {stats.get('total_invoices', 0)}")
        print(f"   Quotes: {stats.get('total_quotes', 0)}")
        print(f"   Products: {stats.get('total_products', 0)}")
        print(f"   Revenue: ${stats.get('total_revenue', 0)}")
    else:
        log_test("Dashboard Stats", False, f"Status: {response.status_code}, Response: {response.text}")
except Exception as e:
    log_test("Dashboard Stats", False, f"Exception: {str(e)}")

# Test 9: Get Products
print("\n🔍 TEST 9: Get Products")
try:
    response = requests.get(f"{BACKEND_URL}/products", headers=headers, timeout=10)
    
    if response.status_code == 200:
        products = response.json()
        log_test("Get Products", True, f"Retrieved {len(products)} products")
        if products:
            print(f"   Sample product: {products[0].get('name')} - ${products[0].get('unit_price')}")
    else:
        log_test("Get Products", False, f"Status: {response.status_code}, Response: {response.text}")
except Exception as e:
    log_test("Get Products", False, f"Exception: {str(e)}")

# Test 10: Create Product
print("\n🔍 TEST 10: Create Product")
try:
    product_data = {
        "name": "PyMongo Test Service",
        "description": "Testing PyMongo Async implementation",
        "unit_price": 150.00,
        "unit": "heure",
        "category": "Services"
    }
    
    response = requests.post(
        f"{BACKEND_URL}/products",
        json=product_data,
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        product = response.json()
        log_test("Create Product", True, f"Product created: {product.get('name')}")
        print(f"   Price: ${product.get('unit_price')}")
    else:
        log_test("Create Product", False, f"Status: {response.status_code}, Response: {response.text}")
except Exception as e:
    log_test("Create Product", False, f"Exception: {str(e)}")

# Test 11: Get Invoices
print("\n🔍 TEST 11: Get Invoices")
try:
    response = requests.get(f"{BACKEND_URL}/invoices", headers=headers, timeout=10)
    
    if response.status_code == 200:
        invoices = response.json()
        log_test("Get Invoices", True, f"Retrieved {len(invoices)} invoices")
    else:
        log_test("Get Invoices", False, f"Status: {response.status_code}, Response: {response.text}")
except Exception as e:
    log_test("Get Invoices", False, f"Exception: {str(e)}")

# Test 12: Create Invoice
if test_client_id:
    print("\n🔍 TEST 12: Create Invoice")
    try:
        invoice_data = {
            "client_id": test_client_id,
            "due_date": (datetime.now() + timedelta(days=30)).isoformat(),
            "items": [
                {
                    "description": "PyMongo Testing Service",
                    "quantity": 5,
                    "unit_price": 100.00,
                    "total": 500.00
                }
            ],
            "province": "QC",
            "notes": "Test invoice for PyMongo Async"
        }
        
        response = requests.post(
            f"{BACKEND_URL}/invoices",
            json=invoice_data,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            invoice = response.json()
            log_test("Create Invoice", True, f"Invoice created: {invoice.get('invoice_number')}")
            print(f"   Subtotal: ${invoice.get('subtotal')}")
            print(f"   GST: ${invoice.get('gst_amount')}")
            print(f"   PST: ${invoice.get('pst_amount')}")
            print(f"   Total: ${invoice.get('total')}")
        else:
            log_test("Create Invoice", False, f"Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        log_test("Create Invoice", False, f"Exception: {str(e)}")

# Test 13: Get Quotes
print("\n🔍 TEST 13: Get Quotes")
try:
    response = requests.get(f"{BACKEND_URL}/quotes", headers=headers, timeout=10)
    
    if response.status_code == 200:
        quotes = response.json()
        log_test("Get Quotes", True, f"Retrieved {len(quotes)} quotes")
    else:
        log_test("Get Quotes", False, f"Status: {response.status_code}, Response: {response.text}")
except Exception as e:
    log_test("Get Quotes", False, f"Exception: {str(e)}")

# Test 14: Create Quote
if test_client_id:
    print("\n🔍 TEST 14: Create Quote")
    try:
        quote_data = {
            "client_id": test_client_id,
            "valid_until": (datetime.now() + timedelta(days=30)).isoformat(),
            "items": [
                {
                    "description": "PyMongo Testing Quote",
                    "quantity": 3,
                    "unit_price": 200.00,
                    "total": 600.00
                }
            ],
            "notes": "Test quote for PyMongo Async"
        }
        
        response = requests.post(
            f"{BACKEND_URL}/quotes",
            json=quote_data,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            quote = response.json()
            log_test("Create Quote", True, f"Quote created: {quote.get('quote_number')}")
        else:
            log_test("Create Quote", False, f"Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        log_test("Create Quote", False, f"Exception: {str(e)}")

# Test 15: Get Company Settings
print("\n🔍 TEST 15: Get Company Settings")
try:
    response = requests.get(f"{BACKEND_URL}/settings/company", headers=headers, timeout=10)
    
    if response.status_code == 200:
        settings = response.json()
        log_test("Get Company Settings", True, "Settings retrieved")
        print(f"   Company: {settings.get('company_name')}")
        print(f"   Email: {settings.get('email')}")
        print(f"   GST: {settings.get('gst_number', 'N/A')}")
    else:
        log_test("Get Company Settings", False, f"Status: {response.status_code}, Response: {response.text}")
except Exception as e:
    log_test("Get Company Settings", False, f"Exception: {str(e)}")

# Test 16: Update Company Settings
print("\n🔍 TEST 16: Update Company Settings")
try:
    settings_data = {
        "phone": "514-555-7777",
        "address": "789 PyMongo Street",
        "city": "Montréal"
    }
    
    response = requests.put(
        f"{BACKEND_URL}/settings/company",
        json=settings_data,
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        log_test("Update Company Settings", True, "Settings updated successfully")
    else:
        log_test("Update Company Settings", False, f"Status: {response.status_code}, Response: {response.text}")
except Exception as e:
    log_test("Update Company Settings", False, f"Exception: {str(e)}")

# Test 17: Upload Logo URL and Set Primary Color
print("\n🔍 TEST 17: Upload Logo URL and Set Primary Color")
try:
    logo_data = {
        "logo_url": "https://example.com/logo.png"
    }
    
    response = requests.post(
        f"{BACKEND_URL}/settings/company/upload-logo",
        json=logo_data,
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        result = response.json()
        log_test("Upload Logo URL", True, f"Logo URL saved: {result.get('logo_url')}")
    else:
        log_test("Upload Logo URL", False, f"Status: {response.status_code}, Response: {response.text}")
        
    # Also set primary color for branding
    settings_data = {
        "primary_color": "#2563eb"
    }
    
    response = requests.put(
        f"{BACKEND_URL}/settings/company",
        json=settings_data,
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        log_test("Set Primary Color", True, "Primary color set to #2563eb")
    else:
        log_test("Set Primary Color", False, f"Status: {response.status_code}")
        
except Exception as e:
    log_test("Upload Logo URL", False, f"Exception: {str(e)}")

# Test 18: Delete Client (cleanup)
if test_client_id:
    print("\n🔍 TEST 18: Delete Client")
    try:
        response = requests.delete(
            f"{BACKEND_URL}/clients/{test_client_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            log_test("Delete Client", True, "Client deleted successfully")
        else:
            log_test("Delete Client", False, f"Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        log_test("Delete Client", False, f"Exception: {str(e)}")

# Final Summary
print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)

print(f"\n✅ PASSED: {len(test_results['passed'])}")
for result in test_results["passed"]:
    print(f"  {result}")

if test_results["warnings"]:
    print(f"\n⚠️  WARNINGS: {len(test_results['warnings'])}")
    for result in test_results["warnings"]:
        print(f"  {result}")

if test_results["failed"]:
    print(f"\n❌ FAILED: {len(test_results['failed'])}")
    for result in test_results["failed"]:
        print(f"  {result}")
else:
    print("\n🎉 ALL TESTS PASSED!")

print("\n" + "=" * 80)
print(f"Total Tests: {len(test_results['passed']) + len(test_results['failed'])}")
print(f"Pass Rate: {len(test_results['passed']) / (len(test_results['passed']) + len(test_results['failed'])) * 100:.1f}%")
print("=" * 80)
