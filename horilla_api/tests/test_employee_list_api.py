from django.contrib.auth.models import Permission, User
from django.test import TestCase
from rest_framework.test import APIClient

from employee.models import Employee


class EmployeeListAPITest(TestCase):
    def setUp(self):
        # Create a user to authenticate requests
        self.user = User.objects.create_user(username="testuser", password="password")
        add_employee_perm = Permission.objects.get(codename="add_employee")
        self.user.user_permissions.add(add_employee_perm)
        # Create multiple employees
        Employee.objects.create(
            employee_first_name="Alice", email="alice@example.com", phone="111111"
        )
        Employee.objects.create(
            employee_first_name="Bob", email="bob@example.com", phone="222222"
        )
        Employee.objects.create(
            employee_first_name="Charlie", email="charlie@example.com", phone="333333"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_list_returns_all_employees_for_authenticated_user(self):
        response = self.client.get("/api/employee/list/employees/")
        assert response.status_code == 200
        data = response.json()
        # Expect paginated response with count equal to 3
        assert data.get("count") == 3
        assert len(data.get("results", [])) == 3

    def test_post_can_create_admin_employee_without_duplicate_employee_error(self):
        payload = {
            "username": "admin-creator",
            "password": "Secret123",
            "employee_first_name": "Admin",
            "employee_last_name": "User",
            "email": "admin.user@example.com",
            "phone": "9999999999",
            "role": "admin",
        }

        response = self.client.post(
            "/api/employee/list/employees/", payload, format="json"
        )

        assert response.status_code == 201, response.content
        created_employee = Employee.objects.get(email=payload["email"])
        assert created_employee.role == "admin"
        assert created_employee.employee_user_id is not None
        assert created_employee.employee_user_id.is_superuser is True
        assert Employee.objects.filter(employee_user_id=created_employee.employee_user_id).count() == 1
