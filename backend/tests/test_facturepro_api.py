"""
FacturePro API Tests - Comprehensive Backend Testing
Tests: Auth, Clients, Products, Invoices, Quotes, Employees, Expenses, Settings, Dashboard, CSV Export
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://resend-factures.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_EMAIL = "gussdub@gmail.com"
TEST_PASSWORD = "testpass123"


class TestHealth:
    """Health check tests"""
    
    def test_health_endpoint(self):
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        print("✅ Health check passed")


class TestAuth:
    """Authentication tests"""
    
    def test_login_success(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == TEST_EMAIL
        assert data["token_type"] == "bearer"
        print(f"✅ Login successful for {TEST_EMAIL}")
    
    def test_login_invalid_credentials(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@example.com",
            "password": "wrongpass"
        })
        assert response.status_code == 401
        print("✅ Invalid login correctly rejected")
    
    def test_register_new_user(self):
        unique_email = f"TEST_user_{uuid.uuid4().hex[:8]}@test.com"
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "testpass123",
            "company_name": "TEST Company"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == unique_email
        assert data["user"]["company_name"] == "TEST Company"
        print(f"✅ Registration successful for {unique_email}")
    
    def test_register_duplicate_email(self):
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": TEST_EMAIL,
            "password": "testpass123",
            "company_name": "Duplicate Company"
        })
        assert response.status_code == 400
        print("✅ Duplicate email registration correctly rejected")
    
    def test_forgot_password(self):
        response = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={
            "email": TEST_EMAIL
        })
        assert response.status_code == 200
        data = response.json()
        assert "reset_token" in data
        print("✅ Forgot password token generated")
    
    def test_reset_password_invalid_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/reset-password", json={
            "token": "invalid_token",
            "new_password": "newpassword123"
        })
        assert response.status_code == 400
        print("✅ Invalid reset token correctly rejected")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for protected endpoints"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        return response.json()["access_token"]
    pytest.skip("Authentication failed")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestDashboard:
    """Dashboard stats tests"""
    
    def test_get_dashboard_stats(self, auth_headers):
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify all expected fields exist
        expected_fields = ["total_clients", "total_invoices", "total_quotes", 
                          "total_products", "total_employees", "total_expenses",
                          "total_revenue", "pending_invoices"]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        # Verify data types
        assert isinstance(data["total_clients"], int)
        assert isinstance(data["total_revenue"], (int, float))
        print(f"✅ Dashboard stats: {data['total_clients']} clients, {data['total_invoices']} invoices, ${data['total_revenue']} revenue")


class TestClients:
    """Clients CRUD tests"""
    
    def test_get_clients(self, auth_headers):
        response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print(f"✅ Got {len(response.json())} clients")
    
    def test_create_client(self, auth_headers):
        client_data = {
            "name": f"TEST_Client_{uuid.uuid4().hex[:6]}",
            "email": f"test_{uuid.uuid4().hex[:6]}@client.com",
            "phone": "514-555-1234",
            "address": "123 Test Street",
            "city": "Montreal",
            "postal_code": "H1A 1A1",
            "country": "Canada"
        }
        response = requests.post(f"{BASE_URL}/api/clients", json=client_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == client_data["name"]
        assert data["email"] == client_data["email"]
        assert "id" in data
        print(f"✅ Created client: {data['name']}")
        return data["id"]
    
    def test_update_client(self, auth_headers):
        # Create a client first
        client_data = {
            "name": f"TEST_UpdateClient_{uuid.uuid4().hex[:6]}",
            "email": f"update_{uuid.uuid4().hex[:6]}@client.com"
        }
        create_response = requests.post(f"{BASE_URL}/api/clients", json=client_data, headers=auth_headers)
        client_id = create_response.json()["id"]
        
        # Update the client
        update_data = {"name": "TEST_Updated Name", "phone": "514-999-8888"}
        update_response = requests.put(f"{BASE_URL}/api/clients/{client_id}", json=update_data, headers=auth_headers)
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["name"] == "TEST_Updated Name"
        assert updated["phone"] == "514-999-8888"
        
        # Verify persistence with GET
        get_response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        clients = get_response.json()
        found = next((c for c in clients if c["id"] == client_id), None)
        assert found is not None
        assert found["name"] == "TEST_Updated Name"
        print(f"✅ Updated client: {client_id}")
    
    def test_delete_client(self, auth_headers):
        # Create a client first
        client_data = {
            "name": f"TEST_DeleteClient_{uuid.uuid4().hex[:6]}",
            "email": f"delete_{uuid.uuid4().hex[:6]}@client.com"
        }
        create_response = requests.post(f"{BASE_URL}/api/clients", json=client_data, headers=auth_headers)
        client_id = create_response.json()["id"]
        
        # Delete the client
        delete_response = requests.delete(f"{BASE_URL}/api/clients/{client_id}", headers=auth_headers)
        assert delete_response.status_code == 200
        
        # Verify deletion
        get_response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        clients = get_response.json()
        found = next((c for c in clients if c["id"] == client_id), None)
        assert found is None
        print(f"✅ Deleted client: {client_id}")


class TestProducts:
    """Products CRUD tests"""
    
    def test_get_products(self, auth_headers):
        response = requests.get(f"{BASE_URL}/api/products", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print(f"✅ Got {len(response.json())} products")
    
    def test_create_product(self, auth_headers):
        product_data = {
            "name": f"TEST_Product_{uuid.uuid4().hex[:6]}",
            "description": "Test product description",
            "unit_price": 99.99,
            "unit": "heure",
            "category": "Services"
        }
        response = requests.post(f"{BASE_URL}/api/products", json=product_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == product_data["name"]
        assert data["unit_price"] == 99.99
        assert "id" in data
        print(f"✅ Created product: {data['name']} at ${data['unit_price']}")
        return data["id"]
    
    def test_update_product(self, auth_headers):
        # Create a product first
        product_data = {
            "name": f"TEST_UpdateProduct_{uuid.uuid4().hex[:6]}",
            "unit_price": 50.00
        }
        create_response = requests.post(f"{BASE_URL}/api/products", json=product_data, headers=auth_headers)
        product_id = create_response.json()["id"]
        
        # Update the product
        update_data = {"name": "TEST_Updated Product", "unit_price": 75.00}
        update_response = requests.put(f"{BASE_URL}/api/products/{product_id}", json=update_data, headers=auth_headers)
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["name"] == "TEST_Updated Product"
        assert updated["unit_price"] == 75.00
        print(f"✅ Updated product: {product_id}")
    
    def test_delete_product(self, auth_headers):
        # Create a product first
        product_data = {
            "name": f"TEST_DeleteProduct_{uuid.uuid4().hex[:6]}",
            "unit_price": 25.00
        }
        create_response = requests.post(f"{BASE_URL}/api/products", json=product_data, headers=auth_headers)
        product_id = create_response.json()["id"]
        
        # Delete the product (soft delete - sets is_active to False)
        delete_response = requests.delete(f"{BASE_URL}/api/products/{product_id}", headers=auth_headers)
        assert delete_response.status_code == 200
        
        # Verify deletion (product should not appear in active products list)
        get_response = requests.get(f"{BASE_URL}/api/products", headers=auth_headers)
        products = get_response.json()
        found = next((p for p in products if p["id"] == product_id), None)
        assert found is None
        print(f"✅ Deleted product: {product_id}")


class TestInvoices:
    """Invoices CRUD tests with tax calculation"""
    
    def test_get_invoices(self, auth_headers):
        response = requests.get(f"{BASE_URL}/api/invoices", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print(f"✅ Got {len(response.json())} invoices")
    
    def test_create_invoice_qc_taxes(self, auth_headers):
        """Test invoice creation with Quebec taxes (GST 5% + PST 9.975%)"""
        invoice_data = {
            "client_id": "test-client-id",
            "items": [
                {"name": "Service A", "quantity": 2, "unit_price": 100.00},
                {"name": "Service B", "quantity": 1, "unit_price": 50.00}
            ],
            "province": "QC",
            "due_date": "2026-02-15",
            "notes": "TEST invoice for QC taxes"
        }
        response = requests.post(f"{BASE_URL}/api/invoices", json=invoice_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify tax calculation for QC
        # Subtotal: 2*100 + 1*50 = 250
        # GST (5%): 12.50
        # PST (9.975%): 24.94
        # Total: 287.44
        assert data["subtotal"] == 250.00
        assert data["gst_amount"] == 12.50
        assert abs(data["pst_amount"] - 24.94) < 0.01  # Allow small rounding difference
        assert data["hst_amount"] == 0
        assert "invoice_number" in data
        print(f"✅ Created QC invoice: {data['invoice_number']} - Subtotal: ${data['subtotal']}, GST: ${data['gst_amount']}, PST: ${data['pst_amount']}, Total: ${data['total']}")
        return data["id"]
    
    def test_create_invoice_on_taxes(self, auth_headers):
        """Test invoice creation with Ontario taxes (HST 13%)"""
        invoice_data = {
            "client_id": "test-client-id",
            "items": [
                {"name": "Service C", "quantity": 1, "unit_price": 200.00}
            ],
            "province": "ON",
            "due_date": "2026-02-20",
            "notes": "TEST invoice for ON taxes"
        }
        response = requests.post(f"{BASE_URL}/api/invoices", json=invoice_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify tax calculation for ON
        # Subtotal: 200
        # HST (13%): 26
        # Total: 226
        assert data["subtotal"] == 200.00
        assert data["gst_amount"] == 0
        assert data["pst_amount"] == 0
        assert data["hst_amount"] == 26.00
        assert data["total"] == 226.00
        print(f"✅ Created ON invoice: {data['invoice_number']} - Subtotal: ${data['subtotal']}, HST: ${data['hst_amount']}, Total: ${data['total']}")
    
    def test_update_invoice_status(self, auth_headers):
        # Create an invoice first
        invoice_data = {
            "client_id": "test-client-id",
            "items": [{"name": "Test", "quantity": 1, "unit_price": 100.00}],
            "province": "QC"
        }
        create_response = requests.post(f"{BASE_URL}/api/invoices", json=invoice_data, headers=auth_headers)
        invoice_id = create_response.json()["id"]
        
        # Update status
        status_response = requests.put(f"{BASE_URL}/api/invoices/{invoice_id}/status", 
                                       json={"status": "sent"}, headers=auth_headers)
        assert status_response.status_code == 200
        
        # Verify status change
        get_response = requests.get(f"{BASE_URL}/api/invoices", headers=auth_headers)
        invoices = get_response.json()
        found = next((i for i in invoices if i["id"] == invoice_id), None)
        assert found is not None
        assert found["status"] == "sent"
        print(f"✅ Updated invoice status to 'sent': {invoice_id}")
    
    def test_delete_invoice(self, auth_headers):
        # Create an invoice first
        invoice_data = {
            "client_id": "test-client-id",
            "items": [{"name": "Delete Test", "quantity": 1, "unit_price": 50.00}],
            "province": "QC"
        }
        create_response = requests.post(f"{BASE_URL}/api/invoices", json=invoice_data, headers=auth_headers)
        invoice_id = create_response.json()["id"]
        
        # Delete the invoice
        delete_response = requests.delete(f"{BASE_URL}/api/invoices/{invoice_id}", headers=auth_headers)
        assert delete_response.status_code == 200
        
        # Verify deletion
        get_response = requests.get(f"{BASE_URL}/api/invoices", headers=auth_headers)
        invoices = get_response.json()
        found = next((i for i in invoices if i["id"] == invoice_id), None)
        assert found is None
        print(f"✅ Deleted invoice: {invoice_id}")


class TestQuotes:
    """Quotes CRUD tests"""
    
    def test_get_quotes(self, auth_headers):
        response = requests.get(f"{BASE_URL}/api/quotes", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print(f"✅ Got {len(response.json())} quotes")
    
    def test_create_quote(self, auth_headers):
        quote_data = {
            "client_id": "test-client-id",
            "items": [
                {"name": "Quote Item A", "quantity": 3, "unit_price": 150.00}
            ],
            "province": "QC",
            "valid_until": "2026-03-01",
            "notes": "TEST quote"
        }
        response = requests.post(f"{BASE_URL}/api/quotes", json=quote_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["subtotal"] == 450.00
        assert "quote_number" in data
        assert data["status"] == "pending"
        print(f"✅ Created quote: {data['quote_number']} - Total: ${data['total']}")
        return data["id"]
    
    def test_convert_quote_to_invoice(self, auth_headers):
        # Create a quote first
        quote_data = {
            "client_id": "test-client-id",
            "items": [{"name": "Convert Test", "quantity": 1, "unit_price": 200.00}],
            "province": "QC"
        }
        create_response = requests.post(f"{BASE_URL}/api/quotes", json=quote_data, headers=auth_headers)
        quote_id = create_response.json()["id"]
        
        # Convert to invoice
        convert_response = requests.post(f"{BASE_URL}/api/quotes/{quote_id}/convert", 
                                         json={"due_date": "2026-02-28"}, headers=auth_headers)
        assert convert_response.status_code == 200
        invoice_data = convert_response.json()
        assert "invoice_number" in invoice_data
        assert invoice_data["subtotal"] == 200.00
        
        # Verify quote status changed to converted
        get_response = requests.get(f"{BASE_URL}/api/quotes", headers=auth_headers)
        quotes = get_response.json()
        found = next((q for q in quotes if q["id"] == quote_id), None)
        assert found is not None
        assert found["status"] == "converted"
        print(f"✅ Converted quote {quote_id} to invoice {invoice_data['invoice_number']}")
    
    def test_delete_quote(self, auth_headers):
        # Create a quote first
        quote_data = {
            "client_id": "test-client-id",
            "items": [{"name": "Delete Test", "quantity": 1, "unit_price": 100.00}],
            "province": "QC"
        }
        create_response = requests.post(f"{BASE_URL}/api/quotes", json=quote_data, headers=auth_headers)
        quote_id = create_response.json()["id"]
        
        # Delete the quote
        delete_response = requests.delete(f"{BASE_URL}/api/quotes/{quote_id}", headers=auth_headers)
        assert delete_response.status_code == 200
        
        # Verify deletion
        get_response = requests.get(f"{BASE_URL}/api/quotes", headers=auth_headers)
        quotes = get_response.json()
        found = next((q for q in quotes if q["id"] == quote_id), None)
        assert found is None
        print(f"✅ Deleted quote: {quote_id}")


class TestEmployees:
    """Employees CRUD tests"""
    
    def test_get_employees(self, auth_headers):
        response = requests.get(f"{BASE_URL}/api/employees", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print(f"✅ Got {len(response.json())} employees")
    
    def test_create_employee(self, auth_headers):
        employee_data = {
            "name": f"TEST_Employee_{uuid.uuid4().hex[:6]}",
            "email": f"emp_{uuid.uuid4().hex[:6]}@company.com",
            "phone": "514-555-9999",
            "employee_number": f"EMP-{uuid.uuid4().hex[:4].upper()}",
            "department": "Engineering"
        }
        response = requests.post(f"{BASE_URL}/api/employees", json=employee_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == employee_data["name"]
        assert data["department"] == "Engineering"
        assert "id" in data
        print(f"✅ Created employee: {data['name']}")
        return data["id"]
    
    def test_update_employee(self, auth_headers):
        # Create an employee first
        employee_data = {
            "name": f"TEST_UpdateEmployee_{uuid.uuid4().hex[:6]}",
            "email": f"update_emp_{uuid.uuid4().hex[:6]}@company.com"
        }
        create_response = requests.post(f"{BASE_URL}/api/employees", json=employee_data, headers=auth_headers)
        employee_id = create_response.json()["id"]
        
        # Update the employee
        update_data = {"name": "TEST_Updated Employee", "department": "Sales"}
        update_response = requests.put(f"{BASE_URL}/api/employees/{employee_id}", json=update_data, headers=auth_headers)
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["name"] == "TEST_Updated Employee"
        assert updated["department"] == "Sales"
        print(f"✅ Updated employee: {employee_id}")
    
    def test_delete_employee(self, auth_headers):
        # Create an employee first
        employee_data = {
            "name": f"TEST_DeleteEmployee_{uuid.uuid4().hex[:6]}",
            "email": f"delete_emp_{uuid.uuid4().hex[:6]}@company.com"
        }
        create_response = requests.post(f"{BASE_URL}/api/employees", json=employee_data, headers=auth_headers)
        employee_id = create_response.json()["id"]
        
        # Delete the employee (soft delete)
        delete_response = requests.delete(f"{BASE_URL}/api/employees/{employee_id}", headers=auth_headers)
        assert delete_response.status_code == 200
        
        # Verify deletion
        get_response = requests.get(f"{BASE_URL}/api/employees", headers=auth_headers)
        employees = get_response.json()
        found = next((e for e in employees if e["id"] == employee_id), None)
        assert found is None
        print(f"✅ Deleted employee: {employee_id}")


class TestExpenses:
    """Expenses CRUD tests"""
    
    def test_get_expenses(self, auth_headers):
        response = requests.get(f"{BASE_URL}/api/expenses", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print(f"✅ Got {len(response.json())} expenses")
    
    def test_create_expense(self, auth_headers):
        expense_data = {
            "description": f"TEST_Expense_{uuid.uuid4().hex[:6]}",
            "amount": 125.50,
            "category": "Travel",
            "expense_date": "2026-01-15",
            "notes": "Test expense"
        }
        response = requests.post(f"{BASE_URL}/api/expenses", json=expense_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == expense_data["description"]
        assert data["amount"] == 125.50
        assert data["status"] == "pending"
        assert "id" in data
        print(f"✅ Created expense: {data['description']} - ${data['amount']}")
        return data["id"]
    
    def test_update_expense_status(self, auth_headers):
        # Create an expense first
        expense_data = {
            "description": f"TEST_StatusExpense_{uuid.uuid4().hex[:6]}",
            "amount": 75.00,
            "category": "Office"
        }
        create_response = requests.post(f"{BASE_URL}/api/expenses", json=expense_data, headers=auth_headers)
        expense_id = create_response.json()["id"]
        
        # Update status
        status_response = requests.put(f"{BASE_URL}/api/expenses/{expense_id}/status", 
                                       json={"status": "approved"}, headers=auth_headers)
        assert status_response.status_code == 200
        
        # Verify status change
        get_response = requests.get(f"{BASE_URL}/api/expenses", headers=auth_headers)
        expenses = get_response.json()
        found = next((e for e in expenses if e["id"] == expense_id), None)
        assert found is not None
        assert found["status"] == "approved"
        print(f"✅ Updated expense status to 'approved': {expense_id}")
    
    def test_delete_expense(self, auth_headers):
        # Create an expense first
        expense_data = {
            "description": f"TEST_DeleteExpense_{uuid.uuid4().hex[:6]}",
            "amount": 50.00,
            "category": "Misc"
        }
        create_response = requests.post(f"{BASE_URL}/api/expenses", json=expense_data, headers=auth_headers)
        expense_id = create_response.json()["id"]
        
        # Delete the expense
        delete_response = requests.delete(f"{BASE_URL}/api/expenses/{expense_id}", headers=auth_headers)
        assert delete_response.status_code == 200
        
        # Verify deletion
        get_response = requests.get(f"{BASE_URL}/api/expenses", headers=auth_headers)
        expenses = get_response.json()
        found = next((e for e in expenses if e["id"] == expense_id), None)
        assert found is None
        print(f"✅ Deleted expense: {expense_id}")


class TestSettings:
    """Company settings tests"""
    
    def test_get_company_settings(self, auth_headers):
        response = requests.get(f"{BASE_URL}/api/settings/company", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "company_name" in data
        assert "email" in data
        assert "primary_color" in data
        print(f"✅ Got company settings for: {data['company_name']}")
    
    def test_update_company_settings(self, auth_headers):
        update_data = {
            "phone": "514-TEST-1234",
            "address": "123 Test Avenue",
            "city": "Montreal",
            "postal_code": "H1A 1A1"
        }
        response = requests.put(f"{BASE_URL}/api/settings/company", json=update_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["phone"] == "514-TEST-1234"
        assert data["city"] == "Montreal"
        
        # Verify persistence
        get_response = requests.get(f"{BASE_URL}/api/settings/company", headers=auth_headers)
        settings = get_response.json()
        assert settings["phone"] == "514-TEST-1234"
        print(f"✅ Updated company settings")


class TestCSVExport:
    """CSV export tests"""
    
    def test_export_invoices_csv(self, auth_headers):
        response = requests.get(f"{BASE_URL}/api/export/invoices/csv", headers=auth_headers)
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        assert "factures.csv" in response.headers.get("content-disposition", "")
        
        # Verify CSV content has headers
        content = response.text
        assert "Numero" in content or "numero" in content.lower()
        print(f"✅ Exported invoices CSV ({len(content)} bytes)")
    
    def test_export_expenses_csv(self, auth_headers):
        response = requests.get(f"{BASE_URL}/api/export/expenses/csv", headers=auth_headers)
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        assert "depenses.csv" in response.headers.get("content-disposition", "")
        
        # Verify CSV content has headers
        content = response.text
        assert "Description" in content or "description" in content.lower()
        print(f"✅ Exported expenses CSV ({len(content)} bytes)")


class TestUnauthorizedAccess:
    """Test that protected endpoints require authentication"""
    
    def test_clients_requires_auth(self):
        response = requests.get(f"{BASE_URL}/api/clients")
        assert response.status_code in [401, 403]
        print("✅ Clients endpoint requires authentication")
    
    def test_invoices_requires_auth(self):
        response = requests.get(f"{BASE_URL}/api/invoices")
        assert response.status_code in [401, 403]
        print("✅ Invoices endpoint requires authentication")
    
    def test_dashboard_requires_auth(self):
        response = requests.get(f"{BASE_URL}/api/dashboard/stats")
        assert response.status_code in [401, 403]
        print("✅ Dashboard endpoint requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
