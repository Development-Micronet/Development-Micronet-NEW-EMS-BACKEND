from django.contrib.auth.management.commands.createsuperuser import Command as BaseCommand
from django.contrib.auth.models import User

from employee.models import Employee, EmployeeWorkInformation


class Command(BaseCommand):
    """
    Custom createsuperuser command that automatically creates an Employee profile with admin role.
    """

    def handle(self, *args, **options):
        # Call the parent command to create the superuser
        # The parent's handle method will handle all interactive prompts
        super().handle(*args, **options)
        
        # After the superuser is created, apply our custom logic
        # Get all superusers ordered by creation time to find the most recent one
        latest_superuser = User.objects.filter(is_superuser=True).order_by('-date_joined', '-id').first()
        
        if latest_superuser:
            # Create or get the employee profile with admin role
            employee, created = Employee.objects.get_or_create(
                employee_user_id=latest_superuser,
                defaults={
                    "employee_first_name": latest_superuser.first_name or latest_superuser.username,
                    "employee_last_name": latest_superuser.last_name or "",
                    "email": latest_superuser.email or f"{latest_superuser.username}@example.com",
                    "phone": "0000000000",
                    "role": "admin",  # Explicitly set role to admin
                },
            )
            
            # If employee already exists but doesn't have admin role, update it
            if not created and employee.role != "admin":
                employee.role = "admin"
                employee.save()
            
            # Ensure work information exists
            EmployeeWorkInformation.objects.get_or_create(employee_id=employee)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nEmployee profile created for superuser '{latest_superuser.username}' with Admin role."
                )
            )

        
        return result
