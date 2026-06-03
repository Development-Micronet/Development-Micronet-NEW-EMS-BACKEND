#!/usr/bin/env python
"""
Test Employee Work Information API - Direct Database Access
"""

import os
import sys

import django

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "horilla.settings")
django.setup()

from base.models import Company, Department, EmployeeShift, JobPosition, WorkType
from employee.models import Employee, EmployeeWorkInformation

print("=" * 70)
print("✅ Work Information Setup Verification")
print("=" * 70)
print()

print("1️⃣  Checking Database Records")
print()

# Check created records
depts = Department.objects.filter(department="IT")
print(f"Departments (IT): {depts.count()} record(s)")
for dept in depts:
    print(f"  - {dept.department} (ID: {dept.id})")

jobs = JobPosition.objects.filter(job_position="Software Developer")
print(f"\nJob Positions (Software Developer): {jobs.count()} record(s)")
for job in jobs:
    print(f"  - {job.job_position} (ID: {job.id})")

shifts = EmployeeShift.objects.filter(employee_shift="Morning Shift")
print(f"\nShifts (Morning Shift): {shifts.count()} record(s)")
for shift in shifts:
    print(f"  - {shift.employee_shift} (ID: {shift.id})")

work_types = WorkType.objects.filter(work_type="Full Time")
print(f"\nWork Types (Full Time): {work_types.count()} record(s)")
for wt in work_types:
    print(f"  - {wt.work_type} (ID: {wt.id})")

print("\n2️⃣  Checking Work Information")
print()

work_infos = EmployeeWorkInformation.objects.all()
print(f"Total Work Information Records: {work_infos.count()}")

for wi in work_infos[:5]:  # Show first 5
    emp = wi.employee_id
    print(
        f"\n  Employee: {emp.employee_first_name} {emp.employee_last_name} (ID: {emp.id})"
    )
    print(
        f"  - Department: {wi.department_id.department if wi.department_id else 'N/A'} (ID: {wi.department_id.id if wi.department_id else 'N/A'})"
    )
    print(
        f"  - Job Position: {wi.job_position_id.job_position if wi.job_position_id else 'N/A'} (ID: {wi.job_position_id.id if wi.job_position_id else 'N/A'})"
    )
    print(
        f"  - Shift: {wi.shift_id.employee_shift if wi.shift_id else 'N/A'} (ID: {wi.shift_id.id if wi.shift_id else 'N/A'})"
    )
    print(
        f"  - Work Type: {wi.work_type_id.work_type if wi.work_type_id else 'N/A'} (ID: {wi.work_type_id.id if wi.work_type_id else 'N/A'})"
    )

print("\n" + "=" * 70)
print("✅ Database Verification Complete!")
print("=" * 70)
print(
    """
You can now test the API endpoints:

1. GET Work Information:
   curl -H "Authorization: Token YOUR_TOKEN" http://localhost:8000/api/employee/employee-work-information/

2. POST New Work Information (for employee without existing):
   curl -X POST -H "Authorization: Token YOUR_TOKEN" \\
        -H "Content-Type: application/json" \\
        -d '{"employee_id":2,"department_id":1,"job_position_id":1,"shift_id":1,"work_type_id":1,"company_id":1,"reporting_manager_id":1}' \\
        http://localhost:8000/api/employee/employee-work-information/

3. Via Swagger UI:
   http://localhost:8000/swagger/
"""
)
