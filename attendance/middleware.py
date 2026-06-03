"""
Middleware to automatically trigger employee clock-out after the configured cutoff.
"""

from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin


class AttendanceMiddleware(MiddlewareMixin):
    """
    This middleware checks for employees who haven't clocked out by the end of their
    scheduled shift and automatically performs the clock-out action if the auto punch-out
    is enabled for their shift. It processes this during each request.
    """

    @staticmethod
    def _get_auto_checkout_time():
        """
        Returns the configured global auto checkout time.
        """
        configured_time = str(getattr(settings, "AUTO_CHECK_OUT_TIME", "18:45"))
        for fmt in ("%H:%M", "%H:%M:%S"):
            try:
                return datetime.strptime(configured_time, fmt).time()
            except ValueError:
                continue
        return datetime.strptime("18:45", "%H:%M").time()

    def process_request(self, request):
        """
        Triggers the `trigger_function` on each request.
        """
        self.trigger_function()

    def trigger_function(self):
        """
        Checks open attendance records and clocks them out once the configured cutoff
        time has passed for the attendance date.
        """
        from attendance.models import Attendance
        from attendance.views.clock_in_out import (
            auto_checkout_attendance_if_due,
            cleanup_stale_open_activities,
        )

        current_time = timezone.localtime(timezone.now())
        cleanup_stale_open_activities(current_datetime=current_time)
        open_attendances = (
            Attendance.objects.filter(
                attendance_clock_in__isnull=False,
                attendance_clock_out__isnull=True,
            )
            .select_related("employee_id", "employee_id__employee_user_id", "attendance_day")
            .order_by("attendance_date", "id")
        )

        for attendance in open_attendances:
            employee = getattr(attendance, "employee_id", None)
            user = getattr(employee, "employee_user_id", None)
            if not employee or not user:
                continue

            try:
                auto_checkout_attendance_if_due(
                    attendance=attendance,
                    current_datetime=current_time,
                )
            except Exception:
                continue
