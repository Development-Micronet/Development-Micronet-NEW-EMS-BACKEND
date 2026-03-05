#!/usr/bin/env python
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "horilla.settings")
django.setup()

from base.models import Company, Department, JobPosition, JobRole, WorkType

company = Company.objects.get(id=1)

# Get or create department
dept, created = Department.objects.get_or_create(department="Engineering")
dept.company_id.add(company)
print(f"✓ Department: ID {dept.id} - Engineering")

# Get or create job position
pos, created = JobPosition.objects.get_or_create(
    job_position="Senior Developer", department_id=dept
)
print(f"✓ Job Position: ID {pos.id} - Senior Developer")

# Get or create job role (requires job_position_id)
role, created = JobRole.objects.get_or_create(job_role="Developer", job_position_id=pos)
role.company_id.add(company)
print(f"✓ Job Role: ID {role.id} - Developer")

# Get or create work type
wtype, created = WorkType.objects.get_or_create(work_type="Office")
wtype.company_id.add(company)
print(f"✓ Work Type: ID {wtype.id} - Office")

print("\n✅ Master data created successfully!")
print(f"\n=== USE THESE IDs IN YOUR WORK INFO REQUEST ===")
print(f"department_id: {dept.id}")
print(f"job_position_id: {pos.id}")
print(f"job_role_id: {role.id}")
print(f"work_type_id: {wtype.id}")
print(f"shift_id: 1")
print(f"reporting_manager_id: 11")
