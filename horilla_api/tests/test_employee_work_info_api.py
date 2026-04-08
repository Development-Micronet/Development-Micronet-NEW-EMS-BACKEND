from django.contrib.auth.models import Permission, User
from django.test import TestCase
from rest_framework.test import APIClient

from employee.models import Employee, EmployeeWorkInformation


class EmployeeWorkInfoAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_employee_create_auto_creates_work_info(self):
        creator = User.objects.create_user(username="creator", password="password")
        creator.user_permissions.add(Permission.objects.get(codename="add_employee"))
        self.client.force_authenticate(user=creator)

        payload = {
            "username": "newemployee",
            "password": "Secret123",
            "employee_first_name": "New",
            "employee_last_name": "Employee",
            "email": "newemployee@example.com",
            "phone": "9999999999",
            "role": "user",
        }

        response = self.client.post(
            "/api/employee/list/employees/", payload, format="json"
        )

        self.assertEqual(response.status_code, 201, response.content)
        employee = Employee.objects.get(email=payload["email"])
        self.assertTrue(
            EmployeeWorkInformation.objects.filter(employee_id=employee).exists()
        )

    def test_admin_can_update_employee_work_info_without_existing_record(self):
        admin_user = User.objects.create_superuser(
            username="rootadmin",
            password="password",
            email="rootadmin@example.com",
        )
        employee = Employee.objects.create(
            employee_first_name="Target",
            email="target@example.com",
            phone="1111111111",
        )

        self.client.force_authenticate(user=admin_user)
        response = self.client.put(
            f"/api/employee/employee-work-information/{employee.id}/",
            {"Work_Location_Label": "HQ"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        work_info = EmployeeWorkInformation.objects.get(employee_id=employee)
        self.assertEqual(work_info.Work_Location_Label, "HQ")

    def test_employee_can_update_own_work_info(self):
        employee_user = User.objects.create_user(
            username="employeeuser",
            password="password",
            email="employeeuser@example.com",
        )
        Employee.objects.create(
            employee_user_id=employee_user,
            employee_first_name="Employee",
            employee_last_name="User",
            email="employeeuser@example.com",
            phone="2222222222",
            role="user",
        )

        self.client.force_authenticate(user=employee_user)
        response = self.client.put(
            "/api/employee/work-info/",
            {"Work_Email_Label": "employee.work@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        work_info = EmployeeWorkInformation.objects.get(
            employee_id=employee_user.employee_get
        )
        self.assertEqual(work_info.Work_Email_Label, "employee.work@example.com")
