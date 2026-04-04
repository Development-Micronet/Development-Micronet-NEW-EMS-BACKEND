from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from attendance.models import BatchAttendance
from base.models import EmployeeShift, WorkType
from employee.models import Employee, EmployeeWorkInformation
from horilla.horilla_middlewares import _thread_locals


class AttendanceRequestAPITest(TestCase):
    def setUp(self):
        if hasattr(_thread_locals, "request"):
            delattr(_thread_locals, "request")
        self.user = User.objects.create_user(
            username="attendance_request_user",
            password="password",
        )
        self.employee = Employee.objects.create(
            employee_user_id=self.user,
            employee_first_name="Neha",
            employee_last_name="Verma",
            email="neha.verma@example.com",
            phone="9999999911",
        )
        self.shift = EmployeeShift.objects.create(employee_shift="General Shift")
        self.work_type = WorkType.objects.create(work_type="General Work Type")
        EmployeeWorkInformation.objects.update_or_create(
            employee_id=self.employee,
            defaults={
                "shift_id": self.shift,
                "work_type_id": self.work_type,
            },
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        if hasattr(_thread_locals, "request"):
            delattr(_thread_locals, "request")

    def test_create_attendance_request_missing_employee_id_returns_400(self):
        payload = {
            "attendance_date": "2026-04-04",
            "shift_id": self.shift.id,
            "attendance_clock_in_date": "2026-04-04",
            "attendance_clock_in": "09:00",
            "attendance_clock_out_date": "2026-04-04",
            "attendance_clock_out": "18:00",
            "attendance_worked_hour": "09:00",
            "minimum_hour": "08:00",
            "request_description": "Missed punch",
        }

        response = self.client.post(
            "/api/attendance/attendance-request/",
            payload,
            format="json",
        )

        assert response.status_code == 400
        assert "employee_id" in response.json()

    def test_create_attendance_request_accepts_reference_names_and_dynamic_batch(self):
        payload = {
            "employee_id": str(self.user.id),
            "attendance_date": "2026-04-03",
            "shift_id": "Regular Shift",
            "work_type_id": "Work From Home",
            "attendance_clock_in_date": "2026-04-03",
            "attendance_clock_in": "09:00",
            "attendance_clock_out_date": "2026-04-03",
            "attendance_clock_out": "18:00",
            "attendance_worked_hour": "09:00",
            "minimum_hour": "08:00",
            "request_description": "Missed punch",
            "batch_attendance_id": "dynamic_create",
        }

        response = self.client.post(
            "/api/attendance/attendance-request/",
            payload,
            format="json",
        )

        assert response.status_code == 200
        assert EmployeeShift.objects.filter(employee_shift="Regular Shift").exists()
        assert WorkType.objects.filter(work_type="Work From Home").exists()
        assert BatchAttendance.objects.filter(title="Dynamic Create").exists()
