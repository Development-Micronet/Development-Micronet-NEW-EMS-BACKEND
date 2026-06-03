from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.db.models import ProtectedError
from django.test import TestCase
from rest_framework.test import APIClient

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
        Contract.objects.create(
            contract_name="Contract",
            employee_id=self.employee,
            contract_start_date=date(2026, 2, 2),
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

    def test_force_delete_retries_after_protected_error_on_employee_delete(self):
        manager = self.employee
        subordinate = Employee.objects.create(
            employee_first_name="Sub", email="sub2@example.com", phone="33333"
        )
        subordinate_work_info = EmployeeWorkInformation.objects.create(
            employee_id=subordinate, reporting_manager_id=manager
        )

        original_delete = Employee.delete
        state = {"raised": False}

        def flaky_delete(instance, *args, **kwargs):
            if instance.pk == manager.pk and not state["raised"]:
                state["raised"] = True
                raise ProtectedError("retryable protected relation", [subordinate_work_info])
            return original_delete(instance, *args, **kwargs)

        with patch.object(Employee, "delete", autospec=True, side_effect=flaky_delete):
            response = self.client.delete(
                f"/api/employee/employees/{manager.id}/?force=true"
            )

        assert response.status_code == 204
        subordinate_work_info.refresh_from_db()
        assert subordinate_work_info.reporting_manager_id is None
        assert not Employee.objects.filter(pk=manager.pk).exists()
