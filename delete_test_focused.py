#!/usr/bin/env python3
"""
Focused test for DELETE functionality in FacturePro backend
Tests specifically requested in the review: DELETE /api/invoices/{id} and DELETE /api/quotes/{id}
"""

import requests
import json
from datetime import datetime, timedelta

class DeleteFunctionalityTester:
    def __init__(self):
        self.base_url = "https://facture-wizard.preview.emergentagent.com"
        self.api_url = f"{self.base_url}/api"
        self.token = None
        self.test_results = []

    def log_result(self, test_name, success, details=""):
        result = f"{'✅' if success else '❌'} {test_name}: {'PASSED' if success else 'FAILED'}"
        if details:
            result += f" - {details}"
        print(result)
        self.test_results.append({"test": test_name, "success": success, "details": details})

    def make_request(self, method, endpoint, data=None):
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
                return None, {"error": f"Unsupported method: {method}"}

            try:
                response_data = response.json()
            except:
                response_data = {"status_code": response.status_code, "text": response.text}

            return response, response_data

        except requests.exceptions.RequestException as e:
            return None, {"error": str(e)}

    def setup_auth(self):
        """Create user and get auth token"""
        test_email = f"delete_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}@example.com"
        user_data = {
            "email": test_email,
            "password": "DeleteTest123",
            "company_name": "Delete Test Company"
        }
        
        response, data = self.make_request('POST', 'auth/register', user_data)
        if response and response.status_code == 200 and 'access_token' in data:
            self.token = data['access_token']
            self.log_result("User Registration & Auth", True, f"Authenticated as {test_email}")
            return True
        else:
            self.log_result("User Registration & Auth", False, f"Failed: {data}")
            return False

    def create_test_client(self):
        """Create a test client for invoices and quotes"""
        client_data = {
            "name": "Client Suppression Test",
            "email": "client.suppression@example.com",
            "phone": "+33123456789",
            "address": "123 Rue de Test",
            "city": "Paris",
            "postal_code": "75001",
            "country": "France"
        }
        
        response, data = self.make_request('POST', 'clients', client_data)
        if response and response.status_code == 200 and 'id' in data:
            self.client_id = data['id']
            self.log_result("Create Test Client", True, f"Client ID: {self.client_id}")
            return True
        else:
            self.log_result("Create Test Client", False, f"Failed: {data}")
            return False

    def test_invoice_delete(self):
        """Test DELETE /api/invoices/{invoice_id}"""
        print("\n--- Testing Invoice Deletion ---")
        
        # 1. Create test invoice
        invoice_data = {
            "client_id": self.client_id,
            "due_date": (datetime.now() + timedelta(days=30)).isoformat(),
            "items": [
                {
                    "description": "Service de test à supprimer",
                    "quantity": 1.0,
                    "unit_price": 100.0
                }
            ],
            "gst_rate": 5.0,
            "pst_rate": 9.975,
            "apply_gst": True,
            "apply_pst": True,
            "notes": "Facture de test pour suppression"
        }
        
        response, data = self.make_request('POST', 'invoices', invoice_data)
        if not (response and response.status_code == 200 and 'id' in data):
            self.log_result("Create Test Invoice", False, f"Failed to create: {data}")
            return False
        
        invoice_id = data['id']
        invoice_number = data['invoice_number']
        self.log_result("Create Test Invoice", True, f"Created {invoice_number} (ID: {invoice_id})")

        # 2. Test successful deletion
        response, data = self.make_request('DELETE', f'invoices/{invoice_id}')
        if response and response.status_code == 200:
            self.log_result("DELETE Invoice - Success", True, f"Invoice {invoice_number} deleted successfully")
        else:
            self.log_result("DELETE Invoice - Success", False, f"Delete failed: {data}")
            return False

        # 3. Verify invoice is gone (should return 404)
        response, data = self.make_request('GET', f'invoices/{invoice_id}')
        if response and response.status_code == 404:
            self.log_result("Verify Invoice Deletion", True, "Invoice correctly not found after deletion")
        else:
            self.log_result("Verify Invoice Deletion", False, f"Invoice still accessible: {data}")

        # 4. Test delete non-existent invoice (should return 404)
        fake_id = "non-existent-invoice-id"
        response, data = self.make_request('DELETE', f'invoices/{fake_id}')
        if response and response.status_code == 404:
            self.log_result("DELETE Non-existent Invoice", True, "Correctly returned 404")
        else:
            self.log_result("DELETE Non-existent Invoice", False, f"Expected 404, got: {response.status_code if response else 'No response'}")

        # 5. Test unauthorized delete (no token)
        # First create another invoice
        response, data = self.make_request('POST', 'invoices', invoice_data)
        if response and response.status_code == 200 and 'id' in data:
            unauthorized_invoice_id = data['id']
            
            # Remove token temporarily
            old_token = self.token
            self.token = None
            
            response, data = self.make_request('DELETE', f'invoices/{unauthorized_invoice_id}')
            if response and response.status_code == 403:
                self.log_result("DELETE Invoice - Unauthorized", True, "Correctly rejected unauthorized request")
            else:
                self.log_result("DELETE Invoice - Unauthorized", False, f"Expected 403, got: {response.status_code if response else 'No response'}")
            
            # Restore token and cleanup
            self.token = old_token
            self.make_request('DELETE', f'invoices/{unauthorized_invoice_id}')

        return True

    def test_quote_delete(self):
        """Test DELETE /api/quotes/{quote_id}"""
        print("\n--- Testing Quote Deletion ---")
        
        # 1. Create test quote
        quote_data = {
            "client_id": self.client_id,
            "valid_until": (datetime.now() + timedelta(days=15)).isoformat(),
            "items": [
                {
                    "description": "Devis de test à supprimer",
                    "quantity": 1.0,
                    "unit_price": 150.0
                }
            ],
            "gst_rate": 5.0,
            "pst_rate": 9.975,
            "apply_gst": True,
            "apply_pst": True,
            "notes": "Devis de test pour suppression"
        }
        
        response, data = self.make_request('POST', 'quotes', quote_data)
        if not (response and response.status_code == 200 and 'id' in data):
            self.log_result("Create Test Quote", False, f"Failed to create: {data}")
            return False
        
        quote_id = data['id']
        quote_number = data['quote_number']
        self.log_result("Create Test Quote", True, f"Created {quote_number} (ID: {quote_id})")

        # 2. Test successful deletion
        response, data = self.make_request('DELETE', f'quotes/{quote_id}')
        if response and response.status_code == 200:
            self.log_result("DELETE Quote - Success", True, f"Quote {quote_number} deleted successfully")
        else:
            self.log_result("DELETE Quote - Success", False, f"Delete failed: {data}")
            return False

        # 3. Verify quote is gone by checking quotes list
        response, data = self.make_request('GET', 'quotes')
        if response and response.status_code == 200:
            quote_exists = any(quote.get('id') == quote_id for quote in data)
            if not quote_exists:
                self.log_result("Verify Quote Deletion", True, "Quote correctly not found in list after deletion")
            else:
                self.log_result("Verify Quote Deletion", False, "Quote still exists in list after deletion")

        # 4. Test delete non-existent quote (should return 404)
        fake_id = "non-existent-quote-id"
        response, data = self.make_request('DELETE', f'quotes/{fake_id}')
        if response and response.status_code == 404:
            self.log_result("DELETE Non-existent Quote", True, "Correctly returned 404")
        else:
            self.log_result("DELETE Non-existent Quote", False, f"Expected 404, got: {response.status_code if response else 'No response'}")

        # 5. Test unauthorized delete (no token)
        # First create another quote
        response, data = self.make_request('POST', 'quotes', quote_data)
        if response and response.status_code == 200 and 'id' in data:
            unauthorized_quote_id = data['id']
            
            # Remove token temporarily
            old_token = self.token
            self.token = None
            
            response, data = self.make_request('DELETE', f'quotes/{unauthorized_quote_id}')
            if response and response.status_code == 403:
                self.log_result("DELETE Quote - Unauthorized", True, "Correctly rejected unauthorized request")
            else:
                self.log_result("DELETE Quote - Unauthorized", False, f"Expected 403, got: {response.status_code if response else 'No response'}")
            
            # Restore token and cleanup
            self.token = old_token
            self.make_request('DELETE', f'quotes/{unauthorized_quote_id}')

        return True

    def cleanup(self):
        """Clean up test data"""
        if hasattr(self, 'client_id'):
            response, _ = self.make_request('DELETE', f'clients/{self.client_id}')
            if response and response.status_code == 200:
                print(f"✅ Cleaned up test client: {self.client_id}")

    def run_tests(self):
        """Run all delete functionality tests"""
        print("🚀 FacturePro Delete Functionality Test")
        print("Testing DELETE /api/invoices/{id} and DELETE /api/quotes/{id}")
        print("=" * 70)

        # Setup
        if not self.setup_auth():
            return False
        
        if not self.create_test_client():
            return False

        # Run tests
        invoice_success = self.test_invoice_delete()
        quote_success = self.test_quote_delete()

        # Cleanup
        self.cleanup()

        # Summary
        passed = sum(1 for result in self.test_results if result['success'])
        total = len(self.test_results)
        
        print("\n" + "=" * 70)
        print(f"📊 Test Summary: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All delete functionality tests PASSED!")
            print("✅ DELETE /api/invoices/{id} is working correctly")
            print("✅ DELETE /api/quotes/{id} is working correctly")
            print("✅ Authentication and authorization are properly enforced")
            print("✅ Error handling for non-existent resources is correct")
            return True
        else:
            print(f"⚠️ {total - passed} tests failed")
            return False

if __name__ == "__main__":
    tester = DeleteFunctionalityTester()
    success = tester.run_tests()
    
    # Save results
    with open('/app/delete_test_results.json', 'w') as f:
        json.dump({
            'summary': {
                'total_tests': len(tester.test_results),
                'passed_tests': sum(1 for r in tester.test_results if r['success']),
                'success': success
            },
            'test_results': tester.test_results
        }, f, indent=2)
    
    exit(0 if success else 1)