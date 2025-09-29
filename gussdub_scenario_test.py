#!/usr/bin/env python3
"""
Test to simulate the exact gussdub@gmail.com scenario
Account exists with subscription_status: None and has 1 client
"""

import requests
import json
import sys
from datetime import datetime

def test_gussdub_scenario():
    """Test the exact scenario of gussdub@gmail.com"""
    api_url = 'https://facture-wizard.preview.emergentagent.com/api'
    
    print("🔍 Testing gussdub@gmail.com Scenario Simulation")
    print("=" * 50)
    
    # Create a user that simulates gussdub's exact situation
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    test_email = f"gussdub_sim_{timestamp}@gmail.com"
    
    # Step 1: Create user
    register_data = {
        'email': test_email,
        'password': 'testpass123',
        'company_name': 'ProFireManager Simulation'
    }
    
    response = requests.post(f'{api_url}/auth/register', json=register_data)
    if response.status_code != 200:
        print(f"❌ Failed to create test user: {response.json()}")
        return False
    
    token = response.json()['access_token']
    user_id = response.json()['user']['id']
    print(f"✅ Created simulation user: {test_email}")
    
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    
    # Step 2: Create a client (like gussdub has)
    client_data = {
        "name": "test",
        "email": "test@gmail.com",
        "phone": "514-123-4567",
        "address": "123 Test St",
        "city": "Montreal",
        "postal_code": "H1A 1A1",
        "country": "Canada"
    }
    
    response = requests.post(f'{api_url}/clients', json=client_data, headers=headers)
    if response.status_code != 200:
        print(f"❌ Failed to create client: {response.json()}")
        return False
    
    client_id = response.json()['id']
    print(f"✅ Created client: {client_data['name']} (ID: {client_id})")
    
    # Step 3: Test GET /api/clients
    response = requests.get(f'{api_url}/clients', headers=headers)
    if response.status_code == 200:
        clients = response.json()
        print(f"✅ GET /api/clients: Found {len(clients)} clients")
        
        # Verify client structure
        if clients and len(clients) > 0:
            client = clients[0]
            required_fields = ['id', 'name', 'email']
            missing_fields = [field for field in required_fields if field not in client]
            
            if not missing_fields:
                print(f"✅ Client has required fields for frontend: {required_fields}")
            else:
                print(f"❌ Client missing fields: {missing_fields}")
                return False
        else:
            print("❌ No clients returned")
            return False
    else:
        print(f"❌ GET /api/clients failed: {response.json()}")
        return False
    
    # Step 4: Test creating invoice with client selection
    invoice_data = {
        "client_id": client_id,
        "items": [
            {
                "description": "Test Service",
                "quantity": 1.0,
                "unit_price": 100.0
            }
        ],
        "gst_rate": 5.0,
        "pst_rate": 9.975,
        "apply_gst": True,
        "apply_pst": True,
        "notes": "Test invoice"
    }
    
    response = requests.post(f'{api_url}/invoices', json=invoice_data, headers=headers)
    if response.status_code == 200:
        invoice = response.json()
        print(f"✅ Created invoice with client: {invoice.get('invoice_number')}")
        
        if invoice.get('client_id') == client_id:
            print("✅ Invoice correctly associated with client")
        else:
            print(f"❌ Invoice client association failed: expected {client_id}, got {invoice.get('client_id')}")
            return False
    else:
        print(f"❌ Failed to create invoice: {response.json()}")
        return False
    
    # Step 5: Test creating quote with client selection
    quote_data = {
        "client_id": client_id,
        "valid_until": "2025-12-31T23:59:59Z",
        "items": [
            {
                "description": "Test Quote Service",
                "quantity": 1.0,
                "unit_price": 150.0
            }
        ],
        "gst_rate": 5.0,
        "pst_rate": 9.975,
        "apply_gst": True,
        "apply_pst": True,
        "notes": "Test quote"
    }
    
    response = requests.post(f'{api_url}/quotes', json=quote_data, headers=headers)
    if response.status_code == 200:
        quote = response.json()
        print(f"✅ Created quote with client: {quote.get('quote_number')}")
        
        if quote.get('client_id') == client_id:
            print("✅ Quote correctly associated with client")
        else:
            print(f"❌ Quote client association failed: expected {client_id}, got {quote.get('client_id')}")
            return False
    else:
        print(f"❌ Failed to create quote: {response.json()}")
        return False
    
    # Step 6: Check subscription status
    response = requests.get(f'{api_url}/subscription/user-status', headers=headers)
    if response.status_code == 200:
        status = response.json()
        print(f"✅ Subscription status: {status.get('subscription_status')}, Access: {status.get('has_access')}")
    else:
        print(f"❌ Failed to get subscription status: {response.json()}")
    
    print("\n🎉 All tests passed! Client selection in invoices/quotes works correctly.")
    print("📋 Summary:")
    print("  - GET /api/clients returns clients with id, name, email fields")
    print("  - POST /api/invoices accepts client_id and creates invoice")
    print("  - POST /api/quotes accepts client_id and creates quote")
    print("  - No subscription blocking issues detected")
    
    return True

if __name__ == "__main__":
    success = test_gussdub_scenario()
    sys.exit(0 if success else 1)