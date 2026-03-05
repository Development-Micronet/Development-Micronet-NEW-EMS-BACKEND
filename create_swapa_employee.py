#!/usr/bin/env python
"""
Create Employee with Swapa credentials
"""
import json
import os
from datetime import datetime

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "horilla.settings")
django.setup()

from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

# Generate unique ID
unique_id = datetime.now().strftime("%H%M%S")

# Employee data with swapa credentials
user_data = {
    "employee_first_name": "Swapa",
    "employee_last_name": "User",
    "email": f"swapa.employee.{unique_id}@company.com",
    "phone": "7719017328",
    "badge_id": f"EMP{unique_id}",
    "gender": "male",
    "dob": "1999-03-10",
    "address": "12 Ram Nagpur",
    "country": "India",
    "state": "Maharashtra",
    "city": "Nagpur",
    "zip": "440028",
    "qualification": "Bachelor's Degree",
    "experience": 2,
    "marital_status": "single",
    "emergency_contact": "9822140456",
    "emergency_contact_name": "Family",
    "emergency_contact_relation": "Brother",
    "username": "swapa",
    "password": "swap1234",
}

print("=" * 80)
print("CREATING EMPLOYEE - SWAPA WITH BRAVE METHOD EMAIL")
print("=" * 80)
print()

# Get or create test user
try:
    test_user = User.objects.get(username="testadmin")
except User.DoesNotExist:
    test_user = User.objects.create_superuser(
        "testadmin", "test@horilla.com", "testpass123"
    )

# Generate token
refresh = RefreshToken.for_user(test_user)
access_token = str(refresh.access_token)

# Make request
client = APIClient()
client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

print(f"👤 Employee Username: swapa")
print(f"🔐 Password: swap1234")
print(f'📧 Employee Email: {user_data["email"]}')
print()
print("📡 Sending POST request...")
print("-" * 80)

response = client.post(
    "http://127.0.0.1:8000/api/employee/list/employees/", user_data, format="json"
)

print(f"\nStatus Code: {response.status_code}")
print()

if response.status_code in [200, 201]:
    data = response.json()
    print("✅ EMPLOYEE CREATED SUCCESSFULLY!")
    print()
    print("=" * 80)
    print("EMPLOYEE CREATED")
    print("=" * 80)
    print(f'Employee ID: {data.get("id")}')
    print(f'Name: {data.get("employee_first_name")} {data.get("employee_last_name")}')
    print(f'Email: {data.get("email")}')
    print(f"Username: swapa")
    print(f"Password: swap1234")
    print(f'Django User ID: {data.get("employee_user_id")}')
    print()
    print("=" * 80)
    print("EMAIL SENDING")
    print("=" * 80)
    print(f'📧 Email sent to: {data.get("email")}')
    print(f"   From: swapshantk@gmail.com (HR Management)")
    print(f"   Subject: Your Account Credentials - Employee Management System")
    print()
    print("⚠️ EMAIL SHOULD ARRIVE IN YOUR INBOX")
    print("   Check spam folder if not found")
    print()
else:
    print("❌ ERROR!")
    print(json.dumps(response.json(), indent=2))
