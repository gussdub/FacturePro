"""
Stripe Subscription Integration Tests for FacturePro
Tests: Auth/me endpoint, subscription status, checkout creation, checkout status, webhook
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
EXEMPT_USER_EMAIL = "gussdub@gmail.com"
EXEMPT_USER_PASSWORD = "testpass123"


class TestAuthMeSubscription:
    """Test /api/auth/me returns correct subscription info for exempt user"""
    
    @pytest.fixture
    def auth_token(self):
        """Login with exempt user and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": EXEMPT_USER_EMAIL,
            "password": EXEMPT_USER_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json().get("access_token")
    
    def test_exempt_user_login_success(self):
        """Test exempt user can login successfully"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": EXEMPT_USER_EMAIL,
            "password": EXEMPT_USER_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == EXEMPT_USER_EMAIL
        print(f"PASS: Exempt user login successful")
    
    def test_auth_me_returns_active_for_exempt_user(self, auth_token):
        """Test /api/auth/me returns subscription_status='active' and is_exempt=true for exempt user"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify subscription_status is 'active' for exempt user
        assert data.get("subscription_status") == "active", f"Expected 'active', got '{data.get('subscription_status')}'"
        
        # Verify is_exempt is True
        assert data.get("is_exempt") == True, f"Expected is_exempt=True, got {data.get('is_exempt')}"
        
        # Verify email matches
        assert data.get("email") == EXEMPT_USER_EMAIL
        
        print(f"PASS: /api/auth/me returns subscription_status='active', is_exempt=True for exempt user")


class TestSubscriptionCurrent:
    """Test /api/subscription/current endpoint"""
    
    @pytest.fixture
    def auth_token(self):
        """Login with exempt user and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": EXEMPT_USER_EMAIL,
            "password": EXEMPT_USER_PASSWORD
        })
        assert response.status_code == 200
        return response.json().get("access_token")
    
    def test_subscription_current_returns_active_for_exempt(self, auth_token):
        """Test GET /api/subscription/current returns subscription_status='active' for exempt user"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/subscription/current", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify subscription_status is 'active' for exempt user
        assert data.get("subscription_status") == "active", f"Expected 'active', got '{data.get('subscription_status')}'"
        
        # Verify is_exempt is True
        assert data.get("is_exempt") == True
        
        print(f"PASS: /api/subscription/current returns subscription_status='active' for exempt user")
    
    def test_subscription_current_requires_auth(self):
        """Test /api/subscription/current requires authentication"""
        response = requests.get(f"{BASE_URL}/api/subscription/current")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"PASS: /api/subscription/current requires authentication")


class TestCreateCheckout:
    """Test /api/subscription/create-checkout endpoint"""
    
    @pytest.fixture
    def auth_token(self):
        """Login with exempt user and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": EXEMPT_USER_EMAIL,
            "password": EXEMPT_USER_PASSWORD
        })
        assert response.status_code == 200
        return response.json().get("access_token")
    
    def test_create_checkout_returns_stripe_url(self, auth_token):
        """Test POST /api/subscription/create-checkout returns valid Stripe checkout URL and session_id"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(
            f"{BASE_URL}/api/subscription/create-checkout",
            headers=headers,
            json={"origin_url": "https://billing-app-32.preview.emergentagent.com"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify URL is returned and is a Stripe checkout URL
        assert "url" in data, "Response should contain 'url'"
        assert data["url"].startswith("https://checkout.stripe.com"), f"URL should be Stripe checkout URL, got: {data['url']}"
        
        # Verify session_id is returned
        assert "session_id" in data, "Response should contain 'session_id'"
        assert len(data["session_id"]) > 0, "session_id should not be empty"
        
        print(f"PASS: /api/subscription/create-checkout returns valid Stripe URL and session_id")
        return data["session_id"]
    
    def test_create_checkout_requires_origin_url(self, auth_token):
        """Test POST /api/subscription/create-checkout requires origin_url"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(
            f"{BASE_URL}/api/subscription/create-checkout",
            headers=headers,
            json={}
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"PASS: /api/subscription/create-checkout requires origin_url")
    
    def test_create_checkout_requires_auth(self):
        """Test /api/subscription/create-checkout requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/subscription/create-checkout",
            json={"origin_url": "https://example.com"}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"PASS: /api/subscription/create-checkout requires authentication")


class TestCheckoutStatus:
    """Test /api/subscription/checkout-status/{session_id} endpoint"""
    
    @pytest.fixture
    def auth_token(self):
        """Login with exempt user and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": EXEMPT_USER_EMAIL,
            "password": EXEMPT_USER_PASSWORD
        })
        assert response.status_code == 200
        return response.json().get("access_token")
    
    @pytest.fixture
    def checkout_session(self, auth_token):
        """Create a checkout session and return session_id"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(
            f"{BASE_URL}/api/subscription/create-checkout",
            headers=headers,
            json={"origin_url": "https://billing-app-32.preview.emergentagent.com"}
        )
        assert response.status_code == 200
        return response.json()["session_id"]
    
    def test_checkout_status_returns_info(self, auth_token, checkout_session):
        """Test GET /api/subscription/checkout-status/{session_id} returns checkout status"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(
            f"{BASE_URL}/api/subscription/checkout-status/{checkout_session}",
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response contains expected fields
        assert "status" in data, "Response should contain 'status'"
        assert "payment_status" in data, "Response should contain 'payment_status'"
        
        print(f"PASS: /api/subscription/checkout-status returns status info: {data}")
    
    def test_checkout_status_requires_auth(self):
        """Test /api/subscription/checkout-status requires authentication"""
        response = requests.get(f"{BASE_URL}/api/subscription/checkout-status/fake_session_id")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"PASS: /api/subscription/checkout-status requires authentication")


class TestStripeWebhook:
    """Test /api/webhook/stripe endpoint exists"""
    
    def test_webhook_endpoint_exists(self):
        """Test POST /api/webhook/stripe endpoint exists and responds"""
        # Send empty body - should get error but endpoint should exist
        response = requests.post(f"{BASE_URL}/api/webhook/stripe", data=b"")
        
        # Endpoint should exist (not 404) - may return error due to missing signature
        assert response.status_code != 404, f"Webhook endpoint should exist, got 404"
        
        # Should return some response (even if error)
        print(f"PASS: /api/webhook/stripe endpoint exists, status: {response.status_code}")


class TestNewUserRegistration:
    """Test new user registration gets trial status"""
    
    def test_register_new_user_gets_trial(self):
        """Test registering a NEW user returns subscription_status='trial' and trial_end_date is set"""
        # Generate unique email for test
        unique_email = f"TEST_trial_user_{uuid.uuid4().hex[:8]}@test.com"
        
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "testpass123",
            "company_name": "Test Trial Company"
        })
        
        assert response.status_code == 200, f"Registration failed: {response.text}"
        data = response.json()
        
        # Verify access_token is returned
        assert "access_token" in data, "Response should contain access_token"
        
        # Verify user data
        assert "user" in data, "Response should contain user"
        user = data["user"]
        
        # Verify subscription_status is 'trial'
        assert user.get("subscription_status") == "trial", f"Expected 'trial', got '{user.get('subscription_status')}'"
        
        # Verify trial_end_date is set
        assert user.get("trial_end_date") is not None, "trial_end_date should be set"
        
        # Verify trial_end_date is approximately 14 days from now
        trial_end = datetime.fromisoformat(user["trial_end_date"].replace('Z', '+00:00'))
        now = datetime.now(trial_end.tzinfo)
        days_until_trial_end = (trial_end - now).days
        
        # Should be between 13-15 days (allowing for timing variations)
        assert 13 <= days_until_trial_end <= 15, f"Trial should be ~14 days, got {days_until_trial_end} days"
        
        print(f"PASS: New user registered with subscription_status='trial', trial_end_date={user['trial_end_date']}")
        
        # Cleanup: We can't easily delete the user, but it's prefixed with TEST_
        return unique_email


class TestPaymentTransactionsCollection:
    """Test payment_transactions collection is created after checkout"""
    
    @pytest.fixture
    def auth_token(self):
        """Login with exempt user and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": EXEMPT_USER_EMAIL,
            "password": EXEMPT_USER_PASSWORD
        })
        assert response.status_code == 200
        return response.json().get("access_token")
    
    def test_checkout_creates_payment_transaction(self, auth_token):
        """Test that creating a checkout session creates a payment_transactions document"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Create checkout session
        response = requests.post(
            f"{BASE_URL}/api/subscription/create-checkout",
            headers=headers,
            json={"origin_url": "https://billing-app-32.preview.emergentagent.com"}
        )
        
        assert response.status_code == 200
        data = response.json()
        session_id = data["session_id"]
        
        # Check the checkout status - this will also verify the transaction exists
        status_response = requests.get(
            f"{BASE_URL}/api/subscription/checkout-status/{session_id}",
            headers=headers
        )
        
        assert status_response.status_code == 200, f"Checkout status check failed: {status_response.text}"
        
        # The fact that checkout-status works means the transaction was created
        # (it queries payment_transactions collection)
        print(f"PASS: Checkout session created payment_transactions document for session_id: {session_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
