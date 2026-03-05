from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from employee.models import Employee, EmployeeBankDetails, EmployeeWorkInformation


class Command(BaseCommand):
    help = "Ensure admin user has an employee profile, work info, and bank details."

    def handle(self, *args, **options):
        admin_user = User.objects.filter(is_superuser=True).first()
        if admin_user:
            employee, _ = Employee.objects.get_or_create(
                employee_user_id=admin_user,
                defaults={
                    "employee_first_name": admin_user.first_name or "Admin",
                    "employee_last_name": admin_user.last_name or "",
                    "email": admin_user.email or "admin@example.com",
                    "phone": "0000000000",
                },
            )
            EmployeeWorkInformation.objects.get_or_create(employee_id=employee)
            EmployeeBankDetails.objects.get_or_create(
                employee_id=employee,
                defaults={
                    "account_number": "0000000000",
                    "ifsc_code": "ADMIN0000",
                    "bank_name": "Admin Bank",
                    "branch": "Admin Branch",
                },
            )
            self.stdout.write(
                self.style.SUCCESS(
                    "Admin employee profile, work info, and bank details ensured."
                )
            )
        else:
            self.stdout.write(self.style.ERROR("No admin user found."))
