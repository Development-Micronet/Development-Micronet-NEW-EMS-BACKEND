from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission, User
from django.db.models import Q
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from attendance.models import Attendance, AttendanceActivity, WorkRecords
from attendance.signals import sync_work_record_from_attendance
from base.models import EmployeeShiftDay
from employee.models import Employee
from horilla.horilla_middlewares import _thread_locals


class AttendanceClockVisibilityAPITest(TestCase):
    def _aware_datetime(self, hour, minute=0, current_date=None):
        current_date = current_date or timezone.localdate()
        return timezone.make_aware(
            datetime(
                current_date.year,
                current_date.month,
                current_date.day,
                hour,
                minute,
            ),
            timezone.get_current_timezone(),
        )

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
        if hasattr(AttendanceActivity, "company_filter"):
            delattr(AttendanceActivity, "company_filter")
        if hasattr(_thread_locals, "request"):
            delattr(_thread_locals, "request")

    def test_work_record_stays_visible_in_db_and_api_after_check_in_and_check_out(self):
        attendance_date = timezone.localdate()

        with patch(
            "django.utils.timezone.now",
            return_value=self._aware_datetime(9, 15, attendance_date),
        ):
            clock_in_response = self.client.post(
                "/api/attendance/clock-in/", format="json"
            )
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

        with patch(
            "django.utils.timezone.now",
            return_value=self._aware_datetime(18, 45, attendance_date),
        ):
            clock_out_response = self.client.post(
                "/api/attendance/clock-out/", format="json"
            )
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

    def test_multiple_same_day_clock_in_out_excludes_breaks_and_updates_status(self):
        attendance_date = timezone.localdate()

        with patch(
            "django.utils.timezone.now",
            return_value=self._aware_datetime(9, 0, attendance_date),
        ):
            first_clock_in = self.client.post("/api/attendance/clock-in/", format="json")
        assert first_clock_in.status_code == 200
        assert first_clock_in.json()["status"] == "online"

        online_response = self.client.get(
            "/api/attendance/attendance/online-offline/",
            format="json",
        )
        assert online_response.status_code == 200
        online_status = next(
            (
                row
                for row in online_response.json()["employees"]
                if row["user_id"] == self.user.id
            ),
            None,
        )
        assert online_status is not None
        assert online_status["status"] == "online"
        assert online_status["is_online"] is True

        with patch(
            "django.utils.timezone.now",
            return_value=self._aware_datetime(12, 0, attendance_date),
        ):
            first_clock_out = self.client.post(
                "/api/attendance/clock-out/",
                format="json",
            )
        assert first_clock_out.status_code == 200
        assert first_clock_out.json()["status"] == "offline"

        attendance = Attendance.objects.get(
            employee_id=self.employee,
            attendance_date=attendance_date,
        )
        attendance.refresh_from_db()
        assert attendance.attendance_worked_hour == "03:00:00"
        assert attendance.attendance_clock_out.strftime("%H:%M") == "12:00"

        with patch(
            "django.utils.timezone.now",
            return_value=self._aware_datetime(13, 0, attendance_date),
        ):
            second_clock_in = self.client.post(
                "/api/attendance/clock-in/",
                format="json",
            )
        assert second_clock_in.status_code == 200
        assert second_clock_in.json()["status"] == "online"

        attendance.refresh_from_db()
        assert attendance.attendance_clock_out is None

        activities = list(
            AttendanceActivity.objects.filter(
                employee_id=self.employee,
                attendance_date=attendance_date,
            ).order_by("clock_in_date", "clock_in", "id")
        )
        assert len(activities) == 2
        assert activities[0].clock_in.strftime("%H:%M") == "09:00"
        assert activities[0].clock_out.strftime("%H:%M") == "12:00"
        assert activities[1].clock_in.strftime("%H:%M") == "13:00"
        assert activities[1].clock_out is None

        online_response = self.client.get(
            "/api/attendance/attendance/online-offline/",
            format="json",
        )
        assert online_response.status_code == 200
        online_status = next(
            (
                row
                for row in online_response.json()["employees"]
                if row["user_id"] == self.user.id
            ),
            None,
        )
        assert online_status is not None
        assert online_status["status"] == "online"
        assert online_status["is_online"] is True

        with patch(
            "django.utils.timezone.now",
            return_value=self._aware_datetime(18, 0, attendance_date),
        ):
            second_clock_out = self.client.post(
                "/api/attendance/clock-out/",
                format="json",
            )
        assert second_clock_out.status_code == 200
        assert second_clock_out.json()["status"] == "offline"

        attendance.refresh_from_db()
        activities = list(
            AttendanceActivity.objects.filter(
                employee_id=self.employee,
                attendance_date=attendance_date,
            ).order_by("clock_in_date", "clock_in", "id")
        )
        assert len(activities) == 2
        assert activities[1].clock_out.strftime("%H:%M") == "18:00"
        assert attendance.attendance_clock_out.strftime("%H:%M") == "18:00"
        assert attendance.attendance_worked_hour == "08:00:00"

        offline_response = self.client.get(
            "/api/attendance/attendance/online-offline/",
            format="json",
        )
        assert offline_response.status_code == 200
        offline_status = next(
            (
                row
                for row in offline_response.json()["employees"]
                if row["user_id"] == self.user.id
            ),
            None,
        )
        assert offline_status is not None
        assert offline_status["status"] == "offline"
        assert offline_status["is_online"] is False

    def test_late_clock_ins_stay_visible_in_non_validated_attendance_list(self):
        attendance_date = timezone.localdate()
        admin_user = User.objects.create_user(
            username="attendance_admin", password="password"
        )
        admin_user.user_permissions.add(
            Permission.objects.get(codename="view_attendance")
        )
        admin_employee = Employee.objects.create(
            employee_user_id=admin_user,
            employee_first_name="Admin",
            employee_last_name="Late",
            email="admin.late@example.com",
            phone="9999999997",
        )

        self.client.force_authenticate(user=self.user)
        with patch(
            "django.utils.timezone.now",
            return_value=self._aware_datetime(11, 0, attendance_date),
        ):
            employee_clock_in = self.client.post(
                "/api/attendance/clock-in/", format="json"
            )
        assert employee_clock_in.status_code == 200
        with patch(
            "django.utils.timezone.now",
            return_value=self._aware_datetime(19, 0, attendance_date),
        ):
            employee_clock_out = self.client.post(
                "/api/attendance/clock-out/", format="json"
            )
        assert employee_clock_out.status_code == 200

        employee_attendance = Attendance.objects.get(
            employee_id=self.employee, attendance_date=attendance_date
        )
        assert employee_attendance.attendance_validated is False

        employee_results_response = self.client.get(
            "/api/attendance/attendance/",
            {
                "attendance_date": attendance_date.strftime("%Y-%m-%d"),
                "validated": "false",
            },
            format="json",
        )
        assert employee_results_response.status_code == 200
        employee_result_ids = {
            row["employee_id"] for row in employee_results_response.json()["results"]
        }
        assert self.employee.id in employee_result_ids

        self.client.force_authenticate(user=admin_user)
        with patch(
            "django.utils.timezone.now",
            return_value=self._aware_datetime(11, 15, attendance_date),
        ):
            admin_clock_in = self.client.post("/api/attendance/clock-in/", format="json")
        assert admin_clock_in.status_code == 200
        with patch(
            "django.utils.timezone.now",
            return_value=self._aware_datetime(19, 15, attendance_date),
        ):
            admin_clock_out = self.client.post(
                "/api/attendance/clock-out/", format="json"
            )
        assert admin_clock_out.status_code == 200

        admin_attendance = Attendance.objects.get(
            employee_id=admin_employee, attendance_date=attendance_date
        )
        assert admin_attendance.attendance_validated is False

        validate_list_response = self.client.get(
            "/api/attendance/attendance/",
            {
                "attendance_date": attendance_date.strftime("%Y-%m-%d"),
                "validated": "false",
            },
            format="json",
        )
        assert validate_list_response.status_code == 200
        validate_result_ids = {
            row["employee_id"] for row in validate_list_response.json()["results"]
        }
        assert self.employee.id in validate_result_ids
        assert admin_employee.id in validate_result_ids

        validated_response = self.client.get(
            "/api/attendance/attendance/",
            {
                "attendance_date": attendance_date.strftime("%Y-%m-%d"),
                "validated": "true",
            },
            format="json",
        )
        assert validated_response.status_code == 200
        validated_ids = {
            row["employee_id"] for row in validated_response.json()["results"]
        }
        assert self.employee.id not in validated_ids
        assert admin_employee.id not in validated_ids

    def test_on_time_clock_ins_stay_visible_in_validated_attendance_list(self):
        attendance_date = timezone.localdate()
        admin_user = User.objects.create_user(
            username="attendance_admin_ontime", password="password"
        )
        admin_employee = Employee.objects.create(
            employee_user_id=admin_user,
            employee_first_name="Admin",
            employee_last_name="OnTime",
            email="admin.ontime@example.com",
            phone="9999999985",
            role="admin",
        )

        self.client.force_authenticate(user=self.user)
        with patch(
            "django.utils.timezone.now",
            return_value=self._aware_datetime(10, 15, attendance_date),
        ):
            employee_clock_in = self.client.post(
                "/api/attendance/clock-in/", format="json"
            )
        assert employee_clock_in.status_code == 200
        with patch(
            "django.utils.timezone.now",
            return_value=self._aware_datetime(18, 0, attendance_date),
        ):
            employee_clock_out = self.client.post(
                "/api/attendance/clock-out/", format="json"
            )
        assert employee_clock_out.status_code == 200

        self.client.force_authenticate(user=admin_user)
        with patch(
            "django.utils.timezone.now",
            return_value=self._aware_datetime(10, 30, attendance_date),
        ):
            admin_clock_in = self.client.post("/api/attendance/clock-in/", format="json")
        assert admin_clock_in.status_code == 200
        with patch(
            "django.utils.timezone.now",
            return_value=self._aware_datetime(18, 15, attendance_date),
        ):
            admin_clock_out = self.client.post(
                "/api/attendance/clock-out/", format="json"
            )
        assert admin_clock_out.status_code == 200

        validated_response = self.client.get(
            "/api/attendance/attendance/",
            {
                "attendance_date": attendance_date.strftime("%Y-%m-%d"),
                "validated": "true",
            },
            format="json",
        )
        assert validated_response.status_code == 200
        validated_ids = {
            row["employee_id"] for row in validated_response.json()["results"]
        }
        assert self.employee.id in validated_ids
        assert admin_employee.id in validated_ids

        non_validated_response = self.client.get(
            "/api/attendance/attendance/",
            {
                "attendance_date": attendance_date.strftime("%Y-%m-%d"),
                "validated": "false",
            },
            format="json",
        )
        assert non_validated_response.status_code == 200
        non_validated_ids = {
            row["employee_id"] for row in non_validated_response.json()["results"]
        }
        assert self.employee.id not in non_validated_ids
        assert admin_employee.id not in non_validated_ids

    def test_patch_validate_moves_attendance_between_validated_lists(self):
        attendance_date = timezone.localdate()

        self.client.force_authenticate(user=self.user)
        with patch(
            "django.utils.timezone.now",
            return_value=self._aware_datetime(11, 0, attendance_date),
        ):
            clock_in_response = self.client.post(
                "/api/attendance/clock-in/", format="json"
            )
        assert clock_in_response.status_code == 200
        with patch(
            "django.utils.timezone.now",
            return_value=self._aware_datetime(19, 0, attendance_date),
        ):
            clock_out_response = self.client.post(
                "/api/attendance/clock-out/", format="json"
            )
        assert clock_out_response.status_code == 200

        attendance = Attendance.objects.get(
            employee_id=self.employee, attendance_date=attendance_date
        )
        assert attendance.attendance_validated is False

        before_response = self.client.get(
            "/api/attendance/attendance/",
            {
                "attendance_date": attendance_date.strftime("%Y-%m-%d"),
                "validated": "false",
            },
            format="json",
        )
        assert before_response.status_code == 200
        before_ids = {row["id"] for row in before_response.json()["results"]}
        assert attendance.id in before_ids

        validate_response = self.client.patch(
            f"/api/attendance/attendance-validate/{attendance.id}",
            format="json",
        )
        assert validate_response.status_code == 200

        attendance.refresh_from_db()
        assert attendance.attendance_validated is True

        validated_response = self.client.get(
            "/api/attendance/attendance/",
            {
                "attendance_date": attendance_date.strftime("%Y-%m-%d"),
                "validated": "true",
            },
            format="json",
        )
        assert validated_response.status_code == 200
        validated_ids = {row["id"] for row in validated_response.json()["results"]}
        assert attendance.id in validated_ids

        non_validated_response = self.client.get(
            "/api/attendance/attendance/",
            {
                "attendance_date": attendance_date.strftime("%Y-%m-%d"),
                "validated": "false",
            },
            format="json",
        )
        assert non_validated_response.status_code == 200
        non_validated_ids = {
            row["id"] for row in non_validated_response.json()["results"]
        }
        assert attendance.id not in non_validated_ids

    def test_bulk_patch_validate_moves_attendances_between_validated_lists(self):
        attendance_date = timezone.localdate()
        admin_user = User.objects.create_user(
            username="attendance_bulk_admin", password="password"
        )
        admin_user.user_permissions.add(
            Permission.objects.get(codename="view_attendance")
        )
        admin_employee = Employee.objects.create(
            employee_user_id=admin_user,
            employee_first_name="Admin",
            employee_last_name="Bulk",
            email="admin.bulk@example.com",
            phone="9999999975",
        )

        second_user = User.objects.create_user(
            username="attendance_bulk_target", password="password"
        )
        second_employee = Employee.objects.create(
            employee_user_id=second_user,
            employee_first_name="Riya",
            employee_last_name="Bulk",
            email="riya.bulk@example.com",
            phone="9999999974",
        )

        self.client.force_authenticate(user=self.user)
        with patch(
            "django.utils.timezone.now",
            return_value=self._aware_datetime(11, 5, attendance_date),
        ):
            self.client.post("/api/attendance/clock-in/", format="json")
        with patch(
            "django.utils.timezone.now",
            return_value=self._aware_datetime(19, 5, attendance_date),
        ):
            self.client.post("/api/attendance/clock-out/", format="json")

        self.client.force_authenticate(user=second_user)
        with patch(
            "django.utils.timezone.now",
            return_value=self._aware_datetime(11, 10, attendance_date),
        ):
            self.client.post("/api/attendance/clock-in/", format="json")
        with patch(
            "django.utils.timezone.now",
            return_value=self._aware_datetime(19, 10, attendance_date),
        ):
            self.client.post("/api/attendance/clock-out/", format="json")

        attendance_ids = list(
            Attendance.objects.filter(
                employee_id__in=[self.employee, second_employee],
                attendance_date=attendance_date,
            ).values_list("id", flat=True)
        )
        assert len(attendance_ids) == 2
        assert (
            Attendance.objects.filter(
                id__in=attendance_ids, attendance_validated=False
            ).count()
            == 2
        )

        self.client.force_authenticate(user=admin_user)

        before_response = self.client.get(
            "/api/attendance/attendance/",
            {
                "attendance_date": attendance_date.strftime("%Y-%m-%d"),
                "validated": "false",
            },
            format="json",
        )
        assert before_response.status_code == 200
        before_ids = {row["id"] for row in before_response.json()["results"]}
        assert set(attendance_ids).issubset(before_ids)

        bulk_validate_response = self.client.patch(
            "/api/attendance/attendance/bulk-validate/",
            {"ids": attendance_ids},
            format="json",
        )
        assert bulk_validate_response.status_code == 200
        assert bulk_validate_response.json()["validated"] == 2

        assert (
            Attendance.objects.filter(
                id__in=attendance_ids, attendance_validated=True
            ).count()
            == 2
        )

        validated_response = self.client.get(
            "/api/attendance/attendance/",
            {
                "attendance_date": attendance_date.strftime("%Y-%m-%d"),
                "validated": "true",
            },
            format="json",
        )
        assert validated_response.status_code == 200
        validated_ids = {row["id"] for row in validated_response.json()["results"]}
        assert set(attendance_ids).issubset(validated_ids)
        assert admin_employee.id not in {
            row["employee_id"] for row in validated_response.json()["results"]
        }

        non_validated_response = self.client.get(
            "/api/attendance/attendance/",
            {
                "attendance_date": attendance_date.strftime("%Y-%m-%d"),
                "validated": "false",
            },
            format="json",
        )
        assert non_validated_response.status_code == 200
        non_validated_ids = {
            row["id"] for row in non_validated_response.json()["results"]
        }
        assert set(attendance_ids).isdisjoint(non_validated_ids)

    def test_permission_based_admin_can_see_accessible_work_records(self):
        admin_user = User.objects.create_user(
            username="attendance_admin", password="password"
        )
        Employee.objects.create(
            employee_user_id=admin_user,
            employee_first_name="Admin",
            employee_last_name="Viewer",
            email="admin.viewer@example.com",
            phone="9999999997",
            role="admin",
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

    def test_permission_based_admin_can_see_employee_attendance_activities(self):
        activity_date = timezone.localdate()
        admin_user = User.objects.create_user(
            username="attendance_activity_admin", password="password"
        )
        admin_employee = Employee.objects.create(
            employee_user_id=admin_user,
            employee_first_name="Admin",
            employee_last_name="Activity",
            email="admin.activity@example.com",
            phone="9999999994",
            role="admin",
        )

        other_user = User.objects.create_user(
            username="attendance_activity_other", password="password"
        )
        other_employee = Employee.objects.create(
            employee_user_id=other_user,
            employee_first_name="Visible",
            employee_last_name="Activity",
            email="visible.activity@example.com",
            phone="9999999993",
        )

        AttendanceActivity.objects.create(
            employee_id=admin_employee,
            attendance_date=activity_date,
            clock_in_date=activity_date,
            clock_in=datetime.strptime("09:00", "%H:%M").time(),
        )
        AttendanceActivity.objects.create(
            employee_id=other_employee,
            attendance_date=activity_date,
            clock_in_date=activity_date,
            clock_in=datetime.strptime("10:00", "%H:%M").time(),
        )

        self.client.force_authenticate(user=admin_user)
        response = self.client.get(
            "/api/attendance/attendance-activity/",
            format="json",
        )

        assert response.status_code == 200
        visible_employee_ids = {row["employee_id"] for row in response.json()}
        assert admin_employee.id in visible_employee_ids
        assert other_employee.id in visible_employee_ids

    def test_superuser_can_see_all_employee_attendance_data(self):
        activity_date = timezone.localdate()
        superuser = User.objects.create_superuser(
            username="attendance_superuser",
            password="password",
            email="attendance_superuser@example.com",
        )

        other_user = User.objects.create_user(
            username="attendance_superuser_other", password="password"
        )
        other_employee = Employee.objects.create(
            employee_user_id=other_user,
            employee_first_name="Visible",
            employee_last_name="Superuser",
            email="visible.superuser@example.com",
            phone="9999999991",
        )

        attendance = Attendance.objects.create(
            employee_id=other_employee,
            attendance_date=activity_date,
            attendance_clock_in=timezone.localtime().time().replace(microsecond=0),
            attendance_clock_in_date=activity_date,
            attendance_validated=True,
            minimum_hour="00:00",
        )
        sync_work_record_from_attendance(attendance)
        AttendanceActivity.objects.create(
            employee_id=other_employee,
            attendance_date=activity_date,
            clock_in_date=activity_date,
            clock_in=datetime.strptime("10:00", "%H:%M").time(),
        )

        self.client.force_authenticate(user=superuser)
        work_record_response = self.client.get(
            "/api/attendance/attendance/work-records/",
            {"month": activity_date.strftime("%Y-%m")},
            format="json",
        )
        activity_response = self.client.get(
            "/api/attendance/attendance-activity/",
            format="json",
        )

        assert work_record_response.status_code == 200
        assert activity_response.status_code == 200
        assert any(
            row["employee_id"] == other_employee.id for row in work_record_response.json()
        )
        assert any(
            row["employee_id"] == other_employee.id for row in activity_response.json()
        )

    def test_admin_group_user_can_see_all_employee_attendance_activities(self):
        activity_date = timezone.localdate()
        admin_group, _ = Group.objects.get_or_create(name="Admin User")
        admin_user = User.objects.create_user(
            username="attendance_group_admin", password="password"
        )
        admin_user.groups.add(admin_group)
        admin_employee = Employee.objects.create(
            employee_user_id=admin_user,
            employee_first_name="Group",
            employee_last_name="Admin",
            email="group.admin@example.com",
            phone="9999999990",
        )

        other_user = User.objects.create_user(
            username="attendance_group_other", password="password"
        )
        other_employee = Employee.objects.create(
            employee_user_id=other_user,
            employee_first_name="Visible",
            employee_last_name="Group",
            email="visible.group@example.com",
            phone="9999999989",
        )

        AttendanceActivity.objects.create(
            employee_id=admin_employee,
            attendance_date=activity_date,
            clock_in_date=activity_date,
            clock_in=datetime.strptime("09:00", "%H:%M").time(),
        )
        AttendanceActivity.objects.create(
            employee_id=other_employee,
            attendance_date=activity_date,
            clock_in_date=activity_date,
            clock_in=datetime.strptime("10:00", "%H:%M").time(),
        )

        self.client.force_authenticate(user=admin_user)
        response = self.client.get(
            "/api/attendance/attendance-activity/",
            format="json",
        )

        assert response.status_code == 200
        visible_employee_ids = {row["employee_id"] for row in response.json()}
        assert admin_employee.id in visible_employee_ids
        assert other_employee.id in visible_employee_ids

    def test_admin_can_see_all_attendance_activities_despite_company_filter(self):
        activity_date = timezone.localdate()
        admin_user = User.objects.create_user(
            username="attendance_company_admin", password="password"
        )
        admin_employee = Employee.objects.create(
            employee_user_id=admin_user,
            employee_first_name="Company",
            employee_last_name="Admin",
            email="company.admin@example.com",
            phone="9999999987",
            role="admin",
        )

        other_user = User.objects.create_user(
            username="attendance_company_other", password="password"
        )
        other_employee = Employee.objects.create(
            employee_user_id=other_user,
            employee_first_name="Visible",
            employee_last_name="Company",
            email="visible.company@example.com",
            phone="9999999986",
        )

        AttendanceActivity.objects.create(
            employee_id=admin_employee,
            attendance_date=activity_date,
            clock_in_date=activity_date,
            clock_in=datetime.strptime("09:00", "%H:%M").time(),
        )
        AttendanceActivity.objects.create(
            employee_id=other_employee,
            attendance_date=activity_date,
            clock_in_date=activity_date,
            clock_in=datetime.strptime("10:00", "%H:%M").time(),
        )

        AttendanceActivity.company_filter = Q(employee_id__id=-1)
        _thread_locals.request = SimpleNamespace(session={"selected_company": "1"})

        self.client.force_authenticate(user=admin_user)
        response = self.client.get(
            "/api/attendance/attendance-activity/",
            format="json",
        )

        assert response.status_code == 200
        visible_employee_ids = {row["employee_id"] for row in response.json()}
        assert admin_employee.id in visible_employee_ids
        assert other_employee.id in visible_employee_ids

    def test_employee_only_sees_own_attendance_activities(self):
        activity_date = timezone.localdate()
        other_user = User.objects.create_user(
            username="attendance_activity_peer", password="password"
        )
        other_employee = Employee.objects.create(
            employee_user_id=other_user,
            employee_first_name="Peer",
            employee_last_name="Activity",
            email="peer.activity@example.com",
            phone="9999999992",
        )

        AttendanceActivity.objects.create(
            employee_id=self.employee,
            attendance_date=activity_date,
            clock_in_date=activity_date,
            clock_in=datetime.strptime("09:00", "%H:%M").time(),
        )
        AttendanceActivity.objects.create(
            employee_id=other_employee,
            attendance_date=activity_date,
            clock_in_date=activity_date,
            clock_in=datetime.strptime("10:00", "%H:%M").time(),
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            "/api/attendance/attendance-activity/",
            format="json",
        )

        assert response.status_code == 200
        visible_employee_ids = {row["employee_id"] for row in response.json()}
        assert self.employee.id in visible_employee_ids
        assert other_employee.id not in visible_employee_ids
    def test_negative_utc_local_activity_does_not_return_negative_at_work(self):
        attendance_date = timezone.localdate()
        attendance = Attendance.objects.create(
            employee_id=self.employee,
            attendance_date=attendance_date,
            attendance_clock_in_date=attendance_date,
            attendance_clock_in=datetime.strptime("12:30", "%H:%M").time(),
            attendance_validated=False,
            minimum_hour="00:00",
        )

        utc_instant = datetime(
            attendance_date.year,
            attendance_date.month,
            attendance_date.day,
            7,
            0,
            tzinfo=dt_timezone.utc,
        )
        AttendanceActivity.objects.create(
            employee_id=self.employee,
            attendance_date=attendance_date,
            clock_in_date=attendance_date,
            clock_in=datetime.strptime("12:30", "%H:%M").time(),
            in_datetime=utc_instant,
            clock_out_date=attendance_date,
            clock_out=datetime.strptime("07:00", "%H:%M").time(),
            out_datetime=utc_instant,
        )

        attendance.save()
        attendance.refresh_from_db()

        assert attendance.attendance_worked_hour == "00:00:00"

        response = self.client.get(
            "/api/attendance/attendance/",
            {
                "attendance_date": attendance_date.strftime("%Y-%m-%d"),
                "validated": "false",
            },
            format="json",
        )
        assert response.status_code == 200
        result = next(
            (
                row
                for row in response.json()["results"]
                if row["employee_id"] == self.employee.id
                and row["date"] == str(attendance_date)
            ),
            None,
        )
        assert result is not None
        assert result["at_work"] == "00:00:00"

    def test_non_validated_attendance_api_repairs_at_work_for_employee_and_admin(self):
        attendance_date = timezone.localdate()
        admin_user = User.objects.create_user(
            username="attendance_admin_repair", password="password"
        )
        admin_user.user_permissions.add(
            Permission.objects.get(codename="view_attendance")
        )
        admin_employee = Employee.objects.create(
            employee_user_id=admin_user,
            employee_first_name="Admin",
            employee_last_name="Repair",
            email="admin.repair@example.com",
            phone="9999999995",
        )

        self.client.force_authenticate(user=self.user)
        with patch(
            "django.utils.timezone.now",
            return_value=self._aware_datetime(11, 0, attendance_date),
        ):
            employee_clock_in = self.client.post(
                "/api/attendance/clock-in/", format="json"
            )
        assert employee_clock_in.status_code == 200
        with patch(
            "django.utils.timezone.now",
            return_value=self._aware_datetime(19, 0, attendance_date),
        ):
            employee_clock_out = self.client.post(
                "/api/attendance/clock-out/", format="json"
            )
        assert employee_clock_out.status_code == 200

        self.client.force_authenticate(user=admin_user)
        with patch(
            "django.utils.timezone.now",
            return_value=self._aware_datetime(11, 15, attendance_date),
        ):
            admin_clock_in = self.client.post("/api/attendance/clock-in/", format="json")
        assert admin_clock_in.status_code == 200
        with patch(
            "django.utils.timezone.now",
            return_value=self._aware_datetime(19, 15, attendance_date),
        ):
            admin_clock_out = self.client.post(
                "/api/attendance/clock-out/", format="json"
            )
        assert admin_clock_out.status_code == 200

        employee_attendance = Attendance.objects.get(
            employee_id=self.employee, attendance_date=attendance_date
        )
        admin_attendance = Attendance.objects.get(
            employee_id=admin_employee, attendance_date=attendance_date
        )

        Attendance.objects.filter(pk=employee_attendance.pk).update(
            attendance_worked_hour="-143:00:00",
            at_work_second=-514800,
            attendance_overtime="00:00",
            overtime_second=0,
        )
        Attendance.objects.filter(pk=admin_attendance.pk).update(
            attendance_worked_hour="-143:00:00",
            at_work_second=-514800,
            attendance_overtime="00:00",
            overtime_second=0,
        )

        self.client.force_authenticate(user=self.user)
        employee_response = self.client.get(
            "/api/attendance/attendance/",
            {
                "attendance_date": attendance_date.strftime("%Y-%m-%d"),
                "validated": "false",
            },
            format="json",
        )
        assert employee_response.status_code == 200
        employee_result = next(
            (
                row
                for row in employee_response.json()["results"]
                if row["employee_id"] == self.employee.id
            ),
            None,
        )
        assert employee_result is not None
        assert employee_result["at_work"] == "08:00:00"

        employee_attendance.refresh_from_db()
        assert employee_attendance.attendance_worked_hour == "08:00:00"
        assert employee_attendance.at_work_second == 28800

        self.client.force_authenticate(user=admin_user)
        admin_response = self.client.get(
            "/api/attendance/attendance/",
            {
                "attendance_date": attendance_date.strftime("%Y-%m-%d"),
                "validated": "false",
            },
            format="json",
        )
        assert admin_response.status_code == 200
        admin_results = {
            row["employee_id"]: row["at_work"]
            for row in admin_response.json()["results"]
        }
        assert admin_results[self.employee.id] == "08:00:00"
        assert admin_results[admin_employee.id] == "08:00:00"

        admin_attendance.refresh_from_db()
        assert admin_attendance.attendance_worked_hour == "08:00:00"
        assert admin_attendance.at_work_second == 28800
