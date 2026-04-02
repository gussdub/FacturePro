"""
Test suite for FacturePro Quote/Invoice Number Features
Tests:
1. Editable quote_number field in quotes
2. Editable invoice_number field in invoices
3. Backend PUT /api/quotes/{id} recalculates taxes when items change
4. Backend PUT /api/invoices/{id} allows updating invoice_number
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication for tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "gussdub@gmail.com",
            "password": "testpass123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get auth headers"""
        return {"Authorization": f"Bearer {auth_token}"}


class TestQuoteNumberFeatures(TestAuth):
    """Test quote_number field editing and tax recalculation"""
    
    def test_login_success(self):
        """Test login with provided credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "gussdub@gmail.com",
            "password": "testpass123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        print("✓ Login successful")
    
    def test_get_existing_quotes(self, auth_headers):
        """Get existing quotes to find one to edit"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=auth_headers)
        assert response.status_code == 200
        quotes = response.json()
        print(f"✓ Found {len(quotes)} existing quotes")
        return quotes
    
    def test_create_quote_with_items(self, auth_headers):
        """Create a new quote with items to test tax calculation"""
        # First get a client
        clients_resp = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        assert clients_resp.status_code == 200
        clients = clients_resp.json()
        assert len(clients) > 0, "No clients found"
        client_id = clients[0]["id"]
        
        # Create quote with items
        quote_data = {
            "client_id": client_id,
            "valid_until": "2026-12-31",
            "province": "QC",
            "items": [
                {"description": "TEST_Service A", "quantity": 2, "unit_price": 100.00},
                {"description": "TEST_Service B", "quantity": 1, "unit_price": 50.00}
            ],
            "notes": "Test quote for number editing"
        }
        response = requests.post(f"{BASE_URL}/api/quotes", json=quote_data, headers=auth_headers)
        assert response.status_code == 200
        quote = response.json()
        
        # Verify quote was created with auto-generated number
        assert "quote_number" in quote
        assert quote["quote_number"].startswith("QUO-")
        
        # Verify tax calculation (QC: TPS 5% + TVQ 9.975%)
        subtotal = 2 * 100 + 1 * 50  # 250
        expected_gst = round(subtotal * 0.05, 2)  # 12.50
        expected_pst = round(subtotal * 0.09975, 2)  # 24.94
        expected_total = round(subtotal + expected_gst + expected_pst, 2)  # 287.44
        
        assert quote["subtotal"] == subtotal
        assert quote["gst_amount"] == expected_gst
        assert quote["pst_amount"] == expected_pst
        assert quote["total"] == expected_total
        
        print(f"✓ Created quote {quote['quote_number']} with correct taxes")
        return quote
    
    def test_update_quote_number(self, auth_headers):
        """Test updating quote_number field"""
        # Create a quote first
        clients_resp = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        clients = clients_resp.json()
        client_id = clients[0]["id"]
        
        create_resp = requests.post(f"{BASE_URL}/api/quotes", json={
            "client_id": client_id,
            "valid_until": "2026-12-31",
            "province": "QC",
            "items": [{"description": "TEST_Item", "quantity": 1, "unit_price": 100}],
            "notes": "Test for quote number update"
        }, headers=auth_headers)
        assert create_resp.status_code == 200
        quote = create_resp.json()
        quote_id = quote["id"]
        original_number = quote["quote_number"]
        
        # Update the quote_number
        new_quote_number = f"CUSTOM-{uuid.uuid4().hex[:6].upper()}"
        update_resp = requests.put(f"{BASE_URL}/api/quotes/{quote_id}", json={
            "quote_number": new_quote_number
        }, headers=auth_headers)
        assert update_resp.status_code == 200
        updated_quote = update_resp.json()
        
        assert updated_quote["quote_number"] == new_quote_number
        print(f"✓ Updated quote_number from {original_number} to {new_quote_number}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/quotes/{quote_id}", headers=auth_headers)
        return updated_quote
    
    def test_put_quote_recalculates_taxes(self, auth_headers):
        """Test that PUT /api/quotes/{id} recalculates taxes when items change"""
        # Create a quote
        clients_resp = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        clients = clients_resp.json()
        client_id = clients[0]["id"]
        
        create_resp = requests.post(f"{BASE_URL}/api/quotes", json={
            "client_id": client_id,
            "valid_until": "2026-12-31",
            "province": "QC",
            "items": [{"description": "TEST_Original", "quantity": 1, "unit_price": 100}],
            "notes": "Test for tax recalculation"
        }, headers=auth_headers)
        assert create_resp.status_code == 200
        quote = create_resp.json()
        quote_id = quote["id"]
        
        original_subtotal = quote["subtotal"]
        original_total = quote["total"]
        
        # Update with new items (higher value)
        new_items = [
            {"description": "TEST_New Item 1", "quantity": 3, "unit_price": 200},
            {"description": "TEST_New Item 2", "quantity": 2, "unit_price": 150}
        ]
        update_resp = requests.put(f"{BASE_URL}/api/quotes/{quote_id}", json={
            "items": new_items,
            "province": "QC"
        }, headers=auth_headers)
        assert update_resp.status_code == 200
        updated_quote = update_resp.json()
        
        # Verify taxes were recalculated
        new_subtotal = 3 * 200 + 2 * 150  # 900
        expected_gst = round(new_subtotal * 0.05, 2)  # 45.00
        expected_pst = round(new_subtotal * 0.09975, 2)  # 89.78
        expected_total = round(new_subtotal + expected_gst + expected_pst, 2)  # 1034.78
        
        assert updated_quote["subtotal"] == new_subtotal
        assert updated_quote["gst_amount"] == expected_gst
        assert updated_quote["pst_amount"] == expected_pst
        assert updated_quote["total"] == expected_total
        
        print(f"✓ PUT /api/quotes recalculated taxes: subtotal {original_subtotal} -> {new_subtotal}, total {original_total} -> {expected_total}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/quotes/{quote_id}", headers=auth_headers)
        return updated_quote


class TestInvoiceNumberFeatures(TestAuth):
    """Test invoice_number field editing"""
    
    def test_get_existing_invoices(self, auth_headers):
        """Get existing invoices"""
        response = requests.get(f"{BASE_URL}/api/invoices", headers=auth_headers)
        assert response.status_code == 200
        invoices = response.json()
        print(f"✓ Found {len(invoices)} existing invoices")
        return invoices
    
    def test_create_invoice_with_items(self, auth_headers):
        """Create a new invoice with items"""
        # Get a client
        clients_resp = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        clients = clients_resp.json()
        client_id = clients[0]["id"]
        
        # Create invoice
        invoice_data = {
            "client_id": client_id,
            "due_date": "2026-12-31",
            "province": "QC",
            "items": [
                {"description": "TEST_Invoice Item", "quantity": 5, "unit_price": 75.00}
            ],
            "notes": "Test invoice for number editing"
        }
        response = requests.post(f"{BASE_URL}/api/invoices", json=invoice_data, headers=auth_headers)
        assert response.status_code == 200
        invoice = response.json()
        
        # Verify invoice was created with auto-generated number
        assert "invoice_number" in invoice
        assert invoice["invoice_number"].startswith("INV-")
        
        # Verify tax calculation
        subtotal = 5 * 75  # 375
        expected_gst = round(subtotal * 0.05, 2)  # 18.75
        expected_pst = round(subtotal * 0.09975, 2)  # 37.41
        expected_total = round(subtotal + expected_gst + expected_pst, 2)  # 431.16
        
        assert invoice["subtotal"] == subtotal
        assert invoice["gst_amount"] == expected_gst
        assert invoice["pst_amount"] == expected_pst
        assert invoice["total"] == expected_total
        
        print(f"✓ Created invoice {invoice['invoice_number']} with correct taxes")
        return invoice
    
    def test_update_invoice_number(self, auth_headers):
        """Test updating invoice_number field"""
        # Create an invoice first
        clients_resp = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        clients = clients_resp.json()
        client_id = clients[0]["id"]
        
        create_resp = requests.post(f"{BASE_URL}/api/invoices", json={
            "client_id": client_id,
            "due_date": "2026-12-31",
            "province": "QC",
            "items": [{"description": "TEST_Item", "quantity": 1, "unit_price": 100}],
            "notes": "Test for invoice number update"
        }, headers=auth_headers)
        assert create_resp.status_code == 200
        invoice = create_resp.json()
        invoice_id = invoice["id"]
        original_number = invoice["invoice_number"]
        
        # Update the invoice_number
        new_invoice_number = f"FACT-{uuid.uuid4().hex[:6].upper()}"
        update_resp = requests.put(f"{BASE_URL}/api/invoices/{invoice_id}", json={
            "invoice_number": new_invoice_number
        }, headers=auth_headers)
        assert update_resp.status_code == 200
        updated_invoice = update_resp.json()
        
        assert updated_invoice["invoice_number"] == new_invoice_number
        print(f"✓ Updated invoice_number from {original_number} to {new_invoice_number}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/invoices/{invoice_id}", headers=auth_headers)
        return updated_invoice
    
    def test_put_invoice_recalculates_taxes(self, auth_headers):
        """Test that PUT /api/invoices/{id} recalculates taxes when items change"""
        # Create an invoice
        clients_resp = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        clients = clients_resp.json()
        client_id = clients[0]["id"]
        
        create_resp = requests.post(f"{BASE_URL}/api/invoices", json={
            "client_id": client_id,
            "due_date": "2026-12-31",
            "province": "QC",
            "items": [{"description": "TEST_Original", "quantity": 1, "unit_price": 100}],
            "notes": "Test for tax recalculation"
        }, headers=auth_headers)
        assert create_resp.status_code == 200
        invoice = create_resp.json()
        invoice_id = invoice["id"]
        
        original_subtotal = invoice["subtotal"]
        original_total = invoice["total"]
        
        # Update with new items
        new_items = [
            {"description": "TEST_New Item", "quantity": 4, "unit_price": 250}
        ]
        update_resp = requests.put(f"{BASE_URL}/api/invoices/{invoice_id}", json={
            "items": new_items,
            "province": "QC"
        }, headers=auth_headers)
        assert update_resp.status_code == 200
        updated_invoice = update_resp.json()
        
        # Verify taxes were recalculated
        new_subtotal = 4 * 250  # 1000
        expected_gst = round(new_subtotal * 0.05, 2)  # 50.00
        expected_pst = round(new_subtotal * 0.09975, 2)  # 99.75
        expected_total = round(new_subtotal + expected_gst + expected_pst, 2)  # 1149.75
        
        assert updated_invoice["subtotal"] == new_subtotal
        assert updated_invoice["gst_amount"] == expected_gst
        assert updated_invoice["pst_amount"] == expected_pst
        assert updated_invoice["total"] == expected_total
        
        print(f"✓ PUT /api/invoices recalculated taxes: subtotal {original_subtotal} -> {new_subtotal}, total {original_total} -> {expected_total}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/invoices/{invoice_id}", headers=auth_headers)
        return updated_invoice


class TestPDFGeneration(TestAuth):
    """Test PDF generation still works after changes"""
    
    def test_quote_pdf_generation(self, auth_headers):
        """Test quote PDF generation"""
        # Get existing quotes
        quotes_resp = requests.get(f"{BASE_URL}/api/quotes", headers=auth_headers)
        quotes = quotes_resp.json()
        
        if len(quotes) == 0:
            pytest.skip("No quotes available for PDF test")
        
        quote_id = quotes[0]["id"]
        pdf_resp = requests.get(f"{BASE_URL}/api/quotes/{quote_id}/pdf", headers=auth_headers)
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers.get("content-type") == "application/pdf"
        assert len(pdf_resp.content) > 0
        print(f"✓ Quote PDF generated successfully ({len(pdf_resp.content)} bytes)")
    
    def test_invoice_pdf_generation(self, auth_headers):
        """Test invoice PDF generation"""
        # Get existing invoices
        invoices_resp = requests.get(f"{BASE_URL}/api/invoices", headers=auth_headers)
        invoices = invoices_resp.json()
        
        if len(invoices) == 0:
            pytest.skip("No invoices available for PDF test")
        
        invoice_id = invoices[0]["id"]
        pdf_resp = requests.get(f"{BASE_URL}/api/invoices/{invoice_id}/pdf", headers=auth_headers)
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers.get("content-type") == "application/pdf"
        assert len(pdf_resp.content) > 0
        print(f"✓ Invoice PDF generated successfully ({len(pdf_resp.content)} bytes)")


class TestCleanup(TestAuth):
    """Cleanup test data"""
    
    def test_cleanup_test_quotes(self, auth_headers):
        """Remove test quotes"""
        quotes_resp = requests.get(f"{BASE_URL}/api/quotes", headers=auth_headers)
        quotes = quotes_resp.json()
        deleted = 0
        for quote in quotes:
            if any(item.get("description", "").startswith("TEST_") for item in quote.get("items", [])):
                requests.delete(f"{BASE_URL}/api/quotes/{quote['id']}", headers=auth_headers)
                deleted += 1
        print(f"✓ Cleaned up {deleted} test quotes")
    
    def test_cleanup_test_invoices(self, auth_headers):
        """Remove test invoices"""
        invoices_resp = requests.get(f"{BASE_URL}/api/invoices", headers=auth_headers)
        invoices = invoices_resp.json()
        deleted = 0
        for invoice in invoices:
            if any(item.get("description", "").startswith("TEST_") for item in invoice.get("items", [])):
                requests.delete(f"{BASE_URL}/api/invoices/{invoice['id']}", headers=auth_headers)
                deleted += 1
        print(f"✓ Cleaned up {deleted} test invoices")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
