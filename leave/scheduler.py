import calendar
import datetime as dt
import sys
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from dateutil.relativedelta import relativedelta
from django.db import connection
from django.db.utils import OperationalError


def leave_reset():
    """
    Reset leave balances for employees based on configured reset dates.
    Includes proper error handling and database connection management.
    """
    try:
        from leave.models import LeaveType

        # Ensure database connection is available
        connection.ensure_connection()

        today = datetime.now()
        today_date = today.date()

        # Query with proper error handling
        try:
            leave_types = LeaveType.objects.filter(reset=True)
        except OperationalError:
            # Reconnect if database connection was lost
            connection.close()
            leave_types = LeaveType.objects.filter(reset=True)

        # Looping through filtered leave types with reset is true
        for leave_type in leave_types:
            # Looping through all available leaves
            available_leaves = leave_type.employee_available_leave.all()

            for available_leave in available_leaves:
                reset_date = available_leave.reset_date
                expired_date = available_leave.expired_date
                if reset_date == today_date:
                    available_leave.update_carryforward()
                    # new_reset_date = available_leave.set_reset_date(assigned_date=today_date,available_leave = available_leave)
                    new_reset_date = available_leave.set_reset_date(
                        assigned_date=today_date, available_leave=available_leave
                    )
                    available_leave.reset_date = new_reset_date
                    available_leave.save()
                if expired_date and expired_date <= today_date:
                    new_expired_date = available_leave.set_expired_date(
                        available_leave=available_leave, assigned_date=today_date
                    )
                    available_leave.expired_date = new_expired_date
                    available_leave.save()

            if (
                leave_type.carryforward_expire_date
                and leave_type.carryforward_expire_date <= today_date
            ):
                leave_type.carryforward_expire_date = leave_type.set_expired_date(
                    today_date
                )
                leave_type.save()
    except Exception as e:
        # Log the error but don't crash the scheduler
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error in leave_reset scheduler: {str(e)}", exc_info=True)


if not any(
    cmd in sys.argv
    for cmd in ["makemigrations", "migrate", "compilemessages", "flush", "shell"]
):
    """
    Initializes and starts background tasks using APScheduler when the server is running.
    """
    scheduler = BackgroundScheduler()
    scheduler.add_job(leave_reset, "interval", seconds=20)

    scheduler.start()
