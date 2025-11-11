#!/usr/bin/env python3
"""
Quick authentication test for FacturePro
"""

import requests
import json

BACKEND_URL = "https://facturepro.preview.emergentagent.com/api"
TEST_EMAIL = "gussdub@gmail.com"
TEST_PASSWORD = "testpass123"

print("Testing authentication...")

# Try to login first
print(f"1. Attempting login with {TEST_EMAIL}")
response = requests.post(
    f"{BACKEND_URL}/auth/login",
    json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    timeout=10
)

print(f"Login response: {response.status_code}")
if response.status_code != 200:
    print(f"Login failed: {response.text}")
    
    # Try to register the user
    print(f"2. Attempting to register {TEST_EMAIL}")
    response = requests.post(
        f"{BACKEND_URL}/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "company_name": "Test Company"
        },
        timeout=10
    )
    
    print(f"Register response: {response.status_code}")
    if response.status_code == 200:
        print("Registration successful!")
        data = response.json()
        print(f"User ID: {data.get('user', {}).get('id')}")
    else:
        print(f"Registration failed: {response.text}")
        
    # Try login again
    print(f"3. Attempting login again with {TEST_EMAIL}")
    response = requests.post(
        f"{BACKEND_URL}/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=10
    )
    
    print(f"Second login response: {response.status_code}")
    if response.status_code == 200:
        print("Login successful!")
        data = response.json()
        print(f"Token received: {bool(data.get('access_token'))}")
    else:
        print(f"Second login failed: {response.text}")
else:
    print("Login successful!")
    data = response.json()
    print(f"Token received: {bool(data.get('access_token'))}")