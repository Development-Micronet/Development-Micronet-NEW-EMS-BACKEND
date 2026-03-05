"""
Middleware to automatically trigger employee clock-out based on shift schedules
"""

from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from attendance.methods.utils import Request


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
        try:
            return datetime.strptime(configured_time, "%H:%M").time()
        except ValueError:
            return datetime.strptime("18:45", "%H:%M").time()

    def process_request(self, request):
        """
        Triggers the `trigger_function` on each request.
        """
        self.trigger_function()

    def trigger_function(self):
        """
        Retrieves shift schedules with auto punch-out enabled and checks if there are
        any attendance activities that haven't been clocked out. If the scheduled
        auto punch-out time has passed, the function attempts to clock out the employee
        automatically by invoking the `clock_out` function.
        """
        from attendance.models import Attendance, AttendanceActivity
        from attendance.views.clock_in_out import clock_out
        auto_checkout_time = self._get_auto_checkout_time()
        current_time = timezone.localtime(timezone.now())
        activities = (
            AttendanceActivity.objects.filter(clock_out_date=None, clock_out=None)
            .select_related("employee_id")
            .order_by("-created_at")
        )

        for activity in activities:
            attendance = (
                Attendance.objects.filter(
                    employee_id=activity.employee_id,
                    attendance_date=activity.attendance_date,
                    attendance_clock_out=None,
                    attendance_clock_out_date=None,
                )
                .order_by("-id")
                .first()
            )
            if not attendance:
                continue

            auto_checkout_date = activity.attendance_date
            if attendance.is_night_shift():
                auto_checkout_date += timedelta(days=1)

            combined_datetime = timezone.make_aware(
                datetime.combine(auto_checkout_date, auto_checkout_time),
                timezone.get_current_timezone(),
            )

            # Auto check-out applies once the configured cutoff time is reached.
            if current_time >= combined_datetime:
                try:
                    clock_out(
                        Request(
                            user=attendance.employee_id.employee_user_id,
                            date=auto_checkout_date,
                            time=auto_checkout_time,
                            datetime=combined_datetime,
                        )
                    )
                except Exception:
                    continue
