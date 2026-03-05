from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from employee.models import Employee


class EmployeeListAPITest(TestCase):
    def setUp(self):
        # Create a user to authenticate requests
        self.user = User.objects.create_user(username="testuser", password="password")
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
