from django.contrib.auth.models import Permission, User
from django.test import TestCase
from rest_framework.test import APIClient

from attendance.models import Attendance, AttendanceActivity
from employee.models import Employee, EmployeeWorkInformation
from payroll.models.models import Contract


class EmployeeDeleteAPITest(TestCase):
    def setUp(self):
        # create user with delete permission
        self.user = User.objects.create_user(username="deleter", password="password")
        perm = Permission.objects.get(codename="delete_employee")
        self.user.user_permissions.add(perm)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # create an employee and related objects
        self.employee = Employee.objects.create(
            employee_first_name="Tejash", email="tejash@example.com", phone="11111"
        )
        Attendance.objects.create(
            employee_id=self.employee, attendance_date="2026-02-02"
        )
        AttendanceActivity.objects.create(
            employee_id=self.employee,
            attendance_date="2026-02-02",
            clock_in="15:00",
            clock_out="15:01",
        )
        Contract.objects.create(
            contract_name="Contract",
            employee_id=self.employee,
            contract_start_date="2026-02-02",
        )

    def test_delete_blocked_by_protected(self):
        response = self.client.delete(f"/api/employee/employees/{self.employee.id}/")
        assert response.status_code == 409
        data = response.json()
        assert "blocked" in data

    def test_force_delete_removes_related_and_deletes(self):
        response = self.client.delete(
            f"/api/employee/employees/{self.employee.id}/?force=true"
        )
        # Forced delete should succeed
        assert response.status_code == 204
        # Employee should no longer exist
        assert not Employee.objects.filter(pk=self.employee.pk).exists()

    def test_force_delete_clears_nullable_protected_relations(self):
        manager = self.employee
        subordinate = Employee.objects.create(
            employee_first_name="Sub", email="sub@example.com", phone="22222"
        )
        EmployeeWorkInformation.objects.create(
            employee_id=subordinate, reporting_manager_id=manager
        )

        response = self.client.delete(f"/api/employee/employees/{manager.id}/?force=true")
        assert response.status_code == 204

        subordinate_work_info = EmployeeWorkInformation.objects.get(employee_id=subordinate)
        assert subordinate_work_info.reporting_manager_id is None
