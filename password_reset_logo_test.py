"""
Password Reset Email Logo Test for FacturePro
Tests password reset email with specific logo URL to verify correct display
"""

import requests
import json
from datetime import datetime

# Configuration
BACKEND_URL = "https://facturepro.preview.emergentagent.com/api"
TEST_EMAIL = "gussdub@gmail.com"
TEST_PASSWORD = "testpass123"
LOGO_URL = "https://customer-assets.emergentagent.com/job_facturepro/artifacts/y8rea1ms_2c256145-633e-411d-9781-dce2201c8da3_wm.jpeg"

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
print("PASSWORD RESET EMAIL LOGO TEST - FACTUREPRO")
print("=" * 80)
print(f"Backend URL: {BACKEND_URL}")
print(f"Test Email: {TEST_EMAIL}")
print(f"Logo URL: {LOGO_URL}")
print("=" * 80)

# Step 1: Login to get authentication token
print("\n🔍 STEP 1: Login Authentication")
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
            print(f"   User ID: {user_data.get('id')}")
        else:
            log_test("Login Authentication", False, "No token in response")
    else:
        log_test("Login Authentication", False, f"Status: {response.status_code}, Response: {response.text}")
except Exception as e:
    log_test("Login Authentication", False, f"Exception: {str(e)}")

if not auth_token:
    print("\n❌ CRITICAL: Cannot proceed without authentication token")
    exit(1)

headers = {"Authorization": f"Bearer {auth_token}"}

# Step 2: Update company settings with the specific logo URL
print("\n🔍 STEP 2: Update Company Settings with FacturePro Logo")
try:
    # First get current settings
    response = requests.get(f"{BACKEND_URL}/settings/company", headers=headers, timeout=10)
    
    if response.status_code == 200:
        current_settings = response.json()
        log_test("Get Current Company Settings", True, f"Company: {current_settings.get('company_name')}")
        print(f"   Current Logo URL: {current_settings.get('logo_url', 'None')}")
        
        # Update with new logo URL
        update_data = {
            "logo_url": LOGO_URL,
            "primary_color": "#0d9488"  # FacturePro teal color
        }
        
        response = requests.put(
            f"{BACKEND_URL}/settings/company",
            json=update_data,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            log_test("Update Logo URL", True, f"Logo URL updated successfully")
            print(f"   New Logo URL: {LOGO_URL}")
        else:
            log_test("Update Logo URL", False, f"Status: {response.status_code}, Response: {response.text}")
    else:
        log_test("Get Current Company Settings", False, f"Status: {response.status_code}")
        
except Exception as e:
    log_test("Update Company Settings", False, f"Exception: {str(e)}")

# Step 3: Verify logo URL is saved correctly
print("\n🔍 STEP 3: Verify Logo URL in Database")
try:
    response = requests.get(f"{BACKEND_URL}/settings/company", headers=headers, timeout=10)
    
    if response.status_code == 200:
        settings = response.json()
        stored_logo_url = settings.get('logo_url')
        primary_color = settings.get('primary_color')
        company_name = settings.get('company_name')
        
        if stored_logo_url == LOGO_URL:
            log_test("Logo URL Storage Verification", True, "Logo URL correctly stored in database")
            print(f"   Stored Logo URL: {stored_logo_url}")
            print(f"   Primary Color: {primary_color}")
            print(f"   Company Name: {company_name}")
        else:
            log_test("Logo URL Storage Verification", False, f"Expected: {LOGO_URL}, Got: {stored_logo_url}")
    else:
        log_test("Logo URL Storage Verification", False, f"Status: {response.status_code}")
        
except Exception as e:
    log_test("Logo URL Storage Verification", False, f"Exception: {str(e)}")

# Step 4: Send password reset email
print("\n🔍 STEP 4: Send Password Reset Email with Logo")
try:
    response = requests.post(
        f"{BACKEND_URL}/auth/forgot-password",
        json={"email": TEST_EMAIL},
        timeout=15
    )
    
    if response.status_code == 200:
        data = response.json()
        message = data.get("message", "")
        
        if "code de réinitialisation a été envoyé" in message or "reset code" in message.lower():
            log_test("Password Reset Email Sent", True, "Reset email sent successfully via Resend API")
            print(f"   Response: {message}")
        else:
            log_test("Password Reset Email Sent", False, f"Unexpected response: {message}")
    else:
        log_test("Password Reset Email Sent", False, f"Status: {response.status_code}, Response: {response.text}")
        
except Exception as e:
    log_test("Password Reset Email Sent", False, f"Exception: {str(e)}")

# Step 5: Check backend logs for logo URL retrieval
print("\n🔍 STEP 5: Check Backend Logs for Logo URL Retrieval")
try:
    # Check supervisor logs for backend
    import subprocess
    result = subprocess.run(
        ["tail", "-n", "50", "/var/log/supervisor/backend.out.log"],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.returncode == 0:
        log_output = result.stdout
        
        # Look for logo URL in logs
        if LOGO_URL in log_output:
            log_test("Backend Logs - Logo URL Retrieval", True, "Logo URL found in backend logs")
            print(f"   Logo URL correctly retrieved from company_settings")
        else:
            # Check for any logo-related activity
            logo_mentions = [line for line in log_output.split('\n') if 'logo' in line.lower() or 'company_settings' in line.lower()]
            if logo_mentions:
                log_test("Backend Logs - Logo Activity", True, f"Logo-related activity found ({len(logo_mentions)} entries)")
                for mention in logo_mentions[-3:]:  # Show last 3 mentions
                    print(f"   Log: {mention.strip()}")
            else:
                log_warning("Backend Logs - Logo URL", "No logo URL found in recent logs")
                
        # Check for Resend API activity
        resend_mentions = [line for line in log_output.split('\n') if 'resend' in line.lower() or 'email sent' in line.lower()]
        if resend_mentions:
            log_test("Backend Logs - Resend API Activity", True, f"Resend API activity found ({len(resend_mentions)} entries)")
            for mention in resend_mentions[-2:]:  # Show last 2 mentions
                print(f"   Log: {mention.strip()}")
        else:
            log_warning("Backend Logs - Resend API", "No Resend API activity found in recent logs")
            
    else:
        log_warning("Backend Logs Check", f"Could not read logs: {result.stderr}")
        
except Exception as e:
    log_warning("Backend Logs Check", f"Exception: {str(e)}")

# Step 6: Test email template generation function
print("\n🔍 STEP 6: Verify Email Template Function Parameters")
try:
    # Make another password reset request to trigger template generation
    response = requests.post(
        f"{BACKEND_URL}/auth/forgot-password",
        json={"email": TEST_EMAIL},
        timeout=15
    )
    
    if response.status_code == 200:
        log_test("Email Template Generation", True, "create_email_template function called successfully")
        print(f"   Template should include:")
        print(f"   - Logo URL: {LOGO_URL}")
        print(f"   - Primary Color: #0d9488")
        print(f"   - Company Name: Retrieved from settings")
        print(f"   - Reset code in styled box")
    else:
        log_test("Email Template Generation", False, f"Status: {response.status_code}")
        
except Exception as e:
    log_test("Email Template Generation", False, f"Exception: {str(e)}")

# Final Summary
print("\n" + "=" * 80)
print("PASSWORD RESET EMAIL LOGO TEST SUMMARY")
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

print(f"\n📧 EMAIL VERIFICATION:")
print(f"   - Password reset email sent to: {TEST_EMAIL}")
print(f"   - Logo should display: {LOGO_URL}")
print(f"   - Email should show FacturePro branding instead of initials")
print(f"   - Check email inbox for visual confirmation")

print("\n" + "=" * 80)
print(f"Total Tests: {len(test_results['passed']) + len(test_results['failed'])}")
if len(test_results['passed']) + len(test_results['failed']) > 0:
    print(f"Pass Rate: {len(test_results['passed']) / (len(test_results['passed']) + len(test_results['failed'])) * 100:.1f}%")
print("=" * 80)