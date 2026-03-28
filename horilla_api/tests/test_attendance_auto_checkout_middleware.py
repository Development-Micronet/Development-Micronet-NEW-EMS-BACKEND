from datetime import datetime, time
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from attendance.middleware import AttendanceMiddleware
from attendance.models import Attendance
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

    @override_settings(AUTO_CHECK_OUT_TIME="18:30:00")
    @patch("attendance.views.clock_in_out.clock_out")
    def test_auto_checkout_runs_at_and_after_630_pm(self, mock_clock_out):
        current_time = timezone.make_aware(
            datetime(2026, 3, 25, 18, 30),
            timezone.get_current_timezone(),
        )

        with patch("attendance.middleware.timezone.now", return_value=current_time):
            AttendanceMiddleware(lambda request: None).trigger_function()

        mock_clock_out.assert_called_once()
        request = mock_clock_out.call_args.args[0]
        self.assertEqual(request.user, self.user)
        self.assertEqual(request.date, self.attendance_date)
        self.assertEqual(request.time, time(18, 30))
        self.assertEqual(request.datetime, current_time)

    @override_settings(AUTO_CHECK_OUT_TIME="18:30")
    @patch("attendance.views.clock_in_out.clock_out")
    def test_auto_checkout_skips_before_630_pm(self, mock_clock_out):
        current_time = timezone.make_aware(
            datetime(2026, 3, 25, 18, 29),
            timezone.get_current_timezone(),
        )

        with patch("attendance.middleware.timezone.now", return_value=current_time):
            AttendanceMiddleware(lambda request: None).trigger_function()

        mock_clock_out.assert_not_called()
