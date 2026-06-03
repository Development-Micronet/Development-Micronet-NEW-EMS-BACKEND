from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from employee.models import Employee, EmployeeWorkInformation


class Command(BaseCommand):
    help = "Ensure admin user has an employee profile and work info with admin role."

    def handle(self, *args, **options):
        admin_user = User.objects.filter(is_superuser=True).first()
        if admin_user:
            employee, created = Employee.objects.get_or_create(
                employee_user_id=admin_user,
                defaults={
                    "employee_first_name": admin_user.first_name or "Admin",
                    "employee_last_name": admin_user.last_name or "",
                    "email": admin_user.email or "admin@example.com",
                    "phone": "0000000000",
                    "role": "admin",  # Set role to admin for superuser
                },
            )
            # If employee already exists but doesn't have admin role, update it
            if not created and employee.role != "admin":
                employee.role = "admin"
                employee.save()
            
            EmployeeWorkInformation.objects.get_or_create(employee_id=employee)
            self.stdout.write(
                self.style.SUCCESS("Admin employee profile and work info ensured with admin role.")
            )
        else:
            self.stdout.write(self.style.ERROR("No admin user found."))

