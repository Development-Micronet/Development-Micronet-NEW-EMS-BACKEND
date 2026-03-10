import datetime
import sys

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from django.conf import settings
from django.utils import timezone

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
    from attendance.models import Attendance, AttendanceActivity

    now_local = timezone.localtime(timezone.now())
    checkout_time = _parse_auto_checkout_time()
    if now_local.time() < checkout_time:
        return

    today = now_local.date()
    open_attendances = Attendance.objects.filter(
        attendance_date=today,
        attendance_clock_in__isnull=False,
        attendance_clock_out__isnull=True,
    ).select_related("employee_id")

    for attendance in open_attendances:
        open_activity = (
            AttendanceActivity.objects.filter(
                employee_id=attendance.employee_id,
                attendance_date=today,
                clock_out__isnull=True,
            )
            .order_by("-in_datetime")
            .first()
        )

        if open_activity:
            open_activity.clock_out = now_local.time()
            open_activity.clock_out_date = today
            open_activity.out_datetime = now_local
            open_activity.save()

        attendance.attendance_clock_out = now_local.time()
        attendance.attendance_clock_out_date = today
        attendance.is_active = False
        if open_activity is not None:
            attendance.is_early_out = open_activity.is_early_out
        attendance.save()

        if attendance.employee_id:
            attendance.employee_id.is_active = False
            attendance.employee_id.save(update_fields=["is_active"])


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
