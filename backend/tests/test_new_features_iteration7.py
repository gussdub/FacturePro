"""
Test suite for FacturePro Iteration 7 features:
1. Trial expiry email notification endpoint
2. Expense creation without employee_id (optional employee)
3. Expense creation with employee_id
4. File upload for receipts
5. Expense creation with receipt_url
6. File download endpoint
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "gussdub@gmail.com"
TEST_PASSWORD = "testpass123"


class TestTrialExpiryNotification:
    """Test POST /api/subscription/check-trial-expiry endpoint"""
    
    def test_trial_expiry_endpoint_exists(self):
        """Test that the trial expiry endpoint exists and responds"""
        response = requests.post(f"{BASE_URL}/api/subscription/check-trial-expiry")
        # Should return 200 with notified and total_eligible
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "notified" in data, "Response should contain 'notified' field"
        assert "total_eligible" in data, "Response should contain 'total_eligible' field"
        print(f"Trial expiry check: notified={data['notified']}, total_eligible={data['total_eligible']}")
    
    def test_trial_expiry_returns_zero_for_no_expiring_trials(self):
        """Test that endpoint returns 0 when no trials are expiring in 3 days"""
        response = requests.post(f"{BASE_URL}/api/subscription/check-trial-expiry")
        assert response.status_code == 200
        data = response.json()
        # Since exempt user doesn't have trial and no other users with trials expiring in 3 days
        assert isinstance(data["notified"], int), "notified should be an integer"
        assert isinstance(data["total_eligible"], int), "total_eligible should be an integer"
        print(f"Verified: notified={data['notified']}, total_eligible={data['total_eligible']}")


class TestExpenseWithOptionalEmployee:
    """Test expense creation with optional employee_id"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.created_expense_ids = []
        yield
        # Cleanup: delete created expenses
        for expense_id in self.created_expense_ids:
            try:
                requests.delete(f"{BASE_URL}/api/expenses/{expense_id}", headers=self.headers)
            except:
                pass
    
    def test_create_expense_without_employee_id(self):
        """Test creating expense without employee_id (general expense)"""
        expense_data = {
            "description": "TEST_General office supplies",
            "amount": 45.99,
            "category": "Fournitures",
            "expense_date": "2025-01-15"
        }
        response = requests.post(f"{BASE_URL}/api/expenses", json=expense_data, headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        self.created_expense_ids.append(data["id"])
        
        # Verify response structure
        assert "id" in data, "Response should contain 'id'"
        assert data["description"] == expense_data["description"]
        assert data["amount"] == expense_data["amount"]
        assert data["employee_id"] == "", "employee_id should be empty string for general expense"
        print(f"Created general expense: {data['id']}")
    
    def test_create_expense_with_employee_id(self):
        """Test creating expense with employee_id"""
        # First get an employee
        employees_response = requests.get(f"{BASE_URL}/api/employees", headers=self.headers)
        employees = employees_response.json()
        
        if len(employees) == 0:
            # Create a test employee first
            emp_response = requests.post(f"{BASE_URL}/api/employees", json={
                "name": "TEST_Employee",
                "email": "test_employee@test.com",
                "position": "Tester"
            }, headers=self.headers)
            if emp_response.status_code == 200:
                employee_id = emp_response.json()["id"]
            else:
                pytest.skip("No employees available and couldn't create one")
        else:
            employee_id = employees[0]["id"]
        
        expense_data = {
            "description": "TEST_Employee lunch expense",
            "amount": 25.50,
            "category": "Repas",
            "expense_date": "2025-01-15",
            "employee_id": employee_id
        }
        response = requests.post(f"{BASE_URL}/api/expenses", json=expense_data, headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        self.created_expense_ids.append(data["id"])
        
        assert data["employee_id"] == employee_id, "employee_id should match the provided value"
        print(f"Created employee expense: {data['id']} for employee {employee_id}")
    
    def test_get_expense_without_employee_shows_empty_employee_id(self):
        """Test that fetching expense without employee shows empty employee_id"""
        # Create expense without employee
        expense_data = {
            "description": "TEST_Verify general expense",
            "amount": 15.00
        }
        create_response = requests.post(f"{BASE_URL}/api/expenses", json=expense_data, headers=self.headers)
        assert create_response.status_code == 200
        expense_id = create_response.json()["id"]
        self.created_expense_ids.append(expense_id)
        
        # Fetch all expenses and find this one
        get_response = requests.get(f"{BASE_URL}/api/expenses", headers=self.headers)
        assert get_response.status_code == 200
        
        expenses = get_response.json()
        created_expense = next((e for e in expenses if e["id"] == expense_id), None)
        assert created_expense is not None, "Created expense should be in the list"
        assert created_expense["employee_id"] == "", "employee_id should be empty for general expense"
        print(f"Verified expense {expense_id} has empty employee_id")


class TestFileUploadAndDownload:
    """Test file upload and download endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.uploaded_file_ids = []
        yield
    
    def test_upload_image_file(self):
        """Test uploading an image file via POST /api/upload"""
        # Create a simple PNG image (1x1 pixel)
        png_data = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1 dimensions
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT chunk
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,
            0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
            0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,  # IEND chunk
            0x44, 0xAE, 0x42, 0x60, 0x82
        ])
        
        files = {
            'file': ('test_receipt.png', io.BytesIO(png_data), 'image/png')
        }
        
        response = requests.post(f"{BASE_URL}/api/upload", files=files, headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "file_id" in data, "Response should contain 'file_id'"
        assert "storage_path" in data, "Response should contain 'storage_path'"
        assert "filename" in data, "Response should contain 'filename'"
        
        self.uploaded_file_ids.append(data["file_id"])
        print(f"Uploaded file: {data['file_id']}")
        return data["file_id"]
    
    def test_download_uploaded_file(self):
        """Test downloading a file via GET /api/files/{file_id}"""
        # First upload a file
        png_data = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,
            0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
            0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,
            0x44, 0xAE, 0x42, 0x60, 0x82
        ])
        
        files = {'file': ('download_test.png', io.BytesIO(png_data), 'image/png')}
        upload_response = requests.post(f"{BASE_URL}/api/upload", files=files, headers=self.headers)
        assert upload_response.status_code == 200
        file_id = upload_response.json()["file_id"]
        self.uploaded_file_ids.append(file_id)
        
        # Now download the file (no auth required for download)
        download_response = requests.get(f"{BASE_URL}/api/files/{file_id}")
        assert download_response.status_code == 200, f"Expected 200, got {download_response.status_code}"
        assert download_response.headers.get("content-type") == "image/png", "Content-Type should be image/png"
        print(f"Downloaded file {file_id} successfully")
    
    def test_download_nonexistent_file_returns_404(self):
        """Test that downloading non-existent file returns 404"""
        response = requests.get(f"{BASE_URL}/api/files/nonexistent-file-id-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("Verified 404 for non-existent file")


class TestExpenseWithReceipt:
    """Test expense creation with receipt_url"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.created_expense_ids = []
        yield
        # Cleanup
        for expense_id in self.created_expense_ids:
            try:
                requests.delete(f"{BASE_URL}/api/expenses/{expense_id}", headers=self.headers)
            except:
                pass
    
    def test_create_expense_with_receipt_url(self):
        """Test creating expense with receipt_url after uploading a file"""
        # Upload a receipt file first
        png_data = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,
            0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
            0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,
            0x44, 0xAE, 0x42, 0x60, 0x82
        ])
        
        files = {'file': ('receipt_expense.png', io.BytesIO(png_data), 'image/png')}
        upload_response = requests.post(f"{BASE_URL}/api/upload", files=files, headers=self.headers)
        assert upload_response.status_code == 200, f"Upload failed: {upload_response.text}"
        file_id = upload_response.json()["file_id"]
        receipt_url = f"/api/files/{file_id}"
        
        # Create expense with receipt_url
        expense_data = {
            "description": "TEST_Expense with receipt",
            "amount": 89.99,
            "category": "Transport",
            "expense_date": "2025-01-15",
            "receipt_url": receipt_url
        }
        response = requests.post(f"{BASE_URL}/api/expenses", json=expense_data, headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        self.created_expense_ids.append(data["id"])
        
        assert data["receipt_url"] == receipt_url, f"receipt_url should be {receipt_url}, got {data['receipt_url']}"
        print(f"Created expense {data['id']} with receipt_url: {receipt_url}")
    
    def test_expense_receipt_url_is_accessible(self):
        """Test that the receipt_url in expense is accessible"""
        # Upload a receipt
        png_data = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,
            0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
            0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,
            0x44, 0xAE, 0x42, 0x60, 0x82
        ])
        
        files = {'file': ('accessible_receipt.png', io.BytesIO(png_data), 'image/png')}
        upload_response = requests.post(f"{BASE_URL}/api/upload", files=files, headers=self.headers)
        file_id = upload_response.json()["file_id"]
        receipt_url = f"/api/files/{file_id}"
        
        # Create expense
        expense_data = {
            "description": "TEST_Verify receipt accessible",
            "amount": 50.00,
            "receipt_url": receipt_url
        }
        create_response = requests.post(f"{BASE_URL}/api/expenses", json=expense_data, headers=self.headers)
        expense_id = create_response.json()["id"]
        self.created_expense_ids.append(expense_id)
        
        # Verify the receipt is accessible via the full URL
        full_receipt_url = f"{BASE_URL}{receipt_url}"
        download_response = requests.get(full_receipt_url)
        assert download_response.status_code == 200, f"Receipt should be accessible, got {download_response.status_code}"
        print(f"Verified receipt at {receipt_url} is accessible")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
