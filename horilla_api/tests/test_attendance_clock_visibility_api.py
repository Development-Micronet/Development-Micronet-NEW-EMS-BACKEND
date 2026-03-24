from types import SimpleNamespace

from django.db.models import Q
from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from attendance.models import Attendance, WorkRecords
from attendance.signals import sync_work_record_from_attendance
from base.models import EmployeeShiftDay
from employee.models import Employee
from horilla.horilla_middlewares import _thread_locals


class AttendanceClockVisibilityAPITest(TestCase):
    def setUp(self):
        if hasattr(_thread_locals, "request"):
            delattr(_thread_locals, "request")
        if hasattr(WorkRecords, "company_filter"):
            delattr(WorkRecords, "company_filter")
        EmployeeShiftDay.objects.get_or_create(day=timezone.localdate().strftime("%A").lower())
        self.user = User.objects.create_user(
            username="attendance_tester", password="password"
        )
        self.employee = Employee.objects.create(
            employee_user_id=self.user,
            employee_first_name="Ava",
            employee_last_name="Sharma",
            email="ava.sharma@example.com",
            phone="9999999998",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        if hasattr(WorkRecords, "company_filter"):
            delattr(WorkRecords, "company_filter")
        if hasattr(_thread_locals, "request"):
            delattr(_thread_locals, "request")

    def test_work_record_stays_visible_in_db_and_api_after_check_in_and_check_out(self):
        clock_in_response = self.client.post("/api/attendance/clock-in/", format="json")
        assert clock_in_response.status_code == 200

        WorkRecords.company_filter = Q(employee_id__employee_work_info__company_id=999999)
        _thread_locals.request = SimpleNamespace(session={"selected_company": "1"})

        after_check_in = self.client.get(
            "/api/attendance/attendance/work-records/",
            {"month": timezone.localdate().strftime("%Y-%m")},
            format="json",
        )
        assert after_check_in.status_code == 200
        assert len(after_check_in.json()) >= 1
        today_record = next(
            (
                row
                for row in after_check_in.json()
                if row["employee_id"] == self.employee.id
                and row["date"] == str(timezone.localdate())
            ),
            None,
        )
        assert today_record is not None
        assert today_record["is_attendance_record"] is True
        assert today_record["attendance_clock_in"] is not None
        assert today_record["work_record_type"] == "FDP"
        assert today_record["status"] == "present"

        stale_work_record = WorkRecords.objects.get(
            employee_id=self.employee, date=timezone.localdate()
        )
        stale_work_record.work_record_type = "ABS"
        stale_work_record.message = "Absent"
        stale_work_record.is_attendance_record = False
        stale_work_record.attendance_id = None
        stale_work_record.save()

        repaired_response = self.client.get(
            "/api/attendance/attendance/work-records/",
            {"month": timezone.localdate().strftime("%Y-%m")},
            format="json",
        )
        assert repaired_response.status_code == 200
        repaired_today_record = next(
            (
                row
                for row in repaired_response.json()
                if row["employee_id"] == self.employee.id
                and row["date"] == str(timezone.localdate())
            ),
            None,
        )
        assert repaired_today_record is not None
        assert repaired_today_record["work_record_type"] == "FDP"
        assert repaired_today_record["attendance_clock_in"] is not None
        assert repaired_today_record["status"] == "present"

        attendance_list_response = self.client.get(
            "/api/attendance/attendance/",
            {"attendance_date": timezone.localdate().strftime("%Y-%m-%d")},
            format="json",
        )
        assert attendance_list_response.status_code == 200
        attendance_today_record = next(
            (
                row
                for row in attendance_list_response.json()["results"]
                if row["employee_id"] == self.employee.id
                and row["date"] == str(timezone.localdate())
            ),
            None,
        )
        assert attendance_today_record is not None
        assert attendance_today_record["status"] == "present"
        assert attendance_today_record["attendance_date"] == str(timezone.localdate())
        assert attendance_today_record["work_record_type"] == "FDP"

        clock_out_response = self.client.post("/api/attendance/clock-out/", format="json")
        assert clock_out_response.status_code == 200

        after_check_out = self.client.get(
            "/api/attendance/attendance/work-records/",
            {"month": timezone.localdate().strftime("%Y-%m")},
            format="json",
        )
        assert after_check_out.status_code == 200
        today_record_after_checkout = next(
            (
                row
                for row in after_check_out.json()
                if row["employee_id"] == self.employee.id
                and row["date"] == str(timezone.localdate())
            ),
            None,
        )
        assert today_record_after_checkout is not None
        assert today_record_after_checkout["attendance_clock_out"] is not None
        assert today_record_after_checkout["work_record_type"] == "FDP"
        assert today_record_after_checkout["status"] == "present"

        self.employee.refresh_from_db()
        assert self.employee.is_active is True

        attendance = Attendance.objects.get(
            employee_id=self.employee, attendance_date=timezone.localdate()
        )
        assert attendance.attendance_validated is True
        assert attendance.attendance_clock_out is not None

        work_record = WorkRecords.objects.filter(
            employee_id__is_active=True,
            employee_id=self.employee,
            date=timezone.localdate(),
        ).first()
        assert work_record is not None
        assert work_record.is_attendance_record is True
        assert work_record.work_record_type == "FDP"

        if hasattr(WorkRecords, "company_filter"):
            delattr(WorkRecords, "company_filter")
        if hasattr(_thread_locals, "request"):
            delattr(_thread_locals, "request")

    def test_permission_based_admin_can_see_accessible_work_records(self):
        admin_user = User.objects.create_user(
            username="attendance_admin", password="password"
        )
        admin_user.user_permissions.add(
            Permission.objects.get(codename="view_attendance")
        )
        Employee.objects.create(
            employee_user_id=admin_user,
            employee_first_name="Admin",
            employee_last_name="Viewer",
            email="admin.viewer@example.com",
            phone="9999999997",
        )

        other_user = User.objects.create_user(
            username="attendance_other", password="password"
        )
        other_employee = Employee.objects.create(
            employee_user_id=other_user,
            employee_first_name="Visible",
            employee_last_name="Employee",
            email="visible.employee@example.com",
            phone="9999999996",
        )
        attendance = Attendance.objects.create(
            employee_id=other_employee,
            attendance_date=timezone.localdate(),
            attendance_clock_in=timezone.localtime().time().replace(microsecond=0),
            attendance_clock_in_date=timezone.localdate(),
            attendance_validated=True,
            minimum_hour="00:00",
        )
        sync_work_record_from_attendance(attendance)

        self.client.force_authenticate(user=admin_user)
        response = self.client.get(
            "/api/attendance/attendance/work-records/",
            {"month": timezone.localdate().strftime("%Y-%m")},
            format="json",
        )
        assert response.status_code == 200
        assert any(
            row["employee_id"] == other_employee.id
            and row["date"] == str(timezone.localdate())
            and row["work_record_type"] == "FDP"
            and row["status"] == "present"
            for row in response.json()
        )
