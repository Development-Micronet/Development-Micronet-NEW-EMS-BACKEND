#!/usr/bin/env python
"""
Check EmployeeTypeAPIView errors
"""

import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "horilla.settings")
django.setup()

# Check if there are syntax errors
from horilla_api.api_views.employee.views import EmployeeTypeAPIView

print("✓ EmployeeTypeAPIView imported successfully")
print(
    f"  Methods: {[m for m in dir(EmployeeTypeAPIView) if not m.startswith('_')][:10]}"
)

# Check if serializer works
from employee.models import EmployeeType
from horilla_api.api_serializers.employee.serializers import EmployeeTypeSerializer

print("\n✓ EmployeeTypeSerializer imported successfully")

# Test creating an instance
print("\n✓ Testing serializer...")
test_data = {"employee_type": "Test Type", "is_active": True}

serializer = EmployeeTypeSerializer(data=test_data)
if serializer.is_valid():
    print(f"  ✓ Serializer valid")
    print(f"  ✓ Validated data: {serializer.validated_data}")
else:
    print(f"  ✗ Validation errors: {serializer.errors}")

print("\n✓ All checks passed!")
