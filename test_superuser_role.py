"""
Test script to verify superuser role setting.

To run this script:
1. Navigate to project directory
2. Run: python manage.py shell < test_superuser_role.py

Or run directly:
python manage.py shell
>>> exec(open('test_superuser_role.py').read())
"""

from django.contrib.auth.models import User
from employee.models import Employee, EmployeeWorkInformation

print("=" * 60)
print("TESTING SUPERUSER ROLE SETTING")
print("=" * 60)

# Get all superusers
superusers = User.objects.filter(is_superuser=True)
print(f"\nFound {superusers.count()} superuser(s):\n")

for user in superusers:
    print(f"User: {user.username}")
    print(f"  - Email: {user.email}")
    print(f"  - Is Superuser: {user.is_superuser}")
    print(f"  - Date Joined: {user.date_joined}")
    
    # Check if employee profile exists
    try:
        employee = Employee.objects.get(employee_user_id=user)
        print(f"  - Employee Profile: YES")
        print(f"  - Employee Name: {employee.get_full_name()}")
        print(f"  - Role: {employee.role}")
        print(f"  - Role Choices: {dict(Employee.ROLE_CHOICES)}")
        
        # Check work info
        try:
            work_info = employee.employee_work_info
            print(f"  - Work Info: YES")
        except:
            print(f"  - Work Info: NO")
            
    except Employee.DoesNotExist:
        print(f"  - Employee Profile: NO")
        print(f"  - Creating employee profile with admin role...")
        
        employee, created = Employee.objects.get_or_create(
            employee_user_id=user,
            defaults={
                "employee_first_name": user.first_name or user.username,
                "employee_last_name": user.last_name or "",
                "email": user.email or f"{user.username}@example.com",
                "phone": "0000000000",
                "role": "admin",
            }
        )
        print(f"  - Employee Created: {created}")
        print(f"  - Role: {employee.role}")
        
        # Create work info
        work_info, created = EmployeeWorkInformation.objects.get_or_create(employee_id=employee)
        print(f"  - Work Info Created: {created}")
    
    print()

print("=" * 60)
print("TEST COMPLETE")
print("=" * 60)
