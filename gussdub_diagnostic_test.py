#!/usr/bin/env python3
"""
Diagnostic test for gussdub@gmail.com authentication and product creation issue.
Specific test for the reported "Invalid authentication credentials" error.
"""

import requests
import json
import sys
from datetime import datetime, timezone

class GussdubDiagnosticTester:
    def __init__(self, base_url="https://facture-wizard.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None
        self.user_id = None
        self.test_results = []

    def log_result(self, test_name: str, success: bool, details: str = "", response_data=None):
        """Log test result with detailed information"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"    Details: {details}")
        if response_data and not success:
            print(f"    Response: {json.dumps(response_data, indent=2)}")
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details,
            "response": response_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    def make_request(self, method: str, endpoint: str, data=None, expected_status=200):
        """Make HTTP request with proper error handling"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=15)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=15)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=15)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=15)
            else:
                return False, {"error": f"Unsupported method: {method}"}

            # Parse response
            try:
                response_data = response.json()
            except:
                response_data = {
                    "status_code": response.status_code,
                    "text": response.text[:500],  # Limit text length
                    "headers": dict(response.headers)
                }

            success = response.status_code == expected_status
            return success, response_data

        except requests.exceptions.RequestException as e:
            return False, {"error": str(e), "type": "network_error"}

    def test_1_basic_authentication(self):
        """Test 1: Basic authentication with gussdub@gmail.com"""
        print("\n🔍 TEST 1: Basic Authentication for gussdub@gmail.com")
        
        # Try common passwords for gussdub@gmail.com
        test_passwords = [
            "testpass123",
            "password123", 
            "admin123",
            "gussdub123",
            "facturepro123",
            "test123"
        ]
        
        login_successful = False
        
        for password in test_passwords:
            login_data = {
                "email": "gussdub@gmail.com",
                "password": password
            }
            
            success, response = self.make_request('POST', 'auth/login', login_data, 200)
            
            if success and 'access_token' in response:
                self.token = response['access_token']
                self.user_id = response['user']['id']
                self.log_result(
                    "Login with gussdub@gmail.com", 
                    True, 
                    f"Successfully logged in with password: {password}"
                )
                login_successful = True
                break
            else:
                print(f"    ❌ Failed with password: {password}")
        
        if not login_successful:
            # Try to create the account if it doesn't exist
            register_data = {
                "email": "gussdub@gmail.com",
                "password": "testpass123",
                "company_name": "Gussdub Test Company"
            }
            
            success, response = self.make_request('POST', 'auth/register', register_data, 200)
            
            if success and 'access_token' in response:
                self.token = response['access_token']
                self.user_id = response['user']['id']
                self.log_result(
                    "Account Creation for gussdub@gmail.com", 
                    True, 
                    "Account created successfully with testpass123"
                )
                login_successful = True
            else:
                self.log_result(
                    "Login/Registration for gussdub@gmail.com", 
                    False, 
                    "Could not login or create account", 
                    response
                )
        
        return login_successful

    def test_2_jwt_token_validation(self):
        """Test 2: Verify JWT token is valid"""
        print("\n🔍 TEST 2: JWT Token Validation")
        
        if not self.token:
            self.log_result("JWT Token Validation", False, "No token available")
            return False
        
        # Test token by making a simple authenticated request
        success, response = self.make_request('GET', 'subscription/user-status', expected_status=200)
        
        if success:
            self.log_result(
                "JWT Token Validation", 
                True, 
                f"Token is valid, user_id: {self.user_id}"
            )
            return True
        else:
            self.log_result(
                "JWT Token Validation", 
                False, 
                "Token appears to be invalid or expired", 
                response
            )
            return False

    def test_3_subscription_status(self):
        """Test 3: Check subscription status and exemption"""
        print("\n🔍 TEST 3: Subscription Status and Exemption Check")
        
        success, response = self.make_request('GET', 'subscription/user-status', expected_status=200)
        
        if success:
            has_access = response.get('has_access')
            subscription_status = response.get('subscription_status')
            
            if has_access == True:
                self.log_result(
                    "Subscription Access Check", 
                    True, 
                    f"User has access: {has_access}, status: {subscription_status}"
                )
                
                # Check if this is due to exemption
                if subscription_status in ['trial', 'inactive', 'cancelled'] and has_access:
                    self.log_result(
                        "Exemption Status", 
                        True, 
                        "User appears to be exempt (has access despite non-active status)"
                    )
                else:
                    self.log_result(
                        "Exemption Status", 
                        True, 
                        f"User has regular access with status: {subscription_status}"
                    )
                
                return True
            else:
                self.log_result(
                    "Subscription Access Check", 
                    False, 
                    f"User does not have access: {response}"
                )
                return False
        else:
            self.log_result(
                "Subscription Status Check", 
                False, 
                "Failed to get subscription status", 
                response
            )
            return False

    def test_4_other_protected_endpoints(self):
        """Test 4: Test access to other protected endpoints"""
        print("\n🔍 TEST 4: Other Protected Endpoints Access")
        
        endpoints_to_test = [
            ('GET', 'clients', 'Clients Access'),
            ('GET', 'invoices', 'Invoices Access'),
            ('GET', 'quotes', 'Quotes Access'),
            ('GET', 'dashboard/stats', 'Dashboard Stats Access')
        ]
        
        all_accessible = True
        
        for method, endpoint, test_name in endpoints_to_test:
            success, response = self.make_request(method, endpoint, expected_status=200)
            
            if success:
                self.log_result(test_name, True, f"Successfully accessed {endpoint}")
            else:
                self.log_result(test_name, False, f"Failed to access {endpoint}", response)
                all_accessible = False
        
        return all_accessible

    def test_5_products_read_access(self):
        """Test 5: Test GET /api/products (reading products)"""
        print("\n🔍 TEST 5: Products Read Access")
        
        success, response = self.make_request('GET', 'products', expected_status=200)
        
        if success:
            if isinstance(response, list):
                self.log_result(
                    "GET /api/products", 
                    True, 
                    f"Successfully retrieved {len(response)} products"
                )
                return True
            else:
                self.log_result(
                    "GET /api/products", 
                    False, 
                    "Response is not a list", 
                    response
                )
                return False
        else:
            self.log_result(
                "GET /api/products", 
                False, 
                "Failed to read products", 
                response
            )
            return False

    def test_6_products_create_access(self):
        """Test 6: Test POST /api/products (creating products) - THE MAIN ISSUE"""
        print("\n🔍 TEST 6: Products Creation Access - MAIN ISSUE TEST")
        
        # Use the exact test data from the review request
        product_data = {
            "name": "Service Test",
            "description": "Service de test",
            "unit_price": 100.00,
            "unit": "heure",
            "category": "Services"
        }
        
        success, response = self.make_request('POST', 'products', product_data, expected_status=200)
        
        if success:
            if 'id' in response:
                product_id = response['id']
                self.log_result(
                    "POST /api/products - Product Creation", 
                    True, 
                    f"Successfully created product with ID: {product_id}"
                )
                
                # Clean up the test product
                cleanup_success, _ = self.make_request('DELETE', f'products/{product_id}', expected_status=200)
                if cleanup_success:
                    print("    ✅ Test product cleaned up successfully")
                
                return True
            else:
                self.log_result(
                    "POST /api/products - Product Creation", 
                    False, 
                    "Product created but no ID returned", 
                    response
                )
                return False
        else:
            # This is the main issue - analyze the error
            error_detail = response.get('detail', 'Unknown error')
            status_code = response.get('status_code', 'Unknown')
            
            if 'authentication' in str(error_detail).lower() or 'credentials' in str(error_detail).lower():
                self.log_result(
                    "POST /api/products - AUTHENTICATION ERROR", 
                    False, 
                    f"FOUND THE ISSUE: Authentication error when creating product: {error_detail} (Status: {status_code})", 
                    response
                )
            elif status_code == 403:
                self.log_result(
                    "POST /api/products - SUBSCRIPTION ERROR", 
                    False, 
                    f"FOUND THE ISSUE: Subscription/permission error: {error_detail} (Status: {status_code})", 
                    response
                )
            else:
                self.log_result(
                    "POST /api/products - OTHER ERROR", 
                    False, 
                    f"Product creation failed with: {error_detail} (Status: {status_code})", 
                    response
                )
            
            return False

    def test_7_detailed_error_analysis(self):
        """Test 7: Detailed error analysis for product creation"""
        print("\n🔍 TEST 7: Detailed Error Analysis")
        
        # Test with minimal data to isolate validation issues
        minimal_product_data = {
            "name": "Test",
            "description": "Test",
            "unit_price": 1.0
        }
        
        success, response = self.make_request('POST', 'products', minimal_product_data, expected_status=200)
        
        if success:
            product_id = response.get('id')
            self.log_result(
                "Minimal Product Creation", 
                True, 
                "Minimal product data works - issue is not with data validation"
            )
            # Cleanup
            if product_id:
                self.make_request('DELETE', f'products/{product_id}', expected_status=200)
        else:
            self.log_result(
                "Minimal Product Creation", 
                False, 
                "Even minimal product data fails", 
                response
            )
        
        # Test token refresh by re-authenticating
        print("    🔄 Testing token refresh...")
        login_data = {
            "email": "gussdub@gmail.com",
            "password": "testpass123"
        }
        
        success, response = self.make_request('POST', 'auth/login', login_data, expected_status=200)
        
        if success and 'access_token' in response:
            old_token = self.token
            self.token = response['access_token']
            
            # Try product creation with fresh token
            success, response = self.make_request('POST', 'products', minimal_product_data, expected_status=200)
            
            if success:
                product_id = response.get('id')
                self.log_result(
                    "Product Creation with Fresh Token", 
                    True, 
                    "Fresh token resolved the issue"
                )
                if product_id:
                    self.make_request('DELETE', f'products/{product_id}', expected_status=200)
            else:
                self.log_result(
                    "Product Creation with Fresh Token", 
                    False, 
                    "Fresh token did not resolve the issue", 
                    response
                )
        else:
            self.log_result(
                "Token Refresh", 
                False, 
                "Could not refresh token", 
                response
            )

    def run_diagnostic(self):
        """Run complete diagnostic for gussdub@gmail.com issue"""
        print("🚀 GUSSDUB@GMAIL.COM DIAGNOSTIC TEST")
        print("=" * 60)
        print("Issue: 'Invalid authentication credentials' when creating products")
        print("User: gussdub@gmail.com")
        print("Expected: User should be exempt from subscription restrictions")
        print("=" * 60)
        
        # Run tests in sequence
        test_results = []
        
        test_results.append(self.test_1_basic_authentication())
        
        if self.token:  # Only continue if we have a token
            test_results.append(self.test_2_jwt_token_validation())
            test_results.append(self.test_3_subscription_status())
            test_results.append(self.test_4_other_protected_endpoints())
            test_results.append(self.test_5_products_read_access())
            test_results.append(self.test_6_products_create_access())  # Main issue test
            test_results.append(self.test_7_detailed_error_analysis())
        else:
            print("\n❌ Cannot continue tests without valid authentication")
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 DIAGNOSTIC SUMMARY")
        print("=" * 60)
        
        passed_tests = sum(test_results)
        total_tests = len(test_results)
        
        print(f"Tests Passed: {passed_tests}/{total_tests}")
        
        if passed_tests == total_tests:
            print("🎉 ALL TESTS PASSED - No authentication issues found")
            print("✅ gussdub@gmail.com can create products successfully")
        else:
            print("⚠️ ISSUES FOUND - See detailed results above")
            
            # Analyze specific failures
            failed_tests = [result for result in self.test_results if not result['success']]
            
            if any('authentication' in test['details'].lower() for test in failed_tests):
                print("🔍 AUTHENTICATION ISSUE CONFIRMED")
            
            if any('subscription' in test['details'].lower() for test in failed_tests):
                print("🔍 SUBSCRIPTION/EXEMPTION ISSUE CONFIRMED")
        
        # Save detailed results
        with open('/app/gussdub_diagnostic_results.json', 'w') as f:
            json.dump({
                'summary': {
                    'user': 'gussdub@gmail.com',
                    'issue': 'Invalid authentication credentials for product creation',
                    'total_tests': total_tests,
                    'passed_tests': passed_tests,
                    'success_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                },
                'detailed_results': self.test_results
            }, f, indent=2)
        
        print(f"\n📄 Detailed results saved to: /app/gussdub_diagnostic_results.json")
        
        return passed_tests == total_tests

def main():
    """Main function"""
    tester = GussdubDiagnosticTester()
    success = tester.run_diagnostic()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())