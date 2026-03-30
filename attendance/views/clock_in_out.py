"""
clock_in_out.py

This module is used register endpoints to the check-in check-out functionalities
"""

import ipaddress
import logging

logger = logging.getLogger(__name__)
from datetime import date, datetime, timedelta

from django.contrib import messages
from django.conf import settings
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from attendance.methods.utils import (
    activity_datetime,
    employee_exists,
    format_time,
    overtime_calculation,
    shift_schedule_today,
    strtime_seconds,
)
from attendance.models import (
    Attendance,
    AttendanceActivity,
    AttendanceGeneralSetting,
    AttendanceLateComeEarlyOut,
    GraceTime,
)
from attendance.signals import sync_work_record_from_attendance
from attendance.views.views import attendance_validate
from base.context_processors import (
    enable_late_come_early_out_tracking,
    timerunner_enabled,
)
from base.models import AttendanceAllowedIP, Company, EmployeeShiftDay
from horilla.decorators import hx_request_required, login_required
from horilla.horilla_middlewares import _thread_locals


def late_come_create(attendance):
    """
    used to create late come report
    args:
        attendance : attendance object
    """

    if AttendanceLateComeEarlyOut.objects.filter(
        type="late_come", attendance_id=attendance
    ).exists():
        late_come_obj = AttendanceLateComeEarlyOut.objects.filter(
            type="late_come", attendance_id=attendance
        ).first()
    else:
        late_come_obj = AttendanceLateComeEarlyOut()

    late_come_obj.type = "late_come"
    late_come_obj.attendance_id = attendance
    late_come_obj.employee_id = attendance.employee_id
    late_come_obj.save()
    return late_come_obj


def late_come(attendance, start_time, end_time, shift):
    """
    this method is used to mark the late check-in  attendance after the shift starts
    args:
        attendance : attendance obj
        start_time : attendance day shift start time
        end_time : attendance day shift end time

    """
    if not enable_late_come_early_out_tracking(None).get("tracking"):
        return
    request = getattr(_thread_locals, "request", None)
    now_sec = strtime_seconds(attendance.attendance_clock_in.strftime("%H:%M"))
    mid_day_sec = strtime_seconds("12:00")

    # Checking gracetime allowance before creating late come
    if shift and shift.grace_time_id:
        # checking grace time in shift, it has the higher priority
        if (
            shift.grace_time_id.is_active == True
            and shift.grace_time_id.allowed_clock_in == True
        ):
            # Setting allowance for the check in time
            now_sec -= shift.grace_time_id.allowed_time_in_secs
    # checking default grace time
    elif GraceTime.objects.filter(is_default=True, is_active=True).exists():
        grace_time = GraceTime.objects.filter(
            is_default=True,
            is_active=True,
        ).first()
        # Setting allowance for the check in time if grace allocate for clock in event
        if grace_time.allowed_clock_in:
            now_sec -= grace_time.allowed_time_in_secs
    else:
        pass
    if start_time > end_time and start_time != end_time:
        # night shift
        if now_sec < mid_day_sec:
            # Here  attendance or attendance activity for new day night shift
            late_come_create(attendance)
        elif now_sec > start_time:
            # Here  attendance or attendance activity for previous day night shift
            late_come_create(attendance)
    elif start_time < now_sec:
        late_come_create(attendance)
    return True


def clock_in_attendance_and_activity(
    employee,
    date_today,
    attendance_date,
    day,
    now,
    shift,
    minimum_hour,
    start_time,
    end_time,
    in_datetime,
):
    """
    This method is used to create attendance activity or attendance when an employee clocks-in
    args:
        employee        : employee instance
        date_today      : date
        attendance_date : the date that attendance for
        day             : shift day
        now             : current time
        shift           : shift object
        minimum_hour    : minimum hour in shift schedule
        start_time      : start time in shift schedule
        end_time        : end time in shift schedule
    """

    # attendance activity create
    activity = AttendanceActivity.objects.filter(
        employee_id=employee,
        attendance_date=attendance_date,
        clock_in_date=date_today,
        shift_day=day,
        clock_out=None,
    ).first()

    if activity and not activity.clock_out:
        activity.clock_out = in_datetime
        activity.clock_out_date = date_today
        activity.save()

    last_closed_activity = (
        AttendanceActivity.objects.filter(
            employee_id=employee,
            attendance_date=attendance_date,
            clock_out__isnull=False,
            clock_out_date__isnull=False,
        )
        .order_by("-out_datetime", "-id")
        .first()
    )
    resumed_clock_in = in_datetime.time()
    resumed_clock_in_datetime = in_datetime
    resumed_clock_in_date = date_today

    # If the user is checking in again after a check-out, continue from last check-out.
    if last_closed_activity and last_closed_activity.out_datetime:
        resumed_clock_in = last_closed_activity.clock_out
        resumed_clock_in_datetime = last_closed_activity.out_datetime
        resumed_clock_in_date = last_closed_activity.clock_out_date

    new_activity = AttendanceActivity.objects.create(
        employee_id=employee,
        attendance_date=attendance_date,
        clock_in_date=resumed_clock_in_date,
        shift_day=day,
        clock_in=resumed_clock_in,
        in_datetime=resumed_clock_in_datetime,
    )
    # create attendance if not exist
    attendance = Attendance.objects.filter(
        employee_id=employee, attendance_date=attendance_date
    )
    if not attendance.exists():
        attendance = Attendance()
        attendance.employee_id = employee
        attendance.shift_id = shift
        attendance.work_type_id = attendance.employee_id.employee_work_info.work_type_id
        attendance.attendance_date = attendance_date
        attendance.attendance_day = day
        attendance.attendance_clock_in = now
        attendance.attendance_clock_in_date = date_today
        attendance.minimum_hour = minimum_hour
        attendance.attendance_validated = True
        attendance.save()
        # check here late come or not

        attendance = Attendance.find(attendance.id)
        sync_work_record_from_attendance(attendance)
        late_come(
            attendance=attendance, start_time=start_time, end_time=end_time, shift=shift
        )
    else:
        attendance = attendance[0]
        attendance.attendance_clock_out = None
        attendance.attendance_clock_out_date = None
        attendance.attendance_validated = True
        attendance.save()
        sync_work_record_from_attendance(attendance)
        # delete if the attendance marked the early out
        early_out_instance = attendance.late_come_early_out.filter(type="early_out")
        if early_out_instance.exists():
            early_out_instance[0].delete()
    return attendance


@login_required
@hx_request_required
def clock_in(request):
    """
    This method is used to mark the attendance once per a day and multiple attendance activities.
    """
    # check wether check in/check out feature is enabled
    selected_company = request.session.get("selected_company")
    if selected_company == "all":
        attendance_general_settings = AttendanceGeneralSetting.objects.filter(
            company_id=None
        ).first()
    else:
        company = Company.objects.filter(id=selected_company).first()
        attendance_general_settings = AttendanceGeneralSetting.objects.filter(
            company_id=company
        ).first()
    # request.__dict__.get("datetime")' used to check if the request is from a biometric device
    if (
        attendance_general_settings
        and attendance_general_settings.enable_check_in
        or request.__dict__.get("datetime")
    ):
        allowed_attendance_ips = AttendanceAllowedIP.objects.first()

        if (
            not request.__dict__.get("datetime")
            and allowed_attendance_ips
            and allowed_attendance_ips.is_enabled
        ):

            x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
            ip = request.META.get("REMOTE_ADDR")
            if x_forwarded_for:
                ip = x_forwarded_for.split(",")[0]

            allowed_ips = allowed_attendance_ips.additional_data.get("allowed_ips", [])
            ip_allowed = False
            for allowed_ip in allowed_ips:
                try:
                    if ipaddress.ip_address(ip) in ipaddress.ip_network(
                        allowed_ip, strict=False
                    ):
                        ip_allowed = True
                        break
                except ValueError:
                    continue

            if not ip_allowed:
                return HttpResponse(_("You cannot mark attendance from this network"))

        employee, work_info = employee_exists(request)
        datetime_now = datetime.now()
        if request.__dict__.get("datetime"):
            datetime_now = request.datetime
        if employee and work_info is not None:
            shift = work_info.shift_id
            date_today = date.today()
            if request.__dict__.get("date"):
                date_today = request.date
            attendance_date = date_today
            day = date_today.strftime("%A").lower()
            day = EmployeeShiftDay.objects.get(day=day)
            now = datetime.now().strftime("%H:%M")
            if request.__dict__.get("time"):
                now = request.time.strftime("%H:%M")
            now_sec = strtime_seconds(now)
            mid_day_sec = strtime_seconds("12:00")
            minimum_hour, start_time_sec, end_time_sec = shift_schedule_today(
                day=day, shift=shift
            )
            if start_time_sec > end_time_sec:
                # night shift
                # ------------------
                # Night shift in Horilla consider a 24 hours from noon to next day noon,
                # the shift day taken today if the attendance clocked in after 12 O clock.

                if mid_day_sec > now_sec:
                    # Here you need to create attendance for yesterday

                    date_yesterday = date_today - timedelta(days=1)
                    day_yesterday = date_yesterday.strftime("%A").lower()
                    day_yesterday = EmployeeShiftDay.objects.get(day=day_yesterday)
                    minimum_hour, start_time_sec, end_time_sec = shift_schedule_today(
                        day=day_yesterday, shift=shift
                    )
                    attendance_date = date_yesterday
                    day = day_yesterday
            attendance = clock_in_attendance_and_activity(
                employee=employee,
                date_today=date_today,
                attendance_date=attendance_date,
                day=day,
                now=now,
                shift=shift,
                minimum_hour=minimum_hour,
                start_time=start_time_sec,
                end_time=end_time_sec,
                in_datetime=datetime_now,
            )
            return render(request, "attendance/components/in_out_component.html")
        return HttpResponse(
            _(
                "You Don't have work information filled or your employee detail neither entered "
            )
        )
    else:
        messages.error(request, _("Check in/Check out feature is not enabled."))
        return HttpResponse("<script>location.reload();</script>")


def clock_out_attendance_and_activity(
    employee, date_today, now, out_datetime=None, attendance=None
):
    """
    Clock out the attendance and activity
    args:
        employee    : employee instance
        date_today  : today date
        now         : now
    """

    if attendance is None:
        attendance = (
            Attendance.objects.filter(employee_id=employee)
            .order_by("-attendance_date", "-id")
            .first()
        )
    if attendance is None:
        logger.error("No attendance found that needs clocking out.")
        return

    if out_datetime is None:
        out_datetime = datetime.combine(
            date_today, datetime.strptime(now, "%H:%M").time()
        )

    open_activities = AttendanceActivity.objects.filter(
        employee_id=employee,
        attendance_date=attendance.attendance_date,
        clock_out__isnull=True,
    ).order_by("clock_in_date", "clock_in", "id")

    for attendance_activity in open_activities:
        attendance_activity.clock_out = out_datetime.time()
        attendance_activity.clock_out_date = date_today
        attendance_activity.out_datetime = out_datetime
        attendance_activity.save()

    attendance_activities = AttendanceActivity.objects.filter(
        employee_id=employee,
        attendance_date=attendance.attendance_date,
        clock_out__isnull=False,
        clock_out_date__isnull=False,
    ).order_by("attendance_date", "id")

    duration = 0
    for activity in attendance_activities:
        in_datetime, activity_out_datetime = activity_datetime(activity)
        difference = activity_out_datetime - in_datetime
        days_second = difference.days * 24 * 3600
        seconds = difference.seconds
        total_seconds = days_second + seconds
        duration = duration + total_seconds

    attendance.attendance_clock_out = out_datetime.time()
    attendance.attendance_clock_out_date = date_today
    attendance.attendance_worked_hour = format_time(duration)
    attendance.attendance_overtime = overtime_calculation(attendance)

    # Business rule: once attendance is marked through check-in/check-out,
    # keep it validated so it appears as present in attendance views.
    attendance.attendance_validated = True
    attendance.save()
    sync_work_record_from_attendance(attendance)

    return attendance


def get_auto_checkout_time():
    """
    Return the configured automatic check-out cutoff time.
    """
    configured_time = str(getattr(settings, "AUTO_CHECK_OUT_TIME", "18:25"))
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(configured_time, fmt).time()
        except ValueError:
            continue
    return datetime.strptime("18:25", "%H:%M").time()


def _resolve_activity_start_datetime(activity, fallback_datetime):
    """
    Build a timezone-aware start datetime for an attendance activity.
    """
    activity_start = activity.in_datetime
    if activity_start is None and activity.clock_in is not None:
        activity_start = datetime.combine(
            activity.clock_in_date or activity.attendance_date,
            activity.clock_in,
        )
    if activity_start is None:
        activity_start = fallback_datetime
    if timezone.is_naive(activity_start):
        activity_start = timezone.make_aware(
            activity_start,
            timezone.get_current_timezone(),
        )
    return activity_start


def _resolve_attendance_clock_out_datetime(attendance, fallback_datetime):
    """
    Build a timezone-aware clock-out datetime from a parent attendance row.
    """
    attendance_clock_out = getattr(attendance, "attendance_clock_out", None)
    if attendance_clock_out is None:
        return fallback_datetime

    attendance_clock_out_datetime = datetime.combine(
        attendance.attendance_clock_out_date or attendance.attendance_date,
        attendance_clock_out,
    )
    if timezone.is_naive(attendance_clock_out_datetime):
        attendance_clock_out_datetime = timezone.make_aware(
            attendance_clock_out_datetime,
            timezone.get_current_timezone(),
        )
    return attendance_clock_out_datetime


def cleanup_stale_open_activities(employee=None, current_datetime=None):
    """
    Close open activity rows whose parent attendance is already clocked out.
    """
    current_datetime = timezone.localtime(current_datetime or timezone.now())
    open_activities = AttendanceActivity.objects.filter(clock_out__isnull=True).order_by(
        "attendance_date",
        "id",
    )
    if employee is not None:
        open_activities = open_activities.filter(employee_id=employee)

    attendance_cache = {}
    cleaned_count = 0

    for activity in open_activities:
        cache_key = (activity.employee_id_id, activity.attendance_date)
        if cache_key not in attendance_cache:
            attendance_cache[cache_key] = (
                Attendance.objects.filter(
                    employee_id=activity.employee_id,
                    attendance_date=activity.attendance_date,
                )
                .order_by("-id")
                .first()
            )
        attendance = attendance_cache[cache_key]
        if attendance is None or attendance.attendance_clock_out is None:
            continue

        activity_start = _resolve_activity_start_datetime(activity, current_datetime)
        attendance_clock_out_datetime = _resolve_attendance_clock_out_datetime(
            attendance,
            current_datetime,
        )
        resolved_clock_out_datetime = max(
            activity_start,
            attendance_clock_out_datetime,
        )

        activity.clock_out = resolved_clock_out_datetime.time()
        activity.clock_out_date = resolved_clock_out_datetime.date()
        activity.out_datetime = resolved_clock_out_datetime
        activity.save(update_fields=["clock_out", "clock_out_date", "out_datetime"])
        cleaned_count += 1

    if cleaned_count:
        request = getattr(_thread_locals, "request", None)
        if request is not None and hasattr(request, "working_employees"):
            request.working_employees = None

    return cleaned_count


def perform_clock_out(employee, date_today, now, out_datetime=None, attendance=None):
    """
    Apply the shared clock-out flow used by manual and automatic check-out.
    """
    work_info = getattr(employee, "employee_work_info", None)
    shift = getattr(work_info, "shift_id", None)
    if attendance is None:
        attendance = (
            Attendance.objects.filter(
                employee_id=employee,
                attendance_clock_in__isnull=False,
                attendance_clock_out__isnull=True,
            )
            .order_by("-attendance_date", "-id")
            .first()
        )
    if attendance is None:
        attendance = (
            Attendance.objects.filter(employee_id=employee)
            .order_by("-attendance_date", "-id")
            .first()
        )

    if attendance is None:
        return None

    if not attendance.attendance_day:
        day_name = attendance.attendance_date.strftime("%A").lower()
        attendance.attendance_day = EmployeeShiftDay.objects.get(day=day_name)
        attendance.save(update_fields=["attendance_day"])

    day = attendance.attendance_day
    if attendance.shift_id:
        shift = attendance.shift_id

    minimum_hour, start_time_sec, end_time_sec = ("00:00", 0, 0)
    if shift and day:
        minimum_hour, start_time_sec, end_time_sec = shift_schedule_today(
            day=day, shift=shift
        )

    attendance = clock_out_attendance_and_activity(
        employee=employee,
        date_today=date_today,
        now=now,
        out_datetime=out_datetime,
        attendance=attendance,
    )

    if not attendance or not shift:
        return attendance

    early_out_instance = attendance.late_come_early_out.filter(type="early_out")
    is_night_shift = attendance.is_night_shift()
    next_date = attendance.attendance_date + timedelta(days=1)

    if not early_out_instance.exists():
        if is_night_shift:
            now_sec = strtime_seconds(now)
            mid_sec = strtime_seconds("12:00")

            if (attendance.attendance_date == date_today) or (
                mid_sec >= now_sec and date_today == next_date
            ):
                early_out(
                    attendance=attendance,
                    start_time=start_time_sec,
                    end_time=end_time_sec,
                    shift=shift,
                )
        elif attendance.attendance_date == date_today:
            early_out(
                attendance=attendance,
                start_time=start_time_sec,
                end_time=end_time_sec,
                shift=shift,
            )

    request = getattr(_thread_locals, "request", None)
    if request is not None and hasattr(request, "working_employees"):
        request.working_employees = None

    return attendance


def auto_checkout_attendance_if_due(attendance, current_datetime=None):
    """
    Clock out an open attendance once the configured cutoff time is reached.
    """
    if attendance is None or attendance.attendance_clock_out is not None:
        return False

    employee = getattr(attendance, "employee_id", None)
    if employee is None:
        return False

    current_datetime = timezone.localtime(current_datetime or timezone.now())
    checkout_time = get_auto_checkout_time()
    auto_checkout_date = attendance.attendance_date

    if attendance.is_night_shift():
        auto_checkout_date += timedelta(days=1)

    cutoff_datetime = timezone.make_aware(
        datetime.combine(auto_checkout_date, checkout_time),
        timezone.get_current_timezone(),
    )

    if current_datetime < cutoff_datetime:
        return False

    perform_clock_out(
        employee=employee,
        date_today=auto_checkout_date,
        now=checkout_time.strftime("%H:%M"),
        out_datetime=cutoff_datetime,
        attendance=attendance,
    )
    return True


def early_out_create(attendance):
    """
    Used to create early out report
    args:
        attendance : attendance obj
    """
    if AttendanceLateComeEarlyOut.objects.filter(
        type="early_out", attendance_id=attendance
    ).exists():
        late_come_obj = AttendanceLateComeEarlyOut.objects.filter(
            type="early_out", attendance_id=attendance
        ).first()
    else:
        late_come_obj = AttendanceLateComeEarlyOut()
    late_come_obj.type = "early_out"
    late_come_obj.attendance_id = attendance
    late_come_obj.employee_id = attendance.employee_id
    late_come_obj.save()
    return late_come_obj


def early_out(attendance, start_time, end_time, shift):
    """
    This method is used to mark the early check-out attendance before the shift ends
    args:
        attendance : attendance obj
        start_time : attendance day shift start time
        start_end : attendance day shift end time
    """
    if not enable_late_come_early_out_tracking(None).get("tracking"):
        return

    clock_out_time = attendance.attendance_clock_out
    if isinstance(clock_out_time, str):
        clock_out_time = datetime.strptime(clock_out_time, "%H:%M:%S")

    now_sec = strtime_seconds(clock_out_time.strftime("%H:%M"))
    mid_day_sec = strtime_seconds("12:00")
    # Checking gracetime allowance before creating early out
    if shift and shift.grace_time_id:
        if (
            shift.grace_time_id.is_active == True
            and shift.grace_time_id.allowed_clock_out == True
        ):
            now_sec += shift.grace_time_id.allowed_time_in_secs
    elif GraceTime.objects.filter(is_default=True, is_active=True).exists():
        grace_time = GraceTime.objects.filter(
            is_default=True,
            is_active=True,
        ).first()
        # Setting allowance for the check out time if grace allocate for clock out event
        if grace_time.allowed_clock_out:
            now_sec += grace_time.allowed_time_in_secs
    else:
        pass
    if start_time > end_time:
        # Early out condition for night shift
        if now_sec < mid_day_sec:
            if now_sec < end_time:
                # Early out condition for general shift
                early_out_create(attendance)
        else:
            early_out_create(attendance)
        return
    if end_time > now_sec:
        early_out_create(attendance)
    return


@login_required
@hx_request_required
def clock_out(request):
    """
    This method is used to set the out date and time for attendance and attendance activity
    """
    # check wether check in/check out feature is enabled
    selected_company = request.session.get("selected_company")
    if selected_company == "all":
        attendance_general_settings = AttendanceGeneralSetting.objects.filter(
            company_id=None
        ).first()
    else:
        company = Company.objects.filter(id=selected_company).first()
        attendance_general_settings = AttendanceGeneralSetting.objects.filter(
            company_id=company
        ).first()
    if (
        attendance_general_settings
        and attendance_general_settings.enable_check_in
        or request.__dict__.get("datetime")
    ):
        datetime_now = datetime.now()
        if request.__dict__.get("datetime"):
            datetime_now = request.datetime
        employee, work_info = employee_exists(request)
        shift = work_info.shift_id
        date_today = date.today()
        if request.__dict__.get("date"):
            date_today = request.date
        now = datetime.now().strftime("%H:%M")
        if request.__dict__.get("time"):
            now = request.time.strftime("%H:%M")
        perform_clock_out(
            employee=employee,
            date_today=date_today,
            now=now,
            out_datetime=datetime_now,
        )

        return render(request, "attendance/components/in_out_component.html")
    else:
        messages.error(request, _("Check in/Check out feature is not enabled."))
        return HttpResponse("<script>location.reload();</script>")


@login_required
@hx_request_required
def in_out_component(request):
    """
    Refresh the attendance check-in/check-out control for the current user.
    """
    employee = getattr(request.user, "employee_get", None)
    if employee is not None:
        cleanup_stale_open_activities(employee=employee)
        open_attendance = (
            Attendance.objects.filter(
                employee_id=employee,
                attendance_clock_in__isnull=False,
                attendance_clock_out__isnull=True,
            )
            .order_by("-attendance_date", "-id")
            .first()
        )
        auto_checkout_attendance_if_due(open_attendance)
    return render(request, "attendance/components/in_out_component.html")
