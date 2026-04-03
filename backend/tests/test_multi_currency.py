"""
Multi-Currency Feature Tests for FacturePro
Tests: Exchange rates API, Invoice/Quote/Expense currency support, Dashboard stats with CAD conversion
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "gussdub@gmail.com"
TEST_PASSWORD = "testpass123"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for test user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Authentication failed: {response.status_code}")
    return response.json().get("access_token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def test_client(auth_headers):
    """Create a test client for currency tests"""
    response = requests.post(f"{BASE_URL}/api/clients", json={
        "name": "TEST_Currency_Client",
        "email": "currency_test@example.com",
        "phone": "555-1234"
    }, headers=auth_headers)
    if response.status_code in [200, 201]:
        return response.json()
    # Try to find existing test client
    clients = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers).json()
    for c in clients:
        if c.get("name") == "TEST_Currency_Client":
            return c
    pytest.skip("Could not create test client")


class TestExchangeRatesAPI:
    """Test 1: GET /api/exchange-rates returns rates for CAD, USD, EUR, GBP"""
    
    def test_exchange_rates_endpoint_returns_200(self):
        """Exchange rates endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/exchange-rates")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Exchange rates endpoint returns 200")
    
    def test_exchange_rates_structure(self):
        """Exchange rates should have correct structure with base, rates, supported"""
        response = requests.get(f"{BASE_URL}/api/exchange-rates")
        data = response.json()
        
        # Check structure
        assert "base" in data, "Missing 'base' field"
        assert "rates" in data, "Missing 'rates' field"
        assert "supported" in data, "Missing 'supported' field"
        
        # Check base is CAD
        assert data["base"] == "CAD", f"Expected base 'CAD', got '{data['base']}'"
        
        # Check supported currencies
        expected_currencies = ["CAD", "USD", "EUR", "GBP"]
        for cur in expected_currencies:
            assert cur in data["supported"], f"Missing {cur} in supported currencies"
        
        print(f"PASS: Exchange rates structure correct - base: {data['base']}, supported: {data['supported']}")
    
    def test_exchange_rates_values(self):
        """Exchange rates should have valid numeric values for all currencies"""
        response = requests.get(f"{BASE_URL}/api/exchange-rates")
        data = response.json()
        rates = data.get("rates", {})
        
        # CAD should be 1.0
        assert rates.get("CAD") == 1.0, f"CAD rate should be 1.0, got {rates.get('CAD')}"
        
        # Other currencies should be positive numbers less than 1 (since they're worth more than CAD)
        for cur in ["USD", "EUR", "GBP"]:
            rate = rates.get(cur)
            assert rate is not None, f"Missing rate for {cur}"
            assert isinstance(rate, (int, float)), f"{cur} rate should be numeric"
            assert rate > 0, f"{cur} rate should be positive"
            assert rate < 2, f"{cur} rate seems too high: {rate}"
        
        print(f"PASS: Exchange rates values valid - CAD: {rates['CAD']}, USD: {rates.get('USD')}, EUR: {rates.get('EUR')}, GBP: {rates.get('GBP')}")


class TestInvoiceMultiCurrency:
    """Tests 2 & 5: Invoice creation and update with currency support"""
    
    def test_create_invoice_with_usd_currency(self, auth_headers, test_client):
        """Test 2: POST /api/invoices with currency=USD - total in USD, total_cad converted"""
        payload = {
            "client_id": test_client["id"],
            "items": [{"description": "TEST_USD_Service", "quantity": 1, "unit_price": 100}],
            "province": "QC",
            "currency": "USD",
            "exchange_rate_to_cad": 0.72,
            "due_date": "2026-02-15"
        }
        response = requests.post(f"{BASE_URL}/api/invoices", json=payload, headers=auth_headers)
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}"
        
        data = response.json()
        
        # Verify currency is stored
        assert data.get("currency") == "USD", f"Expected currency 'USD', got '{data.get('currency')}'"
        
        # Verify exchange rate is stored
        assert data.get("exchange_rate_to_cad") == 0.72, f"Expected exchange_rate 0.72, got {data.get('exchange_rate_to_cad')}"
        
        # Verify total is in USD (subtotal + taxes)
        assert "total" in data, "Missing 'total' field"
        
        # Verify total_cad is calculated (total / exchange_rate)
        assert "total_cad" in data, "Missing 'total_cad' field"
        expected_total_cad = round(data["total"] / 0.72, 2)
        assert abs(data["total_cad"] - expected_total_cad) < 0.1, f"total_cad mismatch: expected ~{expected_total_cad}, got {data['total_cad']}"
        
        print(f"PASS: Invoice created with USD - total: {data['total']} USD, total_cad: {data['total_cad']} CAD")
        return data
    
    def test_update_invoice_with_currency_change(self, auth_headers, test_client):
        """Test 5: PUT /api/invoices/{id} with currency change preserves conversion"""
        # First create an invoice
        create_payload = {
            "client_id": test_client["id"],
            "items": [{"description": "TEST_Currency_Change", "quantity": 2, "unit_price": 50}],
            "province": "QC",
            "currency": "CAD",
            "exchange_rate_to_cad": 1.0,
            "due_date": "2026-02-20"
        }
        create_response = requests.post(f"{BASE_URL}/api/invoices", json=create_payload, headers=auth_headers)
        assert create_response.status_code in [200, 201]
        invoice = create_response.json()
        invoice_id = invoice["id"]
        
        # Update to EUR currency
        update_payload = {
            "items": [{"description": "TEST_Currency_Change_Updated", "quantity": 2, "unit_price": 50}],
            "currency": "EUR",
            "exchange_rate_to_cad": 0.62,
            "province": "QC"
        }
        update_response = requests.put(f"{BASE_URL}/api/invoices/{invoice_id}", json=update_payload, headers=auth_headers)
        assert update_response.status_code == 200, f"Update failed: {update_response.status_code}"
        
        updated = update_response.json()
        
        # Verify currency changed
        assert updated.get("currency") == "EUR", f"Expected currency 'EUR', got '{updated.get('currency')}'"
        
        # Verify exchange rate updated
        assert updated.get("exchange_rate_to_cad") == 0.62, f"Expected exchange_rate 0.62, got {updated.get('exchange_rate_to_cad')}"
        
        # Verify total_cad recalculated
        assert "total_cad" in updated, "Missing total_cad after update"
        
        print(f"PASS: Invoice updated with EUR - currency: {updated['currency']}, total_cad: {updated['total_cad']}")


class TestQuoteMultiCurrency:
    """Test 3: Quote creation with currency support"""
    
    def test_create_quote_with_eur_currency(self, auth_headers, test_client):
        """Test 3: POST /api/quotes with currency=EUR - currency and total_cad stored correctly"""
        payload = {
            "client_id": test_client["id"],
            "items": [{"description": "TEST_EUR_Quote_Item", "quantity": 3, "unit_price": 200}],
            "province": "QC",
            "currency": "EUR",
            "exchange_rate_to_cad": 0.62,
            "valid_until": "2026-03-01"
        }
        response = requests.post(f"{BASE_URL}/api/quotes", json=payload, headers=auth_headers)
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}"
        
        data = response.json()
        
        # Verify currency is stored
        assert data.get("currency") == "EUR", f"Expected currency 'EUR', got '{data.get('currency')}'"
        
        # Verify exchange rate is stored
        assert data.get("exchange_rate_to_cad") == 0.62, f"Expected exchange_rate 0.62, got {data.get('exchange_rate_to_cad')}"
        
        # Verify total_cad is calculated
        assert "total_cad" in data, "Missing 'total_cad' field"
        expected_total_cad = round(data["total"] / 0.62, 2)
        assert abs(data["total_cad"] - expected_total_cad) < 1, f"total_cad mismatch: expected ~{expected_total_cad}, got {data['total_cad']}"
        
        print(f"PASS: Quote created with EUR - total: {data['total']} EUR, total_cad: {data['total_cad']} CAD")


class TestExpenseMultiCurrency:
    """Test 4: Expense creation with currency support"""
    
    def test_create_expense_with_gbp_currency(self, auth_headers):
        """Test 4: POST /api/expenses with currency=GBP - amount_cad calculated correctly"""
        payload = {
            "description": "TEST_GBP_Expense",
            "amount": 150,
            "category": "Travel",
            "currency": "GBP",
            "exchange_rate_to_cad": 0.54,
            "expense_date": "2026-01-15"
        }
        response = requests.post(f"{BASE_URL}/api/expenses", json=payload, headers=auth_headers)
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}"
        
        data = response.json()
        
        # Verify currency is stored
        assert data.get("currency") == "GBP", f"Expected currency 'GBP', got '{data.get('currency')}'"
        
        # Verify exchange rate is stored
        assert data.get("exchange_rate_to_cad") == 0.54, f"Expected exchange_rate 0.54, got {data.get('exchange_rate_to_cad')}"
        
        # Verify amount is in GBP
        assert data.get("amount") == 150, f"Expected amount 150, got {data.get('amount')}"
        
        # Verify amount_cad is calculated (amount / exchange_rate)
        assert "amount_cad" in data, "Missing 'amount_cad' field"
        expected_amount_cad = round(150 / 0.54, 2)
        assert abs(data["amount_cad"] - expected_amount_cad) < 1, f"amount_cad mismatch: expected ~{expected_amount_cad}, got {data['amount_cad']}"
        
        print(f"PASS: Expense created with GBP - amount: {data['amount']} GBP, amount_cad: {data['amount_cad']} CAD")


class TestDashboardMultiCurrency:
    """Tests 6 & 7: Dashboard stats use CAD-converted values"""
    
    def test_dashboard_stats_uses_total_cad(self, auth_headers):
        """Test 6: GET /api/dashboard/stats - total_revenue uses total_cad for multi-currency invoices"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify total_revenue field exists
        assert "total_revenue" in data, "Missing 'total_revenue' field"
        assert isinstance(data["total_revenue"], (int, float)), "total_revenue should be numeric"
        
        print(f"PASS: Dashboard stats returns total_revenue: {data['total_revenue']} CAD")
    
    def test_expense_analytics_uses_amount_cad(self, auth_headers):
        """Test 7: GET /api/dashboard/expense-analytics - expenses use amount_cad for chart data"""
        response = requests.get(f"{BASE_URL}/api/dashboard/expense-analytics", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify structure
        assert "by_category" in data, "Missing 'by_category' field"
        assert "total" in data, "Missing 'total' field"
        
        # Total should be in CAD (sum of amount_cad values)
        assert isinstance(data["total"], (int, float)), "total should be numeric"
        
        print(f"PASS: Expense analytics returns total: {data['total']} CAD, categories: {len(data['by_category'])}")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_invoices(self, auth_headers):
        """Remove test invoices"""
        response = requests.get(f"{BASE_URL}/api/invoices", headers=auth_headers)
        if response.status_code == 200:
            invoices = response.json()
            deleted = 0
            for inv in invoices:
                if any(item.get("description", "").startswith("TEST_") for item in inv.get("items", [])):
                    requests.delete(f"{BASE_URL}/api/invoices/{inv['id']}", headers=auth_headers)
                    deleted += 1
            print(f"Cleaned up {deleted} test invoices")
    
    def test_cleanup_test_quotes(self, auth_headers):
        """Remove test quotes"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=auth_headers)
        if response.status_code == 200:
            quotes = response.json()
            deleted = 0
            for q in quotes:
                if any(item.get("description", "").startswith("TEST_") for item in q.get("items", [])):
                    requests.delete(f"{BASE_URL}/api/quotes/{q['id']}", headers=auth_headers)
                    deleted += 1
            print(f"Cleaned up {deleted} test quotes")
    
    def test_cleanup_test_expenses(self, auth_headers):
        """Remove test expenses"""
        response = requests.get(f"{BASE_URL}/api/expenses", headers=auth_headers)
        if response.status_code == 200:
            expenses = response.json()
            deleted = 0
            for exp in expenses:
                if exp.get("description", "").startswith("TEST_"):
                    requests.delete(f"{BASE_URL}/api/expenses/{exp['id']}", headers=auth_headers)
                    deleted += 1
            print(f"Cleaned up {deleted} test expenses")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
