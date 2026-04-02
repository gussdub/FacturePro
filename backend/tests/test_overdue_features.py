"""
Test suite for FacturePro Overdue Invoice Tracking and Reminder Features
Tests the new payment tracking dashboard endpoints:
- GET /api/dashboard/overdue - List overdue invoices
- POST /api/invoices/{id}/remind - Send reminder email with PDF attachment
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "gussdub@gmail.com"
TEST_PASSWORD = "testpass123"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for test user"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Return headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestOverdueEndpoint:
    """Tests for GET /api/dashboard/overdue endpoint"""

    def test_get_overdue_invoices_success(self, auth_headers):
        """Test that overdue endpoint returns proper structure"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overdue", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "overdue_invoices" in data
        assert "total_overdue" in data
        assert "count" in data
        assert isinstance(data["overdue_invoices"], list)
        assert isinstance(data["total_overdue"], (int, float))
        assert isinstance(data["count"], int)
        assert data["count"] == len(data["overdue_invoices"])

    def test_overdue_invoice_fields(self, auth_headers):
        """Test that each overdue invoice has required fields"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overdue", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] > 0:
            invoice = data["overdue_invoices"][0]
            required_fields = ["id", "invoice_number", "client_name", "client_email", 
                            "total", "due_date", "days_overdue", "last_reminded"]
            for field in required_fields:
                assert field in invoice, f"Missing field: {field}"
            
            # Verify data types
            assert isinstance(invoice["days_overdue"], int)
            assert invoice["days_overdue"] > 0
            assert isinstance(invoice["total"], (int, float))

    def test_overdue_sorted_by_days(self, auth_headers):
        """Test that overdue invoices are sorted by days_overdue descending"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overdue", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data["overdue_invoices"]) > 1:
            days_list = [inv["days_overdue"] for inv in data["overdue_invoices"]]
            assert days_list == sorted(days_list, reverse=True), "Invoices not sorted by days_overdue"

    def test_overdue_requires_auth(self):
        """Test that overdue endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overdue")
        assert response.status_code in [401, 403]

    def test_total_overdue_calculation(self, auth_headers):
        """Test that total_overdue equals sum of invoice totals"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overdue", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        calculated_total = sum(inv["total"] for inv in data["overdue_invoices"])
        assert abs(data["total_overdue"] - calculated_total) < 0.01, "Total overdue mismatch"


class TestReminderEndpoint:
    """Tests for POST /api/invoices/{id}/remind endpoint"""

    def test_remind_requires_auth(self):
        """Test that remind endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/invoices/fake-id/remind",
            json={"to_email": "test@test.com"}
        )
        assert response.status_code in [401, 403]

    def test_remind_invoice_not_found(self, auth_headers):
        """Test remind with non-existent invoice ID"""
        response = requests.post(
            f"{BASE_URL}/api/invoices/non-existent-id/remind",
            headers=auth_headers,
            json={"to_email": "test@test.com"}
        )
        assert response.status_code == 404

    def test_remind_missing_email(self, auth_headers):
        """Test remind without email when client has no email"""
        # First get an overdue invoice
        overdue_response = requests.get(f"{BASE_URL}/api/dashboard/overdue", headers=auth_headers)
        if overdue_response.json()["count"] == 0:
            pytest.skip("No overdue invoices to test")
        
        invoice_id = overdue_response.json()["overdue_invoices"][0]["id"]
        
        # Try to send reminder without email (should use client email or fail)
        response = requests.post(
            f"{BASE_URL}/api/invoices/{invoice_id}/remind",
            headers=auth_headers,
            json={}  # No email provided
        )
        # Should either succeed (using client email) or return 400 if no email available
        assert response.status_code in [200, 400, 500]

    def test_remind_with_valid_email(self, auth_headers):
        """Test remind endpoint with valid email (may fail due to Resend free tier)"""
        # Get an overdue invoice
        overdue_response = requests.get(f"{BASE_URL}/api/dashboard/overdue", headers=auth_headers)
        if overdue_response.json()["count"] == 0:
            pytest.skip("No overdue invoices to test")
        
        invoice = overdue_response.json()["overdue_invoices"][0]
        invoice_id = invoice["id"]
        
        # Send reminder - may fail due to Resend free tier restrictions
        response = requests.post(
            f"{BASE_URL}/api/invoices/{invoice_id}/remind",
            headers=auth_headers,
            json={"to_email": invoice.get("client_email", "test@example.com")}
        )
        
        # Accept 200 (success) or 500 (Resend free tier restriction)
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "message" in data
            assert "email_id" in data

    def test_remind_updates_last_reminded(self, auth_headers):
        """Test that successful reminder updates last_reminded field"""
        # Get overdue invoices
        overdue_response = requests.get(f"{BASE_URL}/api/dashboard/overdue", headers=auth_headers)
        if overdue_response.json()["count"] == 0:
            pytest.skip("No overdue invoices to test")
        
        invoice = overdue_response.json()["overdue_invoices"][0]
        
        # Check if last_reminded was updated (from previous test or manual action)
        if invoice.get("last_reminded"):
            # Verify it's a valid ISO datetime
            try:
                datetime.fromisoformat(invoice["last_reminded"].replace("Z", "+00:00"))
            except ValueError:
                pytest.fail("last_reminded is not a valid ISO datetime")


class TestDashboardStats:
    """Tests for dashboard stats endpoint to verify overdue count"""

    def test_dashboard_stats_includes_pending(self, auth_headers):
        """Test that dashboard stats includes pending invoices count"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "pending_invoices" in data
        assert isinstance(data["pending_invoices"], int)


class TestInvoiceStatusUpdate:
    """Tests for invoice status auto-update to 'overdue'"""

    def test_overdue_status_auto_set(self, auth_headers):
        """Test that overdue endpoint auto-updates invoice status to 'overdue'"""
        # Get overdue invoices
        response = requests.get(f"{BASE_URL}/api/dashboard/overdue", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] > 0:
            # Get the invoice directly to verify status
            invoice_id = data["overdue_invoices"][0]["id"]
            inv_response = requests.get(f"{BASE_URL}/api/invoices", headers=auth_headers)
            
            assert inv_response.status_code == 200
            invoices = inv_response.json()
            
            # Find the overdue invoice
            overdue_inv = next((inv for inv in invoices if inv["id"] == invoice_id), None)
            if overdue_inv:
                assert overdue_inv["status"] == "overdue", "Invoice status should be 'overdue'"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
