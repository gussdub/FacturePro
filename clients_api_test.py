#!/usr/bin/env python3
"""
Specific test for clients API issue reported by gussdub@gmail.com
Tests the exact scenario: user can't select clients in invoice/quote creation
"""

import requests
import json
import sys
from datetime import datetime, timedelta

class ClientsAPITester:
    def __init__(self, base_url="https://facture-wizard.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None
        self.user_id = None
        self.test_results = []

    def log_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {details}")
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details
        })

    def make_request(self, method: str, endpoint: str, data: dict = None, expected_status: int = 200):
        """Make HTTP request"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=10)
            else:
                return False, {"error": f"Unsupported method: {method}"}

            success = response.status_code == expected_status
            try:
                response_data = response.json()
            except:
                response_data = {"status_code": response.status_code, "text": response.text}

            return success, response_data

        except requests.exceptions.RequestException as e:
            return False, {"error": str(e)}

    def setup_test_user(self):
        """Setup a test user account"""
        # Try to create a test user that simulates gussdub@gmail.com scenario
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        test_email = f"testgussdub{timestamp}@gmail.com"
        
        register_data = {
            "email": test_email,
            "password": "testpass123",
            "company_name": "Test Gussdub Company"
        }
        
        success, response = self.make_request('POST', 'auth/register', register_data, 200)
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.user_id = response['user']['id']
            self.log_result("User Setup", True, f"Created test user: {test_email}")
            return True
        else:
            self.log_result("User Setup", False, f"Failed to create user: {response}")
            return False

    def test_clients_api_basic(self):
        """Test basic clients API functionality"""
        print("\n🔍 Testing Basic Clients API...")
        
        # Test 1: GET /api/clients (should return empty list initially)
        success, response = self.make_request('GET', 'clients', expected_status=200)
        if success and isinstance(response, list):
            self.log_result("GET /api/clients", True, f"Returns list with {len(response)} clients")
            initial_count = len(response)
        else:
            self.log_result("GET /api/clients", False, f"Failed: {response}")
            return False

        # Test 2: Create test client (as specified in review request)
        test_client_data = {
            "name": "Client Test",
            "email": "client.test@example.com",
            "phone": "514-123-4567",
            "address": "123 Rue Test",
            "city": "Montréal",
            "postal_code": "H1A 1A1",
            "country": "Canada"
        }
        
        success, response = self.make_request('POST', 'clients', test_client_data, 200)
        if success and 'id' in response:
            client_id = response['id']
            self.log_result("POST /api/clients", True, f"Created client with ID: {client_id}")
            
            # Verify client has required fields for frontend
            required_fields = ['id', 'name', 'email']
            missing_fields = [field for field in required_fields if field not in response]
            
            if not missing_fields:
                self.log_result("Client Data Structure", True, f"Client has required fields: {required_fields}")
            else:
                self.log_result("Client Data Structure", False, f"Missing fields: {missing_fields}")
                
        else:
            self.log_result("POST /api/clients", False, f"Failed: {response}")
            return False

        # Test 3: Verify client appears in GET /api/clients
        success, response = self.make_request('GET', 'clients', expected_status=200)
        if success and isinstance(response, list):
            new_count = len(response)
            if new_count > initial_count:
                self.log_result("Client in List", True, f"Client count increased from {initial_count} to {new_count}")
                
                # Find our test client
                test_client_found = False
                for client in response:
                    if client.get('name') == 'Client Test' and client.get('email') == 'client.test@example.com':
                        test_client_found = True
                        # Check if it has the fields needed for frontend selection
                        if all(field in client for field in ['id', 'name', 'email']):
                            self.log_result("Client Frontend Fields", True, "Client has id, name, email for selection")
                        else:
                            self.log_result("Client Frontend Fields", False, f"Client missing selection fields: {client}")
                        break
                
                if test_client_found:
                    self.log_result("Test Client Found", True, "Test client found in clients list")
                else:
                    self.log_result("Test Client Found", False, "Test client not found in list")
            else:
                self.log_result("Client in List", False, f"Client count didn't increase: {new_count} vs {initial_count}")
        else:
            self.log_result("Client in List", False, f"Failed to get updated list: {response}")

        return True

    def test_invoice_quote_client_selection(self):
        """Test client selection in invoice/quote creation"""
        print("\n🔍 Testing Client Selection in Invoice/Quote Creation...")
        
        # First, get clients list to use in forms
        success, clients_response = self.make_request('GET', 'clients', expected_status=200)
        if not success or not isinstance(clients_response, list) or len(clients_response) == 0:
            self.log_result("Clients Available for Forms", False, "No clients available for invoice/quote creation")
            return False
        
        self.log_result("Clients Available for Forms", True, f"{len(clients_response)} clients available")
        
        # Use the first client for testing
        test_client = clients_response[0]
        client_id = test_client.get('id')
        
        if not client_id:
            self.log_result("Client ID Available", False, "Client doesn't have ID field")
            return False
        
        self.log_result("Client ID Available", True, f"Using client ID: {client_id}")

        # Test 1: Create invoice with client selection
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
            "notes": "Test invoice for client selection"
        }
        
        success, response = self.make_request('POST', 'invoices', invoice_data, 200)
        if success and 'id' in response:
            invoice_id = response['id']
            self.log_result("Create Invoice with Client", True, f"Created invoice {response.get('invoice_number')} with client")
            
            # Verify the invoice has the correct client_id
            if response.get('client_id') == client_id:
                self.log_result("Invoice Client Association", True, "Invoice correctly associated with client")
            else:
                self.log_result("Invoice Client Association", False, f"Client ID mismatch: expected {client_id}, got {response.get('client_id')}")
        else:
            self.log_result("Create Invoice with Client", False, f"Failed: {response}")

        # Test 2: Create quote with client selection
        quote_data = {
            "client_id": client_id,
            "valid_until": (datetime.now() + timedelta(days=30)).isoformat(),
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
            "notes": "Test quote for client selection"
        }
        
        success, response = self.make_request('POST', 'quotes', quote_data, 200)
        if success and 'id' in response:
            quote_id = response['id']
            self.log_result("Create Quote with Client", True, f"Created quote {response.get('quote_number')} with client")
            
            # Verify the quote has the correct client_id
            if response.get('client_id') == client_id:
                self.log_result("Quote Client Association", True, "Quote correctly associated with client")
            else:
                self.log_result("Quote Client Association", False, f"Client ID mismatch: expected {client_id}, got {response.get('client_id')}")
        else:
            self.log_result("Create Quote with Client", False, f"Failed: {response}")

        return True

    def test_subscription_access(self):
        """Test that subscription doesn't block client access"""
        print("\n🔍 Testing Subscription Access...")
        
        # Check subscription status
        success, response = self.make_request('GET', 'subscription/user-status', expected_status=200)
        if success:
            has_access = response.get('has_access')
            subscription_status = response.get('subscription_status')
            days_remaining = response.get('days_remaining', 0)
            
            self.log_result("Subscription Status", True, f"Status: {subscription_status}, Access: {has_access}, Days: {days_remaining}")
            
            if has_access:
                self.log_result("Subscription Access", True, "User has subscription access")
            else:
                self.log_result("Subscription Access", False, "User blocked by subscription")
        else:
            self.log_result("Subscription Status", False, f"Failed: {response}")

        # Test that clients API works regardless of subscription
        success, response = self.make_request('GET', 'clients', expected_status=200)
        if success:
            self.log_result("Clients API Access", True, "Clients API accessible")
        else:
            if 'abonnement' in str(response).lower() or response.get('status_code') == 403:
                self.log_result("Clients API Access", False, f"Blocked by subscription: {response}")
            else:
                self.log_result("Clients API Access", False, f"Other error: {response}")

        return True

    def test_user_isolation(self):
        """Test that users only see their own clients"""
        print("\n🔍 Testing User Isolation...")
        
        # Get current user's clients
        success, user1_clients = self.make_request('GET', 'clients', expected_status=200)
        if not success:
            self.log_result("User 1 Clients", False, f"Failed: {user1_clients}")
            return False
        
        user1_count = len(user1_clients)
        self.log_result("User 1 Clients", True, f"User 1 has {user1_count} clients")
        
        # Create another user
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        user2_email = f"testuser2_{timestamp}@example.com"
        
        user2_data = {
            "email": user2_email,
            "password": "testpass123",
            "company_name": "Test User 2 Company"
        }
        
        success, response = self.make_request('POST', 'auth/register', user2_data, 200)
        if not success:
            self.log_result("User 2 Setup", False, f"Failed: {response}")
            return False
        
        # Store original token and switch to user 2
        original_token = self.token
        self.token = response['access_token']
        
        # Check user 2's clients (should be empty)
        success, user2_clients = self.make_request('GET', 'clients', expected_status=200)
        if success:
            user2_count = len(user2_clients)
            if user2_count == 0:
                self.log_result("User Isolation", True, f"User 2 has {user2_count} clients (proper isolation)")
            else:
                # Check if any of user 1's clients are visible
                user1_client_names = {c.get('name') for c in user1_clients}
                user2_client_names = {c.get('name') for c in user2_clients}
                overlap = user1_client_names.intersection(user2_client_names)
                
                if overlap:
                    self.log_result("User Isolation", False, f"User 2 can see User 1's clients: {overlap}")
                else:
                    self.log_result("User Isolation", True, f"User 2 has {user2_count} own clients (proper isolation)")
        else:
            self.log_result("User Isolation", False, f"Failed: {user2_clients}")
        
        # Restore original token
        self.token = original_token
        return True

    def cleanup(self):
        """Clean up test data"""
        print("\n🧹 Cleaning up test data...")
        
        # Get all clients and delete test ones
        success, clients = self.make_request('GET', 'clients', expected_status=200)
        if success and isinstance(clients, list):
            for client in clients:
                if client.get('name') == 'Client Test' or 'test' in client.get('name', '').lower():
                    client_id = client.get('id')
                    success, _ = self.make_request('DELETE', f'clients/{client_id}', expected_status=200)
                    if success:
                        print(f"✅ Deleted test client: {client.get('name')}")
                    else:
                        print(f"⚠️ Failed to delete client: {client.get('name')}")

    def run_tests(self):
        """Run all client API tests"""
        print("🚀 Starting Clients API Tests for gussdub@gmail.com Issue")
        print("=" * 60)
        
        # Setup
        if not self.setup_test_user():
            print("❌ Failed to setup test user, aborting tests")
            return False
        
        # Run tests
        self.test_subscription_access()
        self.test_clients_api_basic()
        self.test_invoice_quote_client_selection()
        self.test_user_isolation()
        
        # Cleanup
        self.cleanup()
        
        # Summary
        print("\n" + "=" * 60)
        passed = sum(1 for result in self.test_results if result['success'])
        total = len(self.test_results)
        
        print(f"📊 Test Summary: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! Clients API is working correctly.")
            return True
        else:
            print(f"⚠️ {total - passed} tests failed. Issues detected in clients API.")
            
            # Show failed tests
            print("\n❌ Failed Tests:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  - {result['test']}: {result['details']}")
            
            return False

def main():
    tester = ClientsAPITester()
    success = tester.run_tests()
    
    # Save results
    with open('/app/clients_api_test_results.json', 'w') as f:
        json.dump({
            'summary': {
                'total_tests': len(tester.test_results),
                'passed_tests': sum(1 for r in tester.test_results if r['success']),
                'success': success
            },
            'test_results': tester.test_results
        }, f, indent=2)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())