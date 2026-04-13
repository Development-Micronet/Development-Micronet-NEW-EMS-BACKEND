from datetime import timedelta
from types import SimpleNamespace

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from attendance.models import Attendance, BatchAttendance, WorkRecords
from base.models import EmployeeShift, EmployeeShiftDay, WorkType
from employee.models import Employee, EmployeeWorkInformation
from horilla.horilla_middlewares import _thread_locals
from notifications.models import Notification


class AttendanceRequestAPITest(TestCase):
    def setUp(self):
        if hasattr(_thread_locals, "request"):
            delattr(_thread_locals, "request")
        self.today = timezone.localdate()
        for offset in range(5):
            EmployeeShiftDay.objects.get_or_create(
                day=(self.today - timedelta(days=offset)).strftime("%A").lower()
            )
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
        self.approver_user = User.objects.create_user(
            username="attendance_request_approver",
            password="password",
        )
        self.approver_user.user_permissions.add(
            Permission.objects.get(codename="change_attendance")
        )
        self.approver_employee = Employee.objects.create(
            employee_user_id=self.approver_user,
            employee_first_name="Arun",
            employee_last_name="Nair",
            email="arun.nair@example.com",
            phone="9999999912",
        )
        EmployeeWorkInformation.objects.filter(employee_id=self.employee).update(
            reporting_manager_id=self.approver_employee
        )

    def _attach_online_request_context(self):
        _thread_locals.request = SimpleNamespace(
            session={},
            working_employees=None,
        )

    def _build_payload(self, attendance_date, include_clock_out=True):
        payload = {
            "employee_id": str(self.user.id),
            "attendance_date": attendance_date.isoformat(),
            "shift_id": self.shift.id,
            "work_type_id": self.work_type.id,
            "attendance_clock_in_date": attendance_date.isoformat(),
            "attendance_clock_in": "09:00",
            "attendance_worked_hour": "00:00",
            "minimum_hour": "08:00",
            "request_description": "Missed punch",
        }
        if include_clock_out:
            payload["attendance_clock_out_date"] = attendance_date.isoformat()
            payload["attendance_clock_out"] = "10:00"
            payload["attendance_worked_hour"] = "09:00"
        return payload

    def tearDown(self):
        if hasattr(_thread_locals, "request"):
            delattr(_thread_locals, "request")

    def test_create_attendance_request_defaults_to_authenticated_employee(self):
        payload = {
            "attendance_date": self.today.isoformat(),
            "shift_id": self.shift.id,
            "attendance_clock_in_date": self.today.isoformat(),
            "attendance_clock_in": "09:00",
            "attendance_worked_hour": "00:00",
            "minimum_hour": "08:00",
            "request_description": "Missed punch",
        }

        response = self.client.post(
            "/api/attendance/attendance-request/",
            payload,
            format="json",
        )

        assert response.status_code == 200
        assert Attendance.objects.filter(
            employee_id=self.employee,
            attendance_date=self.today,
        ).exists()

    def test_create_attendance_request_accepts_reference_names_and_dynamic_batch(self):
        payload = {
            "employee_id": str(self.user.id),
            "attendance_date": self.today.isoformat(),
            "shift_id": "Regular Shift",
            "work_type_id": "Work From Home",
            "attendance_clock_in_date": self.today.isoformat(),
            "attendance_clock_in": "09:00",
            "attendance_worked_hour": "00:00",
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

    def test_create_attendance_request_accepts_past_three_days(self):
        payload = self._build_payload(self.today - timedelta(days=3))

        response = self.client.post(
            "/api/attendance/attendance-request/",
            payload,
            format="json",
        )

        assert response.status_code == 200
        assert Attendance.objects.filter(
            employee_id=self.employee,
            attendance_date=self.today - timedelta(days=3),
        ).exists()

    def test_create_attendance_request_notifies_reporting_manager(self):
        response = self.client.post(
            "/api/attendance/attendance-request/",
            self._build_payload(self.today),
            format="json",
        )

        assert response.status_code == 200
        notification = Notification.objects.filter(
            recipient=self.approver_user,
        ).first()

        assert notification is not None
        assert "attendance request" in notification.verb.lower()
        assert str(self.today) in notification.verb

    def test_create_attendance_request_rejects_older_than_past_three_days(self):
        payload = self._build_payload(self.today - timedelta(days=4))

        response = self.client.post(
            "/api/attendance/attendance-request/",
            payload,
            format="json",
        )

        assert response.status_code == 400
        assert "attendance_date" in response.json()

    def test_pending_create_request_stays_offline_and_absent_until_approved(self):
        response = self.client.post(
            "/api/attendance/attendance-request/",
            self._build_payload(self.today, include_clock_out=False),
            format="json",
        )

        assert response.status_code == 200
        attendance = Attendance.objects.get(
            employee_id=self.employee,
            attendance_date=self.today,
        )
        work_record = WorkRecords.objects.get(
            employee_id=self.employee,
            date=self.today,
        )

        assert attendance.request_type == "create_request"
        assert attendance.is_validate_request is True
        assert attendance.attendance_validated is False
        assert work_record.work_record_type == "ABS"
        assert str(work_record.message) == "Absent"

        self._attach_online_request_context()
        assert self.employee.check_online() is False

        self.client.force_authenticate(user=self.approver_user)
        approve_response = self.client.put(
            f"/api/attendance/attendance-request-approve/{attendance.id}",
            format="json",
        )

        assert approve_response.status_code == 200

        attendance.refresh_from_db()
        work_record.refresh_from_db()
        self._attach_online_request_context()

        assert attendance.attendance_validated is True
        assert attendance.is_validate_request is False
        assert work_record.work_record_type == "FDP"
        assert str(work_record.message) == "Currently working"
        assert self.employee.check_online() is True
        assert Notification.objects.filter(recipient=self.user).filter(
            verb__icontains="attendance request"
        ).filter(verb__icontains="validated").exists()
