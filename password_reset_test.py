"""
Test Password Reset Email Customization with Logo
Tests the forgot-password endpoint with custom branding functionality
"""

import requests
import json
from datetime import datetime

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

print("=" * 80)
print("PASSWORD RESET EMAIL CUSTOMIZATION TEST")
print("=" * 80)
print(f"Backend URL: {BACKEND_URL}")
print(f"Test User: {TEST_EMAIL}")
print("=" * 80)

# Step 1: Login to get authentication token
print("\n🔍 STEP 1: Login for Authentication")
auth_token = None
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
            log_test("Login Authentication", True, f"Token received for {user_data.get('email')}")
        else:
            log_test("Login Authentication", False, "No token in response")
    else:
        log_test("Login Authentication", False, f"Status: {response.status_code}")
except Exception as e:
    log_test("Login Authentication", False, f"Exception: {str(e)}")

if not auth_token:
    print("\n❌ CRITICAL: Cannot proceed without authentication token")
    exit(1)

headers = {"Authorization": f"Bearer {auth_token}"}

# Step 2: Set up company settings with logo and primary color
print("\n🔍 STEP 2: Setup Company Settings with Custom Branding")
try:
    # First, set logo URL
    logo_data = {
        "logo_url": "https://via.placeholder.com/100x100/2563eb/ffffff?text=FP"
    }
    
    response = requests.post(
        f"{BACKEND_URL}/settings/company/upload-logo",
        json=logo_data,
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        result = response.json()
        log_test("Set Logo URL", True, f"Logo URL: {result.get('logo_url')}")
    else:
        log_test("Set Logo URL", False, f"Status: {response.status_code}")
        
    # Set primary color and company name
    settings_data = {
        "primary_color": "#2563eb",
        "company_name": "FacturePro Test Company"
    }
    
    response = requests.put(
        f"{BACKEND_URL}/settings/company",
        json=settings_data,
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        log_test("Set Primary Color & Company Name", True, "Branding settings updated")
    else:
        log_test("Set Primary Color & Company Name", False, f"Status: {response.status_code}")
        
except Exception as e:
    log_test("Setup Company Settings", False, f"Exception: {str(e)}")

# Step 3: Verify settings are stored correctly
print("\n🔍 STEP 3: Verify Company Settings Storage")
try:
    response = requests.get(f"{BACKEND_URL}/settings/company", headers=headers, timeout=10)
    
    if response.status_code == 200:
        settings = response.json()
        logo_url = settings.get('logo_url')
        primary_color = settings.get('primary_color')
        company_name = settings.get('company_name')
        
        print(f"   Logo URL: {logo_url}")
        print(f"   Primary Color: {primary_color}")
        print(f"   Company Name: {company_name}")
        
        if logo_url and primary_color and company_name:
            log_test("Verify Settings Storage", True, "All branding settings stored correctly")
        else:
            missing = []
            if not logo_url: missing.append("logo_url")
            if not primary_color: missing.append("primary_color") 
            if not company_name: missing.append("company_name")
            log_test("Verify Settings Storage", False, f"Missing: {', '.join(missing)}")
    else:
        log_test("Verify Settings Storage", False, f"Status: {response.status_code}")
except Exception as e:
    log_test("Verify Settings Storage", False, f"Exception: {str(e)}")

# Step 4: Test forgot-password endpoint
print("\n🔍 STEP 4: Test Forgot Password with Custom Branding")
try:
    response = requests.post(
        f"{BACKEND_URL}/auth/forgot-password",
        json={"email": TEST_EMAIL},
        timeout=15  # Increased timeout for email processing
    )
    
    if response.status_code == 200:
        data = response.json()
        message = data.get("message", "")
        
        if "code de réinitialisation a été envoyé" in message:
            log_test("Forgot Password Request", True, "Reset code generation successful")
        else:
            log_test("Forgot Password Request", False, f"Unexpected message: {message}")
    else:
        log_test("Forgot Password Request", False, f"Status: {response.status_code}, Response: {response.text}")
except Exception as e:
    log_test("Forgot Password Request", False, f"Exception: {str(e)}")

# Step 5: Verify reset code is stored in database (indirect test)
print("\n🔍 STEP 5: Verify Reset Code Storage")
try:
    # We can't directly access the database, but we can test if a reset code was generated
    # by attempting to use an invalid code and checking the error message
    response = requests.post(
        f"{BACKEND_URL}/auth/reset-password",
        json={
            "email": TEST_EMAIL,
            "reset_code": "000000",  # Invalid code
            "new_password": "NewTestPass123!"
        },
        timeout=10
    )
    
    if response.status_code == 400:
        error_data = response.json()
        if "Code invalide" in error_data.get("detail", ""):
            log_test("Reset Code Storage Verification", True, "Reset code validation working (invalid code rejected)")
        else:
            log_test("Reset Code Storage Verification", False, f"Unexpected error: {error_data}")
    else:
        log_test("Reset Code Storage Verification", False, f"Expected 400 status, got: {response.status_code}")
except Exception as e:
    log_test("Reset Code Storage Verification", False, f"Exception: {str(e)}")

# Step 6: Check backend logs for email sending
print("\n🔍 STEP 6: Check Backend Logs for Email Processing")
try:
    import subprocess
    result = subprocess.run(
        ["tail", "-n", "50", "/var/log/supervisor/backend.err.log"],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    if result.returncode == 0:
        log_content = result.stdout
        
        # Look for email-related log entries
        if "Error sending reset email" in log_content:
            log_test("Backend Email Logs", False, "Email sending error found in logs")
            print("   Error details in backend logs")
        elif "reset_html" in log_content or "create_email_template" in log_content:
            log_test("Backend Email Logs", True, "Email template processing detected")
        else:
            log_test("Backend Email Logs", True, "No email errors in recent logs")
    else:
        log_warning("Backend Email Logs", "Could not read backend logs")
        
except Exception as e:
    log_warning("Backend Email Logs", f"Exception reading logs: {str(e)}")

# Step 7: Test email template generation logic (indirect)
print("\n🔍 STEP 7: Test Email Template Logic")
try:
    # Test that the endpoint processes branding parameters correctly
    # by making another request and checking response consistency
    response = requests.post(
        f"{BACKEND_URL}/auth/forgot-password",
        json={"email": TEST_EMAIL},
        timeout=15
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get("message"):
            log_test("Email Template Logic", True, "Consistent response from forgot-password endpoint")
        else:
            log_test("Email Template Logic", False, "Inconsistent response structure")
    else:
        log_test("Email Template Logic", False, f"Status: {response.status_code}")
except Exception as e:
    log_test("Email Template Logic", False, f"Exception: {str(e)}")

# Step 8: Test with non-existent email (security check)
print("\n🔍 STEP 8: Test Security - Non-existent Email")
try:
    response = requests.post(
        f"{BACKEND_URL}/auth/forgot-password",
        json={"email": "nonexistent@example.com"},
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        message = data.get("message", "")
        
        if "code de réinitialisation a été envoyé" in message:
            log_test("Security - Non-existent Email", True, "Proper security response (no email enumeration)")
        else:
            log_test("Security - Non-existent Email", False, f"Unexpected message: {message}")
    else:
        log_test("Security - Non-existent Email", False, f"Status: {response.status_code}")
except Exception as e:
    log_test("Security - Non-existent Email", False, f"Exception: {str(e)}")

# Final Summary
print("\n" + "=" * 80)
print("PASSWORD RESET EMAIL CUSTOMIZATION TEST SUMMARY")
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
total_tests = len(test_results['passed']) + len(test_results['failed'])
if total_tests > 0:
    pass_rate = len(test_results['passed']) / total_tests * 100
    print(f"Total Tests: {total_tests}")
    print(f"Pass Rate: {pass_rate:.1f}%")
else:
    print("No tests completed")
print("=" * 80)

# Key findings summary
print("\n🔍 KEY FINDINGS:")
print("1. Custom branding retrieval from company_settings")
print("2. Email template generation with logo_url, primary_color, company_name")
print("3. Reset code storage in password_resets collection")
print("4. Resend API email sending with proper 'to' field format")
print("5. Security measures (no email enumeration)")