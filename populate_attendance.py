"""
Script to create sample attendance data for testing
"""

import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "horilla.settings")
sys.path.insert(0, ".")
django.setup()

from datetime import datetime, timedelta

from django.contrib.auth.models import User

from attendance.models import Attendance
from base.models import Company
from employee.models import Employee, EmployeeWorkInformation

# Get company and employees
company = Company.objects.get(company="Horilla Corp")
employees = Employee.objects.all()

print(f"Company: {company}")
print(f"Employees: {employees.count()}")

if employees.count() == 0:
    print("✗ No employees found. Run populate_employees.py first.")
    sys.exit(1)

# Create attendance records for each employee
attendance_count = 0
today = datetime.now().date()

for i, emp in enumerate(employees):
    # Create attendance for last 7 days
    for day_offset in range(7):
        attendance_date = today - timedelta(days=day_offset)

        # Skip weekends
        if attendance_date.weekday() >= 5:
            continue

        # Check if attendance already exists
        existing = Attendance.objects.filter(
            employee_id=emp, attendance_date=attendance_date
        ).exists()

        if not existing:
            try:
                att = Attendance.objects.create(
                    employee_id=emp,
                    attendance_date=attendance_date,
                    attendance_day=attendance_date.strftime("%A"),
                    attendance_validated=day_offset > 1,  # Older records are validated
                )
                attendance_count += 1
                print(
                    f"  ✓ Created attendance for {emp.employee_first_name} on {attendance_date}"
                )
            except Exception as e:
                print(f"  ✗ Error: {str(e)}")

print(f"\n✓ Created {attendance_count} attendance records")
print(f"✓ Total Attendance: {Attendance.objects.count()}")
