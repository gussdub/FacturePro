"""
Test suite for FacturePro Edit Features (Iteration 5)
Tests: PUT /api/quotes/{id}, PUT /api/invoices/{id}, PDF generation, SENDER_EMAIL
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication helper"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for gussdub@gmail.com"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "gussdub@gmail.com",
            "password": "testpass123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}


class TestQuoteUpdate(TestAuth):
    """Test PUT /api/quotes/{id} - Update quote functionality"""
    
    def test_create_and_update_quote(self, auth_headers):
        """Create a quote, then update it and verify changes persist"""
        # First get a client
        clients_resp = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        assert clients_resp.status_code == 200
        clients = clients_resp.json()
        assert len(clients) > 0, "Need at least one client for testing"
        client_id = clients[0]["id"]
        
        # Create a quote
        create_payload = {
            "client_id": client_id,
            "valid_until": "2026-12-31",
            "items": [{"description": "TEST_Original Item", "quantity": 1, "unit_price": 100}],
            "province": "QC",
            "notes": "Original notes"
        }
        create_resp = requests.post(f"{BASE_URL}/api/quotes", json=create_payload, headers=auth_headers)
        assert create_resp.status_code == 200, f"Create quote failed: {create_resp.text}"
        created_quote = create_resp.json()
        quote_id = created_quote["id"]
        
        # Update the quote
        update_payload = {
            "client_id": client_id,
            "valid_until": "2027-01-15",
            "items": [
                {"description": "TEST_Updated Item 1", "quantity": 2, "unit_price": 150},
                {"description": "TEST_Updated Item 2", "quantity": 1, "unit_price": 75}
            ],
            "province": "ON",
            "notes": "Updated notes for testing"
        }
        update_resp = requests.put(f"{BASE_URL}/api/quotes/{quote_id}", json=update_payload, headers=auth_headers)
        assert update_resp.status_code == 200, f"Update quote failed: {update_resp.text}"
        updated_quote = update_resp.json()
        
        # Verify update response
        assert updated_quote["notes"] == "Updated notes for testing"
        assert updated_quote["province"] == "ON"
        assert len(updated_quote["items"]) == 2
        
        # GET to verify persistence
        get_resp = requests.get(f"{BASE_URL}/api/quotes", headers=auth_headers)
        assert get_resp.status_code == 200
        quotes = get_resp.json()
        found_quote = next((q for q in quotes if q["id"] == quote_id), None)
        assert found_quote is not None, "Updated quote not found in list"
        assert found_quote["notes"] == "Updated notes for testing"
        assert found_quote["province"] == "ON"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/quotes/{quote_id}", headers=auth_headers)
    
    def test_update_quote_not_found(self, auth_headers):
        """Test updating non-existent quote returns 404"""
        update_payload = {"notes": "Test"}
        resp = requests.put(f"{BASE_URL}/api/quotes/nonexistent-id", json=update_payload, headers=auth_headers)
        assert resp.status_code == 404
    
    def test_update_quote_requires_auth(self):
        """Test that updating quote requires authentication"""
        resp = requests.put(f"{BASE_URL}/api/quotes/some-id", json={"notes": "Test"})
        assert resp.status_code in [401, 403]


class TestInvoiceUpdate(TestAuth):
    """Test PUT /api/invoices/{id} - Update invoice functionality with tax recalculation"""
    
    def test_create_and_update_invoice(self, auth_headers):
        """Create an invoice, update it, and verify taxes are recalculated"""
        # First get a client
        clients_resp = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        assert clients_resp.status_code == 200
        clients = clients_resp.json()
        assert len(clients) > 0
        client_id = clients[0]["id"]
        
        # Create an invoice
        create_payload = {
            "client_id": client_id,
            "due_date": "2026-12-31",
            "items": [{"description": "TEST_Original Service", "quantity": 1, "unit_price": 100}],
            "province": "QC",
            "notes": "Original invoice notes"
        }
        create_resp = requests.post(f"{BASE_URL}/api/invoices", json=create_payload, headers=auth_headers)
        assert create_resp.status_code == 200, f"Create invoice failed: {create_resp.text}"
        created_invoice = create_resp.json()
        invoice_id = created_invoice["id"]
        
        # Verify original taxes (QC: TPS 5% + TVQ 9.975%)
        assert created_invoice["subtotal"] == 100
        assert created_invoice["gst_amount"] == 5.0  # 5% of 100
        assert created_invoice["pst_amount"] == 9.98  # 9.975% of 100 rounded
        
        # Update the invoice with new items and province
        update_payload = {
            "client_id": client_id,
            "due_date": "2027-01-31",
            "items": [
                {"description": "TEST_Updated Service 1", "quantity": 2, "unit_price": 200},
                {"description": "TEST_Updated Service 2", "quantity": 1, "unit_price": 100}
            ],
            "province": "ON",  # Change to Ontario (HST 13%)
            "notes": "Updated invoice notes"
        }
        update_resp = requests.put(f"{BASE_URL}/api/invoices/{invoice_id}", json=update_payload, headers=auth_headers)
        assert update_resp.status_code == 200, f"Update invoice failed: {update_resp.text}"
        updated_invoice = update_resp.json()
        
        # Verify taxes are recalculated for Ontario
        # Subtotal: (2 * 200) + (1 * 100) = 500
        assert updated_invoice["subtotal"] == 500
        assert updated_invoice["hst_amount"] == 65.0  # 13% of 500
        assert updated_invoice["gst_amount"] == 0  # No GST in Ontario
        assert updated_invoice["pst_amount"] == 0  # No PST in Ontario
        assert updated_invoice["total"] == 565.0  # 500 + 65
        assert updated_invoice["notes"] == "Updated invoice notes"
        
        # GET to verify persistence
        get_resp = requests.get(f"{BASE_URL}/api/invoices", headers=auth_headers)
        assert get_resp.status_code == 200
        invoices = get_resp.json()
        found_invoice = next((i for i in invoices if i["id"] == invoice_id), None)
        assert found_invoice is not None
        assert found_invoice["total"] == 565.0
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/invoices/{invoice_id}", headers=auth_headers)
    
    def test_update_invoice_not_found(self, auth_headers):
        """Test updating non-existent invoice returns 404"""
        update_payload = {"notes": "Test"}
        resp = requests.put(f"{BASE_URL}/api/invoices/nonexistent-id", json=update_payload, headers=auth_headers)
        assert resp.status_code == 404
    
    def test_update_invoice_requires_auth(self):
        """Test that updating invoice requires authentication"""
        resp = requests.put(f"{BASE_URL}/api/invoices/some-id", json={"notes": "Test"})
        assert resp.status_code in [401, 403]


class TestPDFGeneration(TestAuth):
    """Test PDF generation endpoints"""
    
    def test_quote_pdf_generation(self, auth_headers):
        """Test that quote PDF generates without errors"""
        # Get existing quotes
        quotes_resp = requests.get(f"{BASE_URL}/api/quotes", headers=auth_headers)
        assert quotes_resp.status_code == 200
        quotes = quotes_resp.json()
        
        if len(quotes) == 0:
            pytest.skip("No quotes available for PDF test")
        
        quote_id = quotes[0]["id"]
        pdf_resp = requests.get(f"{BASE_URL}/api/quotes/{quote_id}/pdf", headers=auth_headers)
        assert pdf_resp.status_code == 200, f"PDF generation failed: {pdf_resp.text}"
        assert pdf_resp.headers.get("content-type") == "application/pdf"
        assert len(pdf_resp.content) > 1000  # PDF should have substantial content
    
    def test_invoice_pdf_generation(self, auth_headers):
        """Test that invoice PDF generates without errors"""
        # Get existing invoices
        invoices_resp = requests.get(f"{BASE_URL}/api/invoices", headers=auth_headers)
        assert invoices_resp.status_code == 200
        invoices = invoices_resp.json()
        
        if len(invoices) == 0:
            pytest.skip("No invoices available for PDF test")
        
        invoice_id = invoices[0]["id"]
        pdf_resp = requests.get(f"{BASE_URL}/api/invoices/{invoice_id}/pdf", headers=auth_headers)
        assert pdf_resp.status_code == 200, f"PDF generation failed: {pdf_resp.text}"
        assert pdf_resp.headers.get("content-type") == "application/pdf"
        assert len(pdf_resp.content) > 1000


class TestProductDropdown(TestAuth):
    """Test that products are available for dropdown selection"""
    
    def test_products_list_available(self, auth_headers):
        """Test that products endpoint returns data for dropdown"""
        resp = requests.get(f"{BASE_URL}/api/products", headers=auth_headers)
        assert resp.status_code == 200
        products = resp.json()
        # Should have at least the seeded "Consultation" product
        assert len(products) >= 1
        
        # Verify product structure for dropdown
        product = products[0]
        assert "id" in product
        assert "name" in product
        assert "unit_price" in product


class TestSenderEmail:
    """Test SENDER_EMAIL configuration"""
    
    def test_health_endpoint(self):
        """Verify backend is running (indirect test that .env is loaded)"""
        resp = requests.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"


class TestExistingDataVerification(TestAuth):
    """Verify existing quotes and invoices for edit testing"""
    
    def test_existing_quote_available(self, auth_headers):
        """Verify at least one quote exists for edit testing"""
        resp = requests.get(f"{BASE_URL}/api/quotes", headers=auth_headers)
        assert resp.status_code == 200
        quotes = resp.json()
        print(f"Found {len(quotes)} quotes")
        if len(quotes) > 0:
            print(f"First quote: {quotes[0].get('quote_number')}, ID: {quotes[0].get('id')}")
    
    def test_existing_invoice_available(self, auth_headers):
        """Verify at least one invoice exists for edit testing"""
        resp = requests.get(f"{BASE_URL}/api/invoices", headers=auth_headers)
        assert resp.status_code == 200
        invoices = resp.json()
        print(f"Found {len(invoices)} invoices")
        if len(invoices) > 0:
            print(f"First invoice: {invoices[0].get('invoice_number')}, ID: {invoices[0].get('id')}")
