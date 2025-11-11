#!/usr/bin/env python3
"""
Test send_quote_email endpoint specifically
"""

import requests
import json
from datetime import datetime, timedelta

BACKEND_URL = "https://facturepro.preview.emergentagent.com/api"
TEST_EMAIL = "gussdub@gmail.com"
TEST_PASSWORD = "testpass123"

print("=" * 80)
print("TESTING SEND_QUOTE_EMAIL ENDPOINT")
print("=" * 80)

# Step 1: Login
print("1. Logging in...")
response = requests.post(
    f"{BACKEND_URL}/auth/login",
    json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    timeout=10
)

if response.status_code != 200:
    print(f"❌ Login failed: {response.text}")
    exit(1)

data = response.json()
auth_token = data.get("access_token")
headers = {"Authorization": f"Bearer {auth_token}"}
print("✅ Login successful")

# Step 2: Create a test client
print("\n2. Creating test client...")
client_data = {
    "name": "Email Test Client",
    "email": "test.client@example.com",
    "phone": "514-555-1234",
    "address": "123 Test Street",
    "city": "Montreal",
    "postal_code": "H1A 1A1",
    "country": "Canada"
}

response = requests.post(
    f"{BACKEND_URL}/clients",
    json=client_data,
    headers=headers,
    timeout=10
)

if response.status_code != 200:
    print(f"❌ Client creation failed: {response.text}")
    exit(1)

client = response.json()
client_id = client.get("id")
print(f"✅ Client created: {client.get('name')} (ID: {client_id})")

# Step 3: Update company settings with logo and primary color
print("\n3. Setting up company branding...")
settings_data = {
    "logo_url": "https://via.placeholder.com/100x100/2563eb/ffffff?text=LOGO",
    "primary_color": "#2563eb"
}

response = requests.put(
    f"{BACKEND_URL}/settings/company",
    json=settings_data,
    headers=headers,
    timeout=10
)

if response.status_code == 200:
    print("✅ Company branding updated")
else:
    print(f"⚠️  Branding update failed: {response.text}")

# Step 4: Create a test quote
print("\n4. Creating test quote...")
quote_data = {
    "client_id": client_id,
    "valid_until": (datetime.now() + timedelta(days=30)).isoformat(),
    "items": [
        {
            "description": "Email Customization Test Service",
            "quantity": 2,
            "unit_price": 150.00,
            "total": 300.00
        },
        {
            "description": "PDF Generation Test",
            "quantity": 1,
            "unit_price": 100.00,
            "total": 100.00
        }
    ],
    "notes": "This is a test quote for email customization with PDF attachment functionality."
}

response = requests.post(
    f"{BACKEND_URL}/quotes",
    json=quote_data,
    headers=headers,
    timeout=10
)

if response.status_code != 200:
    print(f"❌ Quote creation failed: {response.text}")
    exit(1)

quote = response.json()
quote_id = quote.get("id")
quote_number = quote.get("quote_number")
print(f"✅ Quote created: {quote_number} (ID: {quote_id})")
print(f"   Subtotal: ${quote.get('subtotal')}")
print(f"   Total: ${quote.get('total')}")

# Step 5: Test send_quote_email endpoint
print(f"\n5. Testing send_quote_email endpoint...")
print(f"   Quote ID: {quote_id}")
print(f"   Endpoint: POST /api/quotes/{quote_id}/send-email")

response = requests.post(
    f"{BACKEND_URL}/quotes/{quote_id}/send-email",
    headers=headers,
    timeout=20  # Increased timeout for PDF generation
)

print(f"   Response Status: {response.status_code}")
print(f"   Response Body: {response.text}")

if response.status_code == 200:
    result = response.json()
    print("✅ Email sent successfully!")
    print(f"   Message: {result.get('message')}")
    
    # Step 6: Verify quote status was updated
    print("\n6. Verifying quote status update...")
    response = requests.get(f"{BACKEND_URL}/quotes", headers=headers, timeout=10)
    
    if response.status_code == 200:
        quotes = response.json()
        sent_quote = next((q for q in quotes if q.get('id') == quote_id), None)
        
        if sent_quote:
            status = sent_quote.get('status')
            print(f"   Quote status: {status}")
            
            if status == 'sent':
                print("✅ Quote status correctly updated to 'sent'")
            else:
                print(f"❌ Quote status should be 'sent' but is '{status}'")
        else:
            print("❌ Could not find the quote to verify status")
    else:
        print(f"❌ Failed to retrieve quotes: {response.text}")
        
else:
    print(f"❌ Email sending failed!")
    print(f"   Error details: {response.text}")

# Step 7: Cleanup - Delete test client
print(f"\n7. Cleaning up...")
response = requests.delete(
    f"{BACKEND_URL}/clients/{client_id}",
    headers=headers,
    timeout=10
)

if response.status_code == 200:
    print("✅ Test client deleted")
else:
    print(f"⚠️  Failed to delete test client: {response.text}")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)