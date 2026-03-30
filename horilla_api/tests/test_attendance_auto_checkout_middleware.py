from datetime import datetime, time
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from attendance.middleware import AttendanceMiddleware
from attendance.models import Attendance, AttendanceActivity
from base.models import EmployeeShiftDay
from employee.models import Employee


class AttendanceAutoCheckoutMiddlewareTest(TestCase):
    def setUp(self):
        EmployeeShiftDay.objects.get_or_create(day="wednesday")
        self.user = User.objects.create_user(
            username="auto_checkout_tester",
            password="password",
        )
        self.employee = Employee.objects.create(
            employee_user_id=self.user,
            employee_first_name="Mia",
            employee_last_name="Patel",
            email="mia.patel@example.com",
            phone="9999999995",
        )
        self.attendance_date = datetime(2026, 3, 25).date()
        self.attendance = Attendance.objects.create(
            employee_id=self.employee,
            attendance_date=self.attendance_date,
            attendance_clock_in=time(9, 0),
            attendance_clock_in_date=self.attendance_date,
            attendance_validated=True,
            minimum_hour="00:00",
        )

    @override_settings(AUTO_CHECK_OUT_TIME="18:25:00")
    @patch("attendance.views.clock_in_out.perform_clock_out")
    def test_auto_checkout_runs_at_and_after_625_pm(self, mock_perform_clock_out):
        current_time = timezone.make_aware(
            datetime(2026, 3, 25, 18, 25),
            timezone.get_current_timezone(),
        )

        with patch("attendance.middleware.timezone.now", return_value=current_time):
            AttendanceMiddleware(lambda request: None).trigger_function()

        mock_perform_clock_out.assert_called_once_with(
            employee=self.employee,
            date_today=self.attendance_date,
            now="18:25",
            out_datetime=current_time,
            attendance=self.attendance,
        )

    @override_settings(AUTO_CHECK_OUT_TIME="18:25")
    @patch("attendance.views.clock_in_out.perform_clock_out")
    def test_auto_checkout_skips_before_625_pm(self, mock_perform_clock_out):
        current_time = timezone.make_aware(
            datetime(2026, 3, 25, 18, 24),
            timezone.get_current_timezone(),
        )

        with patch("attendance.middleware.timezone.now", return_value=current_time):
            AttendanceMiddleware(lambda request: None).trigger_function()

        mock_perform_clock_out.assert_not_called()

    @override_settings(AUTO_CHECK_OUT_TIME="18:25")
    @patch("attendance.views.clock_in_out.perform_clock_out")
    def test_in_out_component_refresh_triggers_auto_checkout_at_625_pm(
        self, mock_perform_clock_out
    ):
        session = self.client.session
        session["selected_company"] = "all"
        session.save()
        self.client.force_login(self.user)

        current_time = timezone.make_aware(
            datetime(2026, 3, 25, 18, 25),
            timezone.get_current_timezone(),
        )

        with patch("attendance.views.clock_in_out.timezone.now", return_value=current_time):
            response = self.client.get(
                "/attendance/in-out-component",
                HTTP_HX_REQUEST="true",
            )

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(mock_perform_clock_out.call_count, 1)
        mock_perform_clock_out.assert_any_call(
            employee=self.employee,
            date_today=self.attendance_date,
            now="18:25",
            out_datetime=current_time,
            attendance=self.attendance,
        )

    def test_in_out_component_closes_orphan_open_activity_after_closed_attendance(self):
        self.attendance.attendance_clock_out = time(18, 25)
        self.attendance.attendance_clock_out_date = self.attendance_date
        self.attendance.save(
            update_fields=["attendance_clock_out", "attendance_clock_out_date"]
        )
        orphan_activity = AttendanceActivity.objects.create(
            employee_id=self.employee,
            attendance_date=self.attendance_date,
            clock_in_date=self.attendance_date,
            clock_in=time(18, 25),
            in_datetime=timezone.make_aware(
                datetime(2026, 3, 25, 18, 25),
                timezone.get_current_timezone(),
            ),
        )

        session = self.client.session
        session["selected_company"] = "all"
        session.save()
        self.client.force_login(self.user)

        response = self.client.get(
            "/attendance/in-out-component",
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        orphan_activity.refresh_from_db()
        self.assertIsNotNone(orphan_activity.clock_out)
        self.assertEqual(orphan_activity.clock_out_date, self.attendance_date)
