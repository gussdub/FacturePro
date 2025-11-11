#!/usr/bin/env python3
"""
Test Resend email functionality directly
"""

import resend
import os
from dotenv import load_dotenv

# Load from backend directory
load_dotenv('/app/backend/.env')

RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL')

print(f"RESEND_API_KEY: {RESEND_API_KEY[:10]}..." if RESEND_API_KEY else "None")
print(f"SENDER_EMAIL: {SENDER_EMAIL}")

# Initialize Resend
resend.api_key = RESEND_API_KEY

# Test simple email
try:
    print("\nTesting simple email...")
    result = resend.Emails.send({
        "from": SENDER_EMAIL,
        "to": ["test.client@example.com"],
        "subject": "Test Email",
        "html": "<h1>Test</h1><p>This is a test email.</p>"
    })
    print(f"✅ Simple email sent: {result}")
except Exception as e:
    print(f"❌ Simple email failed: {e}")

# Test email with attachment
try:
    print("\nTesting email with attachment...")
    import base64
    
    # Create a simple text file as attachment
    test_content = "This is a test PDF content"
    encoded_content = base64.b64encode(test_content.encode()).decode()
    
    result = resend.Emails.send({
        "from": SENDER_EMAIL,
        "to": ["test.client@example.com"],
        "subject": "Test Email with Attachment",
        "html": "<h1>Test with Attachment</h1><p>This email has an attachment.</p>",
        "attachments": [{
            "filename": "test.txt",
            "content": encoded_content
        }]
    })
    print(f"✅ Email with attachment sent: {result}")
except Exception as e:
    print(f"❌ Email with attachment failed: {e}")