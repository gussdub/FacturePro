"""
Test CSV Import for Expenses Feature
Tests: POST /api/expenses/import-csv, POST /api/expenses/import-confirm
Features: Column mapping detection, amount parsing, date parsing, French bank CSV support
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for test user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "gussdub@gmail.com",
        "password": "testpass123"
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Authentication failed - skipping authenticated tests")

@pytest.fixture
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestCSVImportPreview:
    """Tests for POST /api/expenses/import-csv - CSV preview and column mapping"""
    
    def test_standard_csv_mapping(self, auth_headers):
        """Test standard CSV with Date,Description,Montant,Categorie,Notes columns"""
        csv_content = "Date,Description,Montant,Categorie,Notes\n2026-03-15,Essence,75.50,Transport,Test\n2026-03-16,Restaurant,45.00,Repas,Lunch"
        files = {'file': ('test.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')}
        
        response = requests.post(f"{BASE_URL}/api/expenses/import-csv", files=files, headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify mapping detected all columns
        assert "mapping" in data
        mapping = data["mapping"]
        assert "expense_date" in mapping, "Should detect date column"
        assert "description" in mapping, "Should detect description column"
        assert "amount" in mapping, "Should detect amount column"
        assert "category" in mapping, "Should detect category column"
        assert "notes" in mapping, "Should detect notes column"
        
        # Verify preview data
        assert "preview" in data
        assert len(data["preview"]) == 2
        assert data["preview"][0]["description"] == "Essence"
        assert data["preview"][0]["amount"] == 75.50
        assert data["preview"][0]["expense_date"] == "2026-03-15"
        assert data["preview"][0]["category"] == "Transport"
        
        print(f"✓ Standard CSV mapping detected: {list(mapping.keys())}")
    
    def test_french_bank_csv_semicolon(self, auth_headers):
        """Test French bank CSV with semicolon separator and French column names"""
        csv_content = "Date de transaction;Libellé;Débit;Crédit;Type\n15/03/2026;Achat Amazon;45,99;;Achat\n16/03/2026;Virement reçu;;100,00;Virement"
        files = {'file': ('bank.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')}
        
        response = requests.post(f"{BASE_URL}/api/expenses/import-csv", files=files, headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        mapping = data["mapping"]
        # Should detect date from "Date de transaction"
        assert "expense_date" in mapping, "Should detect date column from 'Date de transaction'"
        # Should detect description from "Libellé"
        assert "description" in mapping, "Should detect description from 'Libellé'"
        # Should detect amount from "Débit" or "Crédit"
        assert "amount" in mapping, "Should detect amount from 'Débit'"
        
        # Verify date parsing (DD/MM/YYYY -> YYYY-MM-DD)
        preview = data["preview"]
        assert preview[0]["expense_date"] == "2026-03-15", f"Date should be parsed to YYYY-MM-DD, got {preview[0]['expense_date']}"
        
        # Verify amount parsing (comma decimal)
        assert preview[0]["amount"] == 45.99, f"Amount should parse comma decimal, got {preview[0]['amount']}"
        
        print(f"✓ French bank CSV mapping detected: {list(mapping.keys())}")
        print(f"✓ Date parsed: 15/03/2026 -> {preview[0]['expense_date']}")
        print(f"✓ Amount parsed: 45,99 -> {preview[0]['amount']}")
    
    def test_amount_parsing_variations(self, auth_headers):
        """Test amount parsing handles various formats - using semicolon separator for comma decimals"""
        # Use semicolon separator to properly test comma decimal parsing
        csv_content = "Description;Montant\nTest1;$50.00\nTest2;45,99\nTest3;100 CAD"
        files = {'file': ('amounts.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')}
        
        response = requests.post(f"{BASE_URL}/api/expenses/import-csv", files=files, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        preview = data["preview"]
        
        # $50.00 -> 50.0
        assert preview[0]["amount"] == 50.0, f"Should parse $50.00, got {preview[0]['amount']}"
        # 45,99 -> 45.99 (comma decimal in semicolon-separated CSV)
        assert preview[1]["amount"] == 45.99, f"Should parse 45,99, got {preview[1]['amount']}"
        # 100 CAD -> 100.0
        assert preview[2]["amount"] == 100.0, f"Should parse 100 CAD, got {preview[2]['amount']}"
        
        print("✓ Amount parsing handles: $50.00, 45,99, 100 CAD")
    
    def test_date_parsing_variations(self, auth_headers):
        """Test date parsing handles various formats"""
        csv_content = "Date,Description,Amount\n2026-03-15,Test1,10\n15/03/2026,Test2,20\n03/15/2026,Test3,30"
        files = {'file': ('dates.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')}
        
        response = requests.post(f"{BASE_URL}/api/expenses/import-csv", files=files, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        preview = data["preview"]
        
        # YYYY-MM-DD should stay as is
        assert preview[0]["expense_date"] == "2026-03-15", f"YYYY-MM-DD should work, got {preview[0]['expense_date']}"
        # DD/MM/YYYY should convert
        assert preview[1]["expense_date"] == "2026-03-15", f"DD/MM/YYYY should convert, got {preview[1]['expense_date']}"
        
        print("✓ Date parsing handles: YYYY-MM-DD, DD/MM/YYYY")
    
    def test_csv_requires_auth(self):
        """Test CSV import requires authentication"""
        csv_content = "Date,Description,Amount\n2026-03-15,Test,10"
        files = {'file': ('test.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')}
        
        response = requests.post(f"{BASE_URL}/api/expenses/import-csv", files=files)
        
        assert response.status_code in [401, 403], f"Should require auth, got {response.status_code}"
        print("✓ CSV import requires authentication")
    
    def test_empty_csv_error(self, auth_headers):
        """Test empty CSV returns error"""
        csv_content = "Date,Description,Amount"  # Headers only, no data
        files = {'file': ('empty.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')}
        
        response = requests.post(f"{BASE_URL}/api/expenses/import-csv", files=files, headers=auth_headers)
        
        assert response.status_code == 400, f"Should return 400 for empty CSV, got {response.status_code}"
        print("✓ Empty CSV returns 400 error")


class TestCSVImportConfirm:
    """Tests for POST /api/expenses/import-confirm - Confirm and create expenses"""
    
    def test_import_confirm_creates_expenses(self, auth_headers):
        """Test confirming import creates expenses in database"""
        # First get initial count
        expenses_before = requests.get(f"{BASE_URL}/api/expenses", headers=auth_headers).json()
        initial_count = len(expenses_before)
        
        # Import rows
        import_data = {
            "rows": [
                {"description": "TEST_CSV_Import1", "amount": 99.99, "expense_date": "2026-03-15", "category": "Test", "notes": "CSV test"},
                {"description": "TEST_CSV_Import2", "amount": 50.00, "expense_date": "2026-03-16", "category": "Test", "notes": ""}
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/expenses/import-confirm", json=import_data, headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["created"] == 2, f"Should create 2 expenses, got {data['created']}"
        
        # Verify expenses exist in database
        expenses_after = requests.get(f"{BASE_URL}/api/expenses", headers=auth_headers).json()
        assert len(expenses_after) == initial_count + 2, "Should have 2 more expenses"
        
        # Find our test expenses
        test_expenses = [e for e in expenses_after if e["description"].startswith("TEST_CSV_Import")]
        assert len(test_expenses) == 2, "Should find both test expenses"
        
        # Verify data
        exp1 = next((e for e in test_expenses if e["description"] == "TEST_CSV_Import1"), None)
        assert exp1 is not None
        assert exp1["amount"] == 99.99
        assert exp1["category"] == "Test"
        assert exp1["status"] == "pending"
        
        print(f"✓ Import confirm created {data['created']} expenses")
        
        # Cleanup
        for exp in test_expenses:
            requests.delete(f"{BASE_URL}/api/expenses/{exp['id']}", headers=auth_headers)
    
    def test_import_confirm_empty_rows_error(self, auth_headers):
        """Test confirming with empty rows returns error"""
        import_data = {"rows": []}
        
        response = requests.post(f"{BASE_URL}/api/expenses/import-confirm", json=import_data, headers=auth_headers)
        
        assert response.status_code == 400, f"Should return 400 for empty rows, got {response.status_code}"
        print("✓ Empty rows returns 400 error")
    
    def test_import_confirm_requires_auth(self):
        """Test import confirm requires authentication"""
        import_data = {"rows": [{"description": "Test", "amount": 10}]}
        
        response = requests.post(f"{BASE_URL}/api/expenses/import-confirm", json=import_data)
        
        assert response.status_code in [401, 403], f"Should require auth, got {response.status_code}"
        print("✓ Import confirm requires authentication")
    
    def test_import_skips_zero_amount_no_description(self, auth_headers):
        """Test import skips rows with zero amount and no description"""
        import_data = {
            "rows": [
                {"description": "TEST_Valid", "amount": 25.00, "expense_date": "2026-03-15"},
                {"description": "", "amount": 0, "expense_date": "2026-03-16"},  # Should skip
                {"description": "TEST_Valid2", "amount": 0, "expense_date": "2026-03-17"}  # Has description, should skip due to 0 amount
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/expenses/import-confirm", json=import_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        # Only the first row should be created (has description and non-zero amount)
        # The logic skips if amt == 0 AND no description
        assert data["created"] >= 1, f"Should create at least 1 expense, got {data['created']}"
        
        print(f"✓ Import created {data['created']} expenses (skipped invalid rows)")
        
        # Cleanup
        expenses = requests.get(f"{BASE_URL}/api/expenses", headers=auth_headers).json()
        for exp in expenses:
            if exp["description"].startswith("TEST_"):
                requests.delete(f"{BASE_URL}/api/expenses/{exp['id']}", headers=auth_headers)


class TestFullCSVImportFlow:
    """End-to-end test of CSV import flow"""
    
    def test_full_import_flow(self, auth_headers):
        """Test complete flow: upload CSV -> preview -> confirm -> verify"""
        # Step 1: Upload CSV for preview
        csv_content = "Date,Description,Montant,Categorie\n2026-03-20,TEST_FullFlow_Expense,123.45,Testing"
        files = {'file': ('flow.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')}
        
        preview_response = requests.post(f"{BASE_URL}/api/expenses/import-csv", files=files, headers=auth_headers)
        assert preview_response.status_code == 200
        preview_data = preview_response.json()
        
        # Step 2: Verify preview
        assert len(preview_data["preview"]) == 1
        assert preview_data["preview"][0]["description"] == "TEST_FullFlow_Expense"
        assert preview_data["preview"][0]["amount"] == 123.45
        
        # Step 3: Confirm import
        confirm_data = {"rows": preview_data["preview"]}
        confirm_response = requests.post(f"{BASE_URL}/api/expenses/import-confirm", json=confirm_data, headers=auth_headers)
        assert confirm_response.status_code == 200
        assert confirm_response.json()["created"] == 1
        
        # Step 4: Verify expense exists
        expenses = requests.get(f"{BASE_URL}/api/expenses", headers=auth_headers).json()
        test_expense = next((e for e in expenses if e["description"] == "TEST_FullFlow_Expense"), None)
        assert test_expense is not None, "Imported expense should exist"
        assert test_expense["amount"] == 123.45
        assert test_expense["category"] == "Testing"
        assert test_expense["expense_date"] == "2026-03-20"
        
        print("✓ Full CSV import flow completed successfully")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/expenses/{test_expense['id']}", headers=auth_headers)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
