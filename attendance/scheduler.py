import datetime
import sys

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from django.conf import settings
from django.utils import timezone

from attendance.methods.utils import Request
from base.backends import logger


def create_work_record():
    from attendance.models import WorkRecords
    from employee.models import Employee

    date = datetime.datetime.today()
    work_records = WorkRecords.objects.filter(date=date).values_list(
        "employee_id", flat=True
    )
    employees = Employee.objects.exclude(id__in=work_records)
    records_to_create = []

    for employee in employees:
        try:
            shift_schedule = employee.get_shift_schedule()
            if shift_schedule is None:
                continue

            shift = employee.get_shift()
            record = WorkRecords(
                employee_id=employee,
                date=date,
                work_record_type="DFT",
                shift_id=shift,
                message="",
            )
            records_to_create.append(record)
        except Exception as e:
            logger.error(f"Error preparing work record for {employee}: {e}")

    if records_to_create:
        try:
            WorkRecords.objects.bulk_create(records_to_create)
            print(f"Created {len(records_to_create)} work records for {date}.")
        except Exception as e:
            logger.error(f"Failed to bulk create work records: {e}")
    else:
        print(f"No new work records to create for {date}.")


def _parse_auto_checkout_time():
    raw_value = getattr(settings, "AUTO_CHECK_OUT_TIME", "18:45")
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.datetime.strptime(raw_value, fmt).time()
        except ValueError:
            continue
    logger.warning(
        "Invalid AUTO_CHECK_OUT_TIME '%s'. Falling back to 18:45.", raw_value
    )
    return datetime.time(18, 45)


def auto_checkout_employees():
    from attendance.models import Attendance
    from attendance.views.clock_in_out import clock_out

    now_local = timezone.localtime(timezone.now())
    checkout_time = _parse_auto_checkout_time()
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

        auto_checkout_date = attendance.attendance_date
        if attendance.is_night_shift():
            auto_checkout_date += datetime.timedelta(days=1)

        cutoff_datetime = timezone.make_aware(
            datetime.datetime.combine(auto_checkout_date, checkout_time),
            timezone.get_current_timezone(),
        )
        if now_local < cutoff_datetime:
            continue

        try:
            clock_out(
                Request(
                    user=user,
                    date=auto_checkout_date,
                    time=checkout_time,
                    datetime=cutoff_datetime,
                )
            )
        except Exception as exc:
            logger.exception(
                "Auto checkout failed for attendance %s: %s",
                attendance.pk,
                exc,
            )


if not any(
    cmd in sys.argv
    for cmd in ["makemigrations", "migrate", "compilemessages", "flush", "shell"]
):
    """
    Initializes and starts background tasks using APScheduler when the server is running.
    """
    scheduler = BackgroundScheduler(timezone=pytz.timezone(settings.TIME_ZONE))

    scheduler.add_job(
        create_work_record, "interval", minutes=30, misfire_grace_time=3600 * 3
    )
    scheduler.add_job(
        create_work_record,
        "cron",
        hour=0,
        minute=30,
        misfire_grace_time=3600 * 9,
        id="create_daily_work_record",
        replace_existing=True,
    )
    scheduler.add_job(
        auto_checkout_employees,
        "interval",
        minutes=1,
        misfire_grace_time=300,
        id="auto_checkout_after_configured_time",
        replace_existing=True,
    )

    scheduler.start()
