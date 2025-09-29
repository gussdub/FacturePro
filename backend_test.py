import requests
import sys
import json
from datetime import datetime, timedelta
from typing import Dict, Any

class BillingAPITester:
    def __init__(self, base_url="https://facture-wizard.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None
        self.user_id = None
        self.test_client_id = None
        self.test_invoice_id = None
        self.test_quote_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name: str, success: bool, details: str = "", response_data: Any = None):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}: PASSED")
        else:
            print(f"❌ {name}: FAILED - {details}")
        
        self.test_results.append({
            "name": name,
            "success": success,
            "details": details,
            "response_data": response_data
        })

    def make_request(self, method: str, endpoint: str, data: Dict = None, expected_status: int = 200) -> tuple:
        """Make HTTP request and return success status and response"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=10)
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

    def test_user_registration(self):
        """Test user registration"""
        test_data = {
            "email": f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}@example.com",
            "password": "Test123",
            "company_name": "Test Company"
        }
        
        success, response = self.make_request('POST', 'auth/register', test_data, 200)
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.user_id = response['user']['id']
            self.log_test("User Registration", True, f"User created with ID: {self.user_id}")
            return True
        else:
            self.log_test("User Registration", False, f"Registration failed: {response}")
            return False

    def test_user_login(self):
        """Test user login with existing credentials"""
        # Test with the specific credentials mentioned in the review request
        login_data = {
            "email": "test@facturepro.com",
            "password": "testpass123"
        }
        
        success, response = self.make_request('POST', 'auth/login', login_data, 200)
        
        if success and 'access_token' in response:
            # Update token for subsequent tests
            self.token = response['access_token']
            self.user_id = response['user']['id']
            self.log_test("User Login (Existing User)", True, f"Login successful for user: test@facturepro.com")
            return True
        else:
            # If the specific user doesn't exist, create it first
            register_data = {
                "email": "test@facturepro.com",
                "password": "testpass123",
                "company_name": "FacturePro Test Company"
            }
            
            success, _ = self.make_request('POST', 'auth/register', register_data, 200)
            if success:
                # Now try login again
                success, response = self.make_request('POST', 'auth/login', login_data, 200)
                if success and 'access_token' in response:
                    self.token = response['access_token']
                    self.user_id = response['user']['id']
                    self.log_test("User Login (After Registration)", True, f"Login successful after registration")
                    return True
            
            self.log_test("User Login", False, f"Login failed: {response}")
            return False

    def test_dashboard_stats(self):
        """Test dashboard statistics endpoint"""
        success, response = self.make_request('GET', 'dashboard/stats', expected_status=200)
        
        if success:
            required_fields = ['total_clients', 'total_invoices', 'total_quotes', 'pending_invoices', 'total_revenue']
            missing_fields = [field for field in required_fields if field not in response]
            
            if not missing_fields:
                self.log_test("Dashboard Stats", True, f"All stats fields present: {response}")
                return True
            else:
                self.log_test("Dashboard Stats", False, f"Missing fields: {missing_fields}")
                return False
        else:
            self.log_test("Dashboard Stats", False, f"Request failed: {response}")
            return False

    def test_client_management(self):
        """Test client CRUD operations"""
        # Test create client
        client_data = {
            "name": "Test Client",
            "email": "testclient@example.com",
            "phone": "+33123456789",
            "address": "123 Test Street",
            "city": "Paris",
            "postal_code": "75001",
            "country": "France"
        }
        
        success, response = self.make_request('POST', 'clients', client_data, 200)
        if success and 'id' in response:
            self.test_client_id = response['id']
            self.log_test("Create Client", True, f"Client created with ID: {self.test_client_id}")
        else:
            self.log_test("Create Client", False, f"Failed to create client: {response}")
            return False

        # Test get clients list
        success, response = self.make_request('GET', 'clients', expected_status=200)
        if success and isinstance(response, list):
            self.log_test("Get Clients List", True, f"Retrieved {len(response)} clients")
        else:
            self.log_test("Get Clients List", False, f"Failed to get clients: {response}")

        # Test get specific client
        success, response = self.make_request('GET', f'clients/{self.test_client_id}', expected_status=200)
        if success and response.get('id') == self.test_client_id:
            self.log_test("Get Specific Client", True, f"Retrieved client: {response['name']}")
        else:
            self.log_test("Get Specific Client", False, f"Failed to get client: {response}")

        # Test update client
        update_data = {
            "name": "Updated Test Client",
            "email": "updated@example.com",
            "phone": "+33987654321",
            "address": "456 Updated Street",
            "city": "Lyon",
            "postal_code": "69001",
            "country": "France"
        }
        
        success, response = self.make_request('PUT', f'clients/{self.test_client_id}', update_data, 200)
        if success and response.get('name') == "Updated Test Client":
            self.log_test("Update Client", True, f"Client updated successfully")
        else:
            self.log_test("Update Client", False, f"Failed to update client: {response}")

        return True

    def test_invoice_management(self):
        """Test invoice CRUD operations"""
        if not self.test_client_id:
            self.log_test("Invoice Management", False, "No test client available")
            return False

        # Test create invoice
        invoice_data = {
            "client_id": self.test_client_id,
            "due_date": (datetime.now() + timedelta(days=30)).isoformat(),
            "items": [
                {
                    "description": "Service de consultation",
                    "quantity": 2.0,
                    "unit_price": 100.0
                },
                {
                    "description": "Développement web",
                    "quantity": 10.0,
                    "unit_price": 75.0
                }
            ],
            "tax_rate": 20.0,
            "notes": "Facture de test"
        }
        
        success, response = self.make_request('POST', 'invoices', invoice_data, 200)
        if success and 'id' in response:
            self.test_invoice_id = response['id']
            expected_subtotal = 200.0 + 750.0  # 950.0
            expected_tax = expected_subtotal * 0.20  # 190.0
            expected_total = expected_subtotal + expected_tax  # 1140.0
            
            if (abs(response.get('subtotal', 0) - expected_subtotal) < 0.01 and
                abs(response.get('total', 0) - expected_total) < 0.01):
                self.log_test("Create Invoice", True, f"Invoice created with correct calculations: {response['invoice_number']}")
            else:
                self.log_test("Create Invoice", False, f"Invoice calculations incorrect: {response}")
        else:
            self.log_test("Create Invoice", False, f"Failed to create invoice: {response}")
            return False

        # Test get invoices list
        success, response = self.make_request('GET', 'invoices', expected_status=200)
        if success and isinstance(response, list):
            self.log_test("Get Invoices List", True, f"Retrieved {len(response)} invoices")
        else:
            self.log_test("Get Invoices List", False, f"Failed to get invoices: {response}")

        # Test update invoice status
        success, response = self.make_request('PUT', f'invoices/{self.test_invoice_id}/status?status=sent', expected_status=200)
        if success:
            self.log_test("Update Invoice Status", True, "Invoice status updated to sent")
        else:
            self.log_test("Update Invoice Status", False, f"Failed to update status: {response}")

        return True

    def test_quote_management(self):
        """Test quote CRUD operations"""
        if not self.test_client_id:
            self.log_test("Quote Management", False, "No test client available")
            return False

        # Test create quote
        quote_data = {
            "client_id": self.test_client_id,
            "valid_until": (datetime.now() + timedelta(days=15)).isoformat(),
            "items": [
                {
                    "description": "Audit SEO",
                    "quantity": 1.0,
                    "unit_price": 500.0
                }
            ],
            "tax_rate": 20.0,
            "notes": "Devis pour audit SEO"
        }
        
        success, response = self.make_request('POST', 'quotes', quote_data, 200)
        if success and 'id' in response:
            self.test_quote_id = response['id']
            expected_total = 500.0 * 1.20  # 600.0
            
            if abs(response.get('total', 0) - expected_total) < 0.01:
                self.log_test("Create Quote", True, f"Quote created: {response['quote_number']}")
            else:
                self.log_test("Create Quote", False, f"Quote calculations incorrect: {response}")
        else:
            self.log_test("Create Quote", False, f"Failed to create quote: {response}")
            return False

        # Test get quotes list
        success, response = self.make_request('GET', 'quotes', expected_status=200)
        if success and isinstance(response, list):
            self.log_test("Get Quotes List", True, f"Retrieved {len(response)} quotes")
        else:
            self.log_test("Get Quotes List", False, f"Failed to get quotes: {response}")

        # Test convert quote to invoice
        due_date = (datetime.now() + timedelta(days=30)).isoformat()
        success, response = self.make_request('POST', f'quotes/{self.test_quote_id}/convert?due_date={due_date}', expected_status=200)
        if success and 'invoice_number' in response:
            self.log_test("Convert Quote to Invoice", True, f"Quote converted to invoice: {response['invoice_number']}")
        else:
            self.log_test("Convert Quote to Invoice", False, f"Failed to convert quote: {response}")

        return True

    def test_company_settings(self):
        """Test company settings management"""
        # Test get company settings
        success, response = self.make_request('GET', 'settings/company', expected_status=200)
        if success and 'company_name' in response:
            self.log_test("Get Company Settings", True, f"Settings retrieved for: {response['company_name']}")
        else:
            self.log_test("Get Company Settings", False, f"Failed to get settings: {response}")
            return False

        # Test update company settings
        update_data = {
            "company_name": "Updated Test Company",
            "phone": "+33123456789",
            "address": "123 Business Street",
            "city": "Paris",
            "postal_code": "75001",
            "country": "France",
            "primary_color": "#FF6B6B",
            "secondary_color": "#4ECDC4"
        }
        
        success, response = self.make_request('PUT', 'settings/company', update_data, 200)
        if success and response.get('company_name') == "Updated Test Company":
            self.log_test("Update Company Settings", True, "Company settings updated successfully")
        else:
            self.log_test("Update Company Settings", False, f"Failed to update settings: {response}")

        return True

    def test_delete_invoice(self):
        """Test invoice deletion functionality"""
        if not self.test_client_id:
            self.log_test("Delete Invoice Setup", False, "No test client available")
            return False

        # First create an invoice to delete
        invoice_data = {
            "client_id": self.test_client_id,
            "due_date": (datetime.now() + timedelta(days=30)).isoformat(),
            "items": [
                {
                    "description": "Service à supprimer",
                    "quantity": 1.0,
                    "unit_price": 150.0
                }
            ],
            "gst_rate": 5.0,
            "pst_rate": 9.975,
            "apply_gst": True,
            "apply_pst": True,
            "notes": "Facture de test pour suppression"
        }
        
        success, response = self.make_request('POST', 'invoices', invoice_data, 200)
        if not success or 'id' not in response:
            self.log_test("Delete Invoice - Create Test Invoice", False, f"Failed to create test invoice: {response}")
            return False
        
        test_invoice_id = response['id']
        self.log_test("Delete Invoice - Create Test Invoice", True, f"Test invoice created: {test_invoice_id}")

        # Test successful deletion
        success, response = self.make_request('DELETE', f'invoices/{test_invoice_id}', expected_status=200)
        if success and response.get('message') == 'Invoice deleted successfully':
            self.log_test("Delete Invoice - Successful Deletion", True, f"Invoice {test_invoice_id} deleted successfully")
        else:
            self.log_test("Delete Invoice - Successful Deletion", False, f"Failed to delete invoice: {response}")
            return False

        # Verify invoice is actually deleted by trying to get it
        success, response = self.make_request('GET', f'invoices/{test_invoice_id}', expected_status=404)
        if not success and 'not found' in response.get('detail', '').lower():
            self.log_test("Delete Invoice - Verify Deletion", True, "Invoice correctly not found after deletion")
        else:
            self.log_test("Delete Invoice - Verify Deletion", False, f"Invoice still exists after deletion: {response}")

        # Test deletion of non-existent invoice
        fake_invoice_id = "non-existent-invoice-id"
        success, response = self.make_request('DELETE', f'invoices/{fake_invoice_id}', expected_status=404)
        if not success and 'not found' in response.get('detail', '').lower():
            self.log_test("Delete Invoice - Non-existent ID", True, "Correctly returned 404 for non-existent invoice")
        else:
            self.log_test("Delete Invoice - Non-existent ID", False, f"Should have returned 404: {response}")

        # Test unauthorized deletion (without token)
        # First create another invoice
        success, response = self.make_request('POST', 'invoices', invoice_data, 200)
        if success and 'id' in response:
            unauthorized_invoice_id = response['id']
            
            # Remove token temporarily
            old_token = self.token
            self.token = None
            
            success, response = self.make_request('DELETE', f'invoices/{unauthorized_invoice_id}', expected_status=403)
            if not success and 'not authenticated' in response.get('detail', '').lower():
                self.log_test("Delete Invoice - Unauthorized", True, "Correctly rejected unauthorized deletion")
            else:
                self.log_test("Delete Invoice - Unauthorized", False, f"Should have returned 403: {response}")
            
            # Restore token and cleanup
            self.token = old_token
            self.make_request('DELETE', f'invoices/{unauthorized_invoice_id}', expected_status=200)

        return True

    def test_delete_quote(self):
        """Test quote deletion functionality"""
        if not self.test_client_id:
            self.log_test("Delete Quote Setup", False, "No test client available")
            return False

        # First create a quote to delete
        quote_data = {
            "client_id": self.test_client_id,
            "valid_until": (datetime.now() + timedelta(days=15)).isoformat(),
            "items": [
                {
                    "description": "Devis à supprimer",
                    "quantity": 1.0,
                    "unit_price": 200.0
                }
            ],
            "gst_rate": 5.0,
            "pst_rate": 9.975,
            "apply_gst": True,
            "apply_pst": True,
            "notes": "Devis de test pour suppression"
        }
        
        success, response = self.make_request('POST', 'quotes', quote_data, 200)
        if not success or 'id' not in response:
            self.log_test("Delete Quote - Create Test Quote", False, f"Failed to create test quote: {response}")
            return False
        
        test_quote_id = response['id']
        self.log_test("Delete Quote - Create Test Quote", True, f"Test quote created: {test_quote_id}")

        # Test successful deletion
        success, response = self.make_request('DELETE', f'quotes/{test_quote_id}', expected_status=200)
        if success and response.get('message') == 'Quote deleted successfully':
            self.log_test("Delete Quote - Successful Deletion", True, f"Quote {test_quote_id} deleted successfully")
        else:
            self.log_test("Delete Quote - Successful Deletion", False, f"Failed to delete quote: {response}")
            return False

        # Verify quote is actually deleted by trying to get it (note: there's no GET single quote endpoint, so we check the list)
        success, response = self.make_request('GET', 'quotes', expected_status=200)
        if success and isinstance(response, list):
            deleted_quote_exists = any(quote.get('id') == test_quote_id for quote in response)
            if not deleted_quote_exists:
                self.log_test("Delete Quote - Verify Deletion", True, "Quote correctly not found in list after deletion")
            else:
                self.log_test("Delete Quote - Verify Deletion", False, "Quote still exists in list after deletion")
        else:
            self.log_test("Delete Quote - Verify Deletion", False, f"Failed to get quotes list: {response}")

        # Test deletion of non-existent quote
        fake_quote_id = "non-existent-quote-id"
        success, response = self.make_request('DELETE', f'quotes/{fake_quote_id}', expected_status=404)
        if not success and 'not found' in response.get('detail', '').lower():
            self.log_test("Delete Quote - Non-existent ID", True, "Correctly returned 404 for non-existent quote")
        else:
            self.log_test("Delete Quote - Non-existent ID", False, f"Should have returned 404: {response}")

        # Test unauthorized deletion (without token)
        # First create another quote
        success, response = self.make_request('POST', 'quotes', quote_data, 200)
        if success and 'id' in response:
            unauthorized_quote_id = response['id']
            
            # Remove token temporarily
            old_token = self.token
            self.token = None
            
            success, response = self.make_request('DELETE', f'quotes/{unauthorized_quote_id}', expected_status=403)
            if not success and 'not authenticated' in response.get('detail', '').lower():
                self.log_test("Delete Quote - Unauthorized", True, "Correctly rejected unauthorized deletion")
            else:
                self.log_test("Delete Quote - Unauthorized", False, f"Should have returned 403: {response}")
            
            # Restore token and cleanup
            self.token = old_token
            self.make_request('DELETE', f'quotes/{unauthorized_quote_id}', expected_status=200)

        return True

    def test_error_handling(self):
        """Test API error handling"""
        # Test unauthorized access (without token)
        old_token = self.token
        self.token = None
        
        success, response = self.make_request('GET', 'clients', expected_status=403)
        if not success and 'not authenticated' in response.get('detail', '').lower():
            self.log_test("Unauthorized Access", True, "Correctly rejected unauthorized request")
        else:
            self.log_test("Unauthorized Access", False, f"Should have returned 403: {response}")
        
        # Restore token
        self.token = old_token

        # Test invalid client ID
        success, response = self.make_request('GET', 'clients/invalid-id', expected_status=404)
        if not success and 'not found' in response.get('detail', '').lower():
            self.log_test("Invalid Client ID", True, "Correctly returned 404 for invalid client")
        else:
            self.log_test("Invalid Client ID", False, f"Should have returned 404: {response}")

        return True

    def cleanup_test_data(self):
        """Clean up test data"""
        if self.test_client_id:
            success, _ = self.make_request('DELETE', f'clients/{self.test_client_id}', expected_status=200)
            if success:
                print(f"✅ Cleaned up test client: {self.test_client_id}")
            else:
                print(f"⚠️ Failed to clean up test client: {self.test_client_id}")

    def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting Billing API Tests...")
        print(f"Testing against: {self.base_url}")
        print("=" * 60)

        # Authentication tests
        if not self.test_user_registration():
            print("❌ Registration failed, stopping tests")
            return False

        if not self.test_user_login():
            print("❌ Login failed, stopping tests")
            return False

        # Core functionality tests
        self.test_dashboard_stats()
        self.test_client_management()
        self.test_invoice_management()
        self.test_quote_management()
        
        # Delete functionality tests (specific to the review request)
        self.test_delete_invoice()
        self.test_delete_quote()
        
        self.test_company_settings()
        self.test_error_handling()

        # Cleanup
        self.cleanup_test_data()

        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return True
        else:
            print(f"⚠️ {self.tests_run - self.tests_passed} tests failed")
            return False

def main():
    tester = BillingAPITester()
    success = tester.run_all_tests()
    
    # Save detailed results
    with open('/app/backend_test_results.json', 'w') as f:
        json.dump({
            'summary': {
                'total_tests': tester.tests_run,
                'passed_tests': tester.tests_passed,
                'success_rate': (tester.tests_passed / tester.tests_run * 100) if tester.tests_run > 0 else 0
            },
            'test_results': tester.test_results
        }, f, indent=2)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())