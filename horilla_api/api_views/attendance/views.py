from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class OnlineOfflineEmployeesAPIView(APIView):
    """
    API endpoint to fetch today's attendance user id, name, and active status
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.utils import timezone

        from attendance.models import Attendance

        # today = timezone.localdate()

        attendances = Attendance.objects.filter(
            # attendance_date=today
        ).select_related(
            "employee_id",
            "employee_id__employee_user_id",
        )

        data = []
        seen_users = set()

        for attendance in attendances:
            employee = attendance.employee_id
            user_id = employee.employee_user_id_id

            if not user_id or user_id in seen_users:
                continue

            seen_users.add(user_id)

            data.append(
                {
                    "user_id": user_id,
                    "name": f"{employee.employee_first_name} {employee.employee_last_name or ''}".strip(),
                    "is_active": attendance.is_active,
                }
            )

        return Response(
            {
                "employees": data,
                "count": len(data),
            },
            status=status.HTTP_200_OK,
        )


# Bulk validate attendance records


class AttendanceBulkValidateView(APIView):
    """
    Bulk validate attendance records by IDs.
    """

    permission_classes = [IsAuthenticated]

    def patch(self, request):
        ids = request.data.get("ids", [])
        if not isinstance(ids, list) or not ids:
            return Response(
                {"error": "Provide a list of attendance IDs as 'ids'."}, status=400
            )
        from attendance.models import Attendance

        updated = Attendance.objects.filter(id__in=ids).update(
            attendance_validated=True
        )
        return Response({"validated": updated, "errors": []}, status=200)


# API: /attendance/overtime/pending/
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class OvertimePendingView(APIView):
    """
    API endpoint to fetch all attendance records with pending overtime approval.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Assuming 'attendance_overtime_approve' is False for pending
        from attendance.models import Attendance

        pending_overtime = Attendance.objects.filter(
            attendance_overtime_approve=False, attendance_overtime__isnull=False
        )
        data = []
        for obj in pending_overtime:
            data.append(
                {
                    "id": obj.id,
                    "employee_id": obj.employee_id.id if obj.employee_id else None,
                    "employee_name": str(obj.employee_id) if obj.employee_id else None,
                    "attendance_date": str(obj.attendance_date),
                    "overtime": obj.attendance_overtime,
                    "overtime_approved": obj.attendance_overtime_approve,
                }
            )
        return Response({"pending_overtime": data, "count": len(data)}, status=200)


# Validate all attendance records for a given employee_id
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class ValidateAttendanceByEmployeeView(APIView):
    """
    Validates all attendance records for a given employee_id.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, employee_id):
        attendances = Attendance.objects.filter(employee_id=employee_id)
        updated = attendances.update(attendance_validated=True)
        return Response(
            {
                "employee_id": employee_id,
                "validated_count": updated,
                "message": "Attendance validated for employee",
            },
            status=200,
        )


import logging
from datetime import date, datetime, timedelta, timezone

from django import template
from django.conf import settings
from django.core.mail import EmailMessage
from django.db.models import Case, CharField, F, Value, When
from django.http import QueryDict
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

# Create your views here.


# API: /attendance/on-break/
class OnBreakEmployeesAPIView(APIView):
    """
    API endpoint to fetch employees who are currently on break (early out) for today.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = datetime.today().date()
        early_outs = AttendanceLateComeEarlyOut.objects.filter(
            type="early_out", attendance_id__attendance_date=today
        )
        data = []
        for obj in early_outs:
            data.append(
                {
                    "id": obj.id,
                    "employee_id": obj.employee_id.id if obj.employee_id else None,
                    "employee_name": (
                        f"{obj.employee_id.employee_first_name} {obj.employee_id.employee_last_name}"
                        if obj.employee_id
                        else None
                    ),
                    "attendance_id": (
                        obj.attendance_id.id if obj.attendance_id else None
                    ),
                    "date": (
                        str(obj.attendance_id.attendance_date)
                        if obj.attendance_id
                        else None
                    ),
                    "type": obj.type,
                    "reason": obj.reason,
                    "created_at": (
                        obj.created_at.isoformat()
                        if hasattr(obj, "created_at") and obj.created_at
                        else None
                    ),
                }
            )
        return Response({"on_break_employees": data, "count": len(data)}, status=200)


from attendance.models import Attendance, AttendanceActivity, EmployeeShiftDay
from attendance.views.clock_in_out import *

logger = logging.getLogger(__name__)
from attendance.views.dashboard import (
    find_expected_attendances,
    find_late_come,
    find_on_time,
)
from attendance.views.views import *
from base.backends import ConfiguredEmailBackend
from base.methods import generate_pdf, is_reportingmanager
from base.models import HorillaMailTemplate
from employee.filters import EmployeeFilter

from ...api_decorators.base.decorators import (
    manager_permission_required,
    permission_required,
)
from ...api_methods.base.methods import groupby_queryset, permission_based_queryset
from ...api_serializers.attendance.serializers import (
    AttendanceActivitySerializer,
    AttendanceLateComeEarlyOutSerializer,
    AttendanceOverTimeSerializer,
    AttendanceRequestSerializer,
    AttendanceSerializer,
    MailTemplateSerializer,
    UserAttendanceDetailedSerializer,
    UserAttendanceListSerializer,
)
from ...docs import document_api

# Create your views here.


def query_dict(data):
    query_dict = QueryDict("", mutable=True)
    for key, value in data.items():
        if isinstance(value, list):
            for item in value:
                query_dict.appendlist(key, item)
        else:
            query_dict.update({key: value})
    return query_dict


class ClockInAPIView(APIView):
    """
    Allows authenticated employees to clock in, determining the correct shift and attendance date, including handling night shifts.

    Methods:
        post(request): Processes and records the clock-in time.
    """

    permission_classes = [IsAuthenticated]

    @document_api(
        operation_description="Record employee clock-in with automatic shift detection and attendance date assignment, supporting multiple clock-in cycles per day",
        tags=["Attendance"],
    )
    # def post(self, request):
    #     if not request.user.employee_get.check_online():
    #         try:
    #             if request.user.employee_get.get_company().geo_fencing.start:
    #                 from geofencing.views import GeoFencingEmployeeLocationCheckAPIView

    #                 location_api_view = GeoFencingEmployeeLocationCheckAPIView()
    #                 response = location_api_view.post(request)
    #                 if response.status_code != 200:
    #                     return response
    #         except:
    #             pass
    #         from employee.models import Employee

    #         # Always fetch employee from Employee table (employee_employee)
    #         employee = Employee.objects.get(employee_user_id=request.user)
    #         work_info = getattr(employee, "employee_work_info", None)
    #         import logging

    #         logger = logging.getLogger("attendance.debug")
    #         logger.warning(
    #             f"ClockIn Debug: user={request.user} id={request.user.id} username={getattr(request.user, 'username', None)}"
    #         )
    #         logger.warning(f"ClockIn Debug: employee={employee} work_info={work_info}")
    #         from django.utils import timezone as django_timezone

    #         datetime_now = django_timezone.localtime(django_timezone.now())
    #         if request.__dict__.get("datetime"):
    #             datetime_now = request.datetime
    #         from attendance.models import Attendance, AttendanceActivity

    #         date_today = datetime_now.date()
    #         now_time = datetime_now.strftime("%H:%M")  # 24-hour format for DB
    #         AttendanceActivity.objects.create(
    #             employee_id=employee,
    #             attendance_date=date_today,
    #             clock_in_date=date_today,
    #             clock_in=now_time,
    #             in_datetime=datetime_now,
    #         )
    #         attendance, _ = Attendance.objects.get_or_create(
    #             employee_id=employee,
    #             attendance_date=date_today,
    #             defaults={
    #                 "attendance_clock_in_date": date_today,
    #                 "attendance_clock_in": now_time,
    #             },
    #         )
    #         attendance.attendance_clock_in_date = date_today
    #         attendance.attendance_clock_in = now_time
    #         attendance.is_late_come = activity.is_late_come
    #         attendance.save()
    #         attendance.is_active = True
    #         attendance.save()

    #         employee.is_active = True
    #         employee.save()
    #         # Return 12-hour format in response
    #         return Response(
    #             {
    #                 "message": "Clocked-In",
    #                 "clock_in": datetime_now.strftime("%I:%M %p"),
    #                 "is_active": attendance.is_active,
    #             },
    #             status=200,
    #         )
    #     return Response({"message": "Already clocked-in"}, status=400)
    def post(self, request):
        if not request.user.employee_get.check_online():
            # ... [Geo-fencing logic remains the same] ...

            from django.utils import timezone as django_timezone

            from attendance.models import Attendance, AttendanceActivity
            from employee.models import Employee

            employee = Employee.objects.get(employee_user_id=request.user)
            datetime_now = django_timezone.localtime(django_timezone.now())

            if request.__dict__.get("datetime"):
                datetime_now = request.datetime

            date_today = datetime_now.date()
            now_time = datetime_now.strftime("%H:%M")
            resumed_clock_in = datetime_now.time()
            resumed_clock_in_datetime = datetime_now
            resumed_clock_in_date = date_today

            # 1. Create Activity (This triggers the model's save() logic)
            activity = AttendanceActivity.objects.create(
                employee_id=employee,
                attendance_date=date_today,
                clock_in_date=resumed_clock_in_date,
                clock_in=resumed_clock_in,
                in_datetime=resumed_clock_in_datetime,
            )

            # 2. Get/Create Attendance
            attendance, created = Attendance.objects.get_or_create(
                employee_id=employee,
                attendance_date=date_today,
                defaults={
                    "attendance_clock_in_date": date_today,
                    "attendance_clock_in": now_time,
                },
            )

            # 3. Update parent record
            if created or not attendance.attendance_clock_in:
                attendance.attendance_clock_in_date = resumed_clock_in_date
                attendance.attendance_clock_in = resumed_clock_in
            attendance.is_active = True

            # Manually sync the late come flag from activity to parent if needed
            attendance.is_late_come = activity.is_late_come
            attendance.save()

            employee.is_active = True
            employee.save()
            # Only update the flag if it hasn't been marked Late yet
            if activity.is_late_come:
                attendance.is_late_come = True
            attendance.save()
            # 4. Return the new fields in the response
            return Response(
                {
                    "message": "Clocked-In",
                    "clock_in": datetime_now.strftime("%I:%M %p"),
                    "is_active": attendance.is_active,
                    "is_late_come": activity.is_late_come,  # Added this
                    "is_early_out": activity.is_early_out,  # Added this
                },
                status=200,
            )
        return Response({"message": "Already clocked-in"}, status=400)


class ClockOutAPIView(APIView):
    """
    Allows authenticated employees to clock out, updating the latest attendance record and handling early outs.

    Methods:
        post(request): Records the clock-out time.
    """

    permission_classes = [IsAuthenticated]

    @document_api(
        operation_description="Record employee clock-out, updating the latest attendance record with exit time and handling early departures",
        tags=["Attendance"],
    )
    def post(self, request):
        # ... [Geo-fencing logic remains the same] ...

        from django.utils import timezone as django_timezone

        from attendance.models import Attendance, AttendanceActivity
        from employee.models import Employee

        employee = Employee.objects.get(employee_user_id=request.user)
        current_datetime = django_timezone.localtime(django_timezone.now())
        current_date = current_datetime.date()
        now_time = current_datetime.strftime("%H:%M")

        # Try to find the latest open AttendanceActivity for today
        open_activity = (
            AttendanceActivity.objects.filter(
                employee_id=employee,
                attendance_date=current_date,
                clock_out__isnull=True,
            )
            .order_by("-in_datetime")
            .first()
        )

        activity_instance = None  # To store which activity we worked on

        if open_activity:
            open_activity.clock_out = now_time
            open_activity.clock_out_date = current_date
            open_activity.out_datetime = current_datetime
            open_activity.save()  # This triggers the is_early_out logic in model
            activity_instance = open_activity
        else:
            activity_instance = AttendanceActivity.objects.create(
                employee_id=employee,
                attendance_date=current_date,
                clock_in_date=current_date,
                clock_in=now_time,
                in_datetime=current_datetime,
                clock_out_date=current_date,
                clock_out=now_time,
                out_datetime=current_datetime,
            )  # This triggers the is_early_out logic in model

        # Update or create Attendance record
        attendance, _ = Attendance.objects.get_or_create(
            employee_id=employee,
            attendance_date=current_date,
            defaults={
                "attendance_clock_in_date": current_date,
                "attendance_clock_in": now_time,
            },
        )
        attendance.attendance_clock_out = now_time
        attendance.attendance_clock_out_date = current_date
        attendance.is_active = False

        # Optional: Sync the early out flag to the main Attendance record
        attendance.is_early_out = activity_instance.is_early_out
        attendance.save()

        employee.is_active = False
        employee.save()
        # Only update Early Out if this is actually the last activity
        if activity_instance.is_early_out:
            attendance.is_early_out = True
        else:
            # If this isn't an early out anymore (because of a newer punch),
            # we might need to reset it.
            attendance.is_early_out = False
        attendance.save()
        return Response(
            {
                "message": "Clocked-Out",
                "clock_out": current_datetime.strftime("%I:%M %p"),
                "is_active": attendance.is_active,
                "earlyout": activity_instance.is_early_out,  # Status from model logic
                "is_late_come": activity_instance.is_late_come,  # Just for completeness
            },
            status=200,
        )


from datetime import datetime, time

from employee.models import EmployeeWorkInformation


class AttendanceView(APIView):
    """
    Handles CRUD operations for attendance records.

    Methods:
        get_queryset(request, type): Returns filtered attendance records.
        get(request, pk=None, type=None): Retrieves a specific record or a list of records.
        post(request): Creates a new attendance record.
        put(request, pk): Updates an existing attendance record.
        delete(request, pk): Deletes an attendance record and adjusts related overtime if needed.
    """

    # time thresholds for marking late/early
    LATE_COME_THRESHOLD = time(10, 30)
    EARLY_OUT_THRESHOLD = time(18, 30)

    permission_classes = [IsAuthenticated]
    filterset_class = AttendanceFilters

    def get_queryset(self, request=None, type=None):
        # Handle schema generation for DRF-YASG
        if getattr(self, "swagger_fake_view", False) or request is None:
            return Attendance.objects.none()
        if type == "ot":

            condition = AttendanceValidationCondition.objects.first()
            minot = strtime_seconds("00:30")
            if condition is not None:
                minot = strtime_seconds(condition.minimum_overtime_to_approve)
                queryset = Attendance.objects.filter(
                    overtime_second__gte=minot,
                    attendance_validated=True,
                )

        elif type == "validated":
            queryset = Attendance.objects.filter(attendance_validated=True)
        elif type == "non-validated":
            queryset = Attendance.objects.filter(attendance_validated=False)
        else:
            queryset = Attendance.objects.all()
        user = request.user
        # checking user level permissions
        perm = "attendance.view_attendance"
        queryset = permission_based_queryset(user, perm, queryset, user_obj=True)
        return queryset

    @document_api(
        operation_description="Get attendance records for a specific record or list all attendance records with filtering by date, employee, status, and pagination",
        tags=["Attendance"],
    )
    # def get(self, request, pk=None, type=None):
    #     # individual object workflow
    #     if pk:
    #         attendance = get_object_or_404(Attendance, pk=pk)
    #         serializer = AttendanceSerializer(instance=attendance)
    #         return Response(serializer.data, status=200)
    #     # permission based querysete
    #     attendances = self.get_queryset(request, type)
    #     # filtering queryset
    #     attendances_filter_queryset = self.filterset_class(
    #         request.GET, queryset=attendances
    #     ).qs
    #     # Custom filter: only return employees whose attendance is not validated
    #     if request.GET.get("validated") == "false":
    #         attendances_filter_queryset = attendances_filter_queryset.filter(attendance_validated=False)
    #     field_name = request.GET.get("groupby_field", None)
    #     if field_name:
    #         url = request.build_absolute_uri()
    #         return groupby_queryset(
    #             request, url, field_name, attendances_filter_queryset
    #         )
    #     # pagination workflow
    #     paginater = PageNumberPagination()
    #     page = paginater.paginate_queryset(attendances_filter_queryset, request)
    #     serializer = AttendanceSerializer(page, many=True)
    #     return paginater.get_paginated_response(serializer.data)

    def get(self, request, pk=None, type=None):
        # single record
        if pk:
            attendance = get_object_or_404(Attendance, pk=pk)
            data = self._attendance_response(attendance)
            return Response(data, status=200)

        attendances = self.get_queryset(request, type)
        attendances_filter_queryset = self.filterset_class(
            request.GET, queryset=attendances
        ).qs

        validated_param = request.GET.get("validated")
        if validated_param == "false":
            attendances_filter_queryset = attendances_filter_queryset.filter(
                attendance_validated=False
            )
        elif validated_param == "true":
            attendances_filter_queryset = attendances_filter_queryset.filter(
                attendance_validated=True
            )

        field_name = request.GET.get("groupby_field")
        if field_name:
            url = request.build_absolute_uri()
            return groupby_queryset(
                request, url, field_name, attendances_filter_queryset
            )

        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(attendances_filter_queryset, request)
        data = [self._attendance_response(att) for att in page]
        return paginator.get_paginated_response(data)

    def _as_time(self, value):
        if value is None:
            return None
        if isinstance(value, time):
            return value
        if isinstance(value, str):
            for fmt in ("%H:%M:%S", "%H:%M"):
                try:
                    return datetime.strptime(value, fmt).time()
                except ValueError:
                    continue
        # fallback: try converting stringified value
        try:
            return datetime.strptime(str(value), "%H:%M:%S").time()
        except Exception:
            return None

    def _attendance_response(self, att):
        emp = att.employee_id
        work_info = getattr(emp, "employee_work_info", None)

        shift = None
        if work_info:
            if work_info.shift_id:
                # ✅ PRIMARY SOURCE (correct relational data)
                shift = str(work_info.shift_id)
            else:
                # ✅ FALLBACK (label field)
                shift = work_info.Shift_Name

        work_type = None
        if work_info:
            if work_info.work_type_id:
                work_type = str(work_info.work_type_id)
            else:
                work_type = work_info.Work_Type_Name
        day = att.attendance_date.strftime("%A") if att.attendance_date else None

        # compute late/early flags
        check_in = self._as_time(att.attendance_clock_in)
        check_out = self._as_time(att.attendance_clock_out)
        is_late = check_in is not None and check_in > self.LATE_COME_THRESHOLD
        is_early = check_out is not None and check_out < self.EARLY_OUT_THRESHOLD

        return {
            "id": att.id,
            "employee_name": (
                f"{emp.employee_first_name} {emp.employee_last_name}" if emp else None
            ),
            "date": str(att.attendance_date) if att.attendance_date else None,
            "day": day,
            "check_in": (
                str(att.attendance_clock_in) if att.attendance_clock_in else None
            ),
            "in_date": (
                str(att.attendance_clock_in_date)
                if att.attendance_clock_in_date
                else None
            ),
            "check_out": (
                str(att.attendance_clock_out) if att.attendance_clock_out else None
            ),
            "out_date": (
                str(att.attendance_clock_out_date)
                if att.attendance_clock_out_date
                else None
            ),
            "shift": shift,
            "work_type": work_type,
            "min_hour": att.minimum_hour,
            "at_work": att.attendance_worked_hour,
            "pending_hour": (
                att.hours_pending() if hasattr(att, "hours_pending") else None
            ),
            "overtime": att.attendance_overtime,
            "latecome": is_late,
            "earlyout": is_early,
        }

    @manager_permission_required("attendance.add_attendance")
    @document_api(
        operation_description="Create a new attendance record for an employee",
        tags=["Attendance"],
    )
    def post(self, request):
        serializer = AttendanceSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        employee_id = request.data.get("employee_id")
        attendance_date = request.data.get("attendance_date", date.today())
        if Attendance.objects.filter(
            employee_id=employee_id, attendance_date=attendance_date
        ).exists():
            return Response(
                {
                    "error": [
                        "Attendance for this employee on the current date already exists."
                    ]
                },
                status=400,
            )
        return Response(serializer.errors, status=400)

    @method_decorator(permission_required("attendance.change_attendance"))
    @document_api(
        operation_description="Update an existing attendance record",
        tags=["Attendance"],
    )
    def put(self, request, pk):
        try:
            attendance = Attendance.objects.get(id=pk)
        except Attendance.DoesNotExist:
            return Response({"detail": "Attendance record not found."}, status=404)

        serializer = AttendanceSerializer(instance=attendance, data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)

        # Customize error message for unique constraint
        serializer_errors = serializer.errors
        if "non_field_errors" in serializer.errors:
            unique_error_msg = (
                "The fields employee_id, attendance_date must make a unique set."
            )
            if unique_error_msg in serializer.errors["non_field_errors"]:
                serializer_errors = {
                    "non_field_errors": [
                        "The employee already has attendance on this date."
                    ]
                }
        return Response(serializer_errors, status=400)

    @method_decorator(permission_required("attendance.delete_attendance"))
    @document_api(
        operation_description="Delete an attendance record by pk or all records by employee_id (admin only). Automatically adjusts related overtime if applicable.",
        tags=["Attendance"],
    )
    def delete(self, request, pk=None):
        # Allow admin/staff to delete all attendance records for a given employee_id via query param
        employee_id = request.query_params.get("employee_id")
        user = request.user
        if employee_id:
            # Only allow admin/staff
            if not (user.is_superuser or user.is_staff):
                return Response(
                    {"error": "You do not have permission to delete by employee_id."},
                    status=403,
                )
            attendances = Attendance.objects.filter(employee_id=employee_id)
            deleted_count = 0
            errors = []
            for attendance in attendances:
                month = attendance.attendance_date.strftime("%B").lower()
                overtime = attendance.employee_id.employee_overtime.filter(
                    month=month
                ).last()
                if overtime is not None and attendance.attendance_overtime_approve:
                    total_overtime = strtime_seconds(overtime.overtime)
                    attendance_overtime_seconds = strtime_seconds(
                        attendance.attendance_overtime
                    )
                    if total_overtime > attendance_overtime_seconds:
                        total_overtime = total_overtime - attendance_overtime_seconds
                    else:
                        total_overtime = attendance_overtime_seconds - total_overtime
                    overtime.overtime = format_time(total_overtime)
                    overtime.save()
                try:
                    attendance.delete()
                    deleted_count += 1
                except Exception as error:
                    errors.append(str(error))
            return Response({"deleted": deleted_count, "errors": errors}, status=200)
        # Default: delete by pk (single record)
        if pk is None:
            return Response(
                {"error": "pk or employee_id required for deletion."}, status=400
            )
        try:
            attendance = Attendance.objects.get(id=pk)
        except Attendance.DoesNotExist:
            return Response({"error": "Attendance record not found."}, status=404)
        month = attendance.attendance_date.strftime("%B").lower()
        overtime = attendance.employee_id.employee_overtime.filter(month=month).last()
        if overtime is not None and attendance.attendance_overtime_approve:
            total_overtime = strtime_seconds(overtime.overtime)
            attendance_overtime_seconds = strtime_seconds(
                attendance.attendance_overtime
            )
            if total_overtime > attendance_overtime_seconds:
                total_overtime = total_overtime - attendance_overtime_seconds
            else:
                total_overtime = attendance_overtime_seconds - total_overtime
            overtime.overtime = format_time(total_overtime)
            overtime.save()
        try:
            attendance.delete()
            return Response({"status": "deleted"}, status=200)
        except Exception as error:
            return Response({"error": str(error)}, status=400)


class ValidateAttendanceView(APIView):
    def patch(self, request, pk):
        attendance_obj = Attendance.objects.filter(id=pk).first()
        if not attendance_obj:
            return Response({"error": "Attendance record not found."}, status=404)
        if attendance_obj.attendance_validated:
            return Response({"message": "Attendance already validated."}, status=200)
        attendance_obj.attendance_validated = True
        attendance_obj.save()
        try:
            notify.send(
                request.user.employee_get,
                recipient=attendance_obj.employee_id.employee_user_id,
                verb=f"Your attendance for the date {attendance_obj.attendance_date} is validated",
                verb_ar=f"تم تحقيق حضورك في تاريخ {attendance_obj.attendance_date}",
                verb_de=f"Deine Anwesenheit für das Datum {attendance_obj.attendance_date} ist bestätigt.",
                verb_es=f"Se valida tu asistencia para la fecha {attendance_obj.attendance_date}.",
                verb_fr=f"Votre présence pour la date {attendance_obj.attendance_date} est validée.",
                redirect="/attendance/view-my-attendance",
                icon="checkmark",
                api_redirect=f"/api/attendance/attendance?employee_id{attendance_obj.employee_id}",
            )
        except Exception:
            pass
        return Response({"message": "Attendance validated successfully."}, status=200)

    """
    Validates an attendance record and sends a notification to the employee.

    Method:
        put(request, pk): Marks the attendance as validated and notifies the employee.
    """

    permission_classes = [IsAuthenticated]

    @document_api(
        operation_description="Validate an attendance record and send notification to the employee",
        tags=["Attendance"],
    )
    def put(self, request, pk):
        attendance = Attendance.objects.filter(id=pk).update(attendance_validated=True)
        attendance = Attendance.objects.filter(id=pk).first()
        try:
            notify.send(
                request.user.employee_get,
                recipient=attendance.employee_id.employee_user_id,
                verb=f"Your attendance for the date {attendance.attendance_date} is validated",
                verb_ar=f"تم تحقيق حضورك في تاريخ {attendance.attendance_date}",
                verb_de=f"Deine Anwesenheit für das Datum {attendance.attendance_date} ist bestätigt.",
                verb_es=f"Se valida tu asistencia para la fecha {attendance.attendance_date}.",
                verb_fr=f"Votre présence pour la date {attendance.attendance_date} est validée.",
                redirect="/attendance/view-my-attendance",
                icon="checkmark",
                api_redirect=f"/api/attendance/attendance?employee_id{attendance.employee_id}",
            )
        except:
            pass
        return Response(status=200)


class OvertimeApproveView(APIView):
    """
    Approves overtime for an attendance record and sends a notification to the employee.

    Method:
        put(request, pk): Marks the overtime as approved and notifies the employee.
    """

    permission_classes = [IsAuthenticated]

    @document_api(
        operation_description="Approve overtime for an attendance record and send notification to the employee",
        tags=["Attendance"],
    )
    def put(self, request, pk):
        try:
            attendance = Attendance.objects.filter(id=pk).update(
                attendance_overtime_approve=True
            )
        except Exception as E:
            return Response({"error": str(E)}, status=400)

        attendance = Attendance.objects.filter(id=pk).first()
        try:
            notify.send(
                request.user.employee_get,
                recipient=attendance.employee_id.employee_user_id,
                verb=f"Your {attendance.attendance_date}'s attendance overtime approved.",
                verb_ar=f"تمت الموافقة على إضافة ساعات العمل الإضافية لتاريخ {attendance.attendance_date}.",
                verb_de=f"Die Überstunden für den {attendance.attendance_date} wurden genehmigt.",
                verb_es=f"Se ha aprobado el tiempo extra de asistencia para el {attendance.attendance_date}.",
                verb_fr=f"Les heures supplémentaires pour la date {attendance.attendance_date} ont été approuvées.",
                redirect="/attendance/attendance-overtime-view",
                icon="checkmark",
                api_redirect="/api/attendance/attendance-hour-account/",
            )
        except:
            pass
        return Response(status=200)


class AttendanceRequestView(APIView):
    """
    Handles requests for creating, updating, and viewing attendance records.

    Methods:
        get(request, pk=None): Retrieves a specific attendance request by `pk` or a filtered list of requests.
        post(request): Creates a new attendance request.
        put(request, pk): Updates an existing attendance request.
    """

    serializer_class = AttendanceRequestSerializer
    permission_classes = [IsAuthenticated]

    @document_api(
        operation_description="Get attendance requests - retrieve specific request or list all requests with filtering",
        tags=["Attendance"],
    )
    def get(self, request, pk=None):
        if pk:
            attendance = Attendance.objects.get(id=pk)
            serializer = AttendanceRequestSerializer(instance=attendance)
            return Response(serializer.data, status=200)

        requests = Attendance.objects.filter(
            is_validate_request=True,
        )
        requests = filtersubordinates(
            request=request,
            perm="attendance.view_attendance",
            queryset=requests,
        )
        requests = requests | Attendance.objects.filter(
            employee_id__employee_user_id=request.user,
            is_validate_request=True,
        )
        request_filtered_queryset = AttendanceFilters(request.GET, requests).qs
        field_name = request.GET.get("groupby_field", None)
        if field_name:
            # groupby workflow
            url = request.build_absolute_uri()
            return groupby_queryset(request, url, field_name, request_filtered_queryset)

        pagenation = PageNumberPagination()
        page = pagenation.paginate_queryset(request_filtered_queryset, request)
        serializer = self.serializer_class(page, many=True)
        return pagenation.get_paginated_response(serializer.data)

    @document_api(
        operation_description="Create a new attendance request (absence validation, work type change, etc.)",
        tags=["Attendance"],
    )
    def post(self, request):
        from attendance.forms import NewRequestForm

        form = NewRequestForm(data=request.data)
        if form.is_valid():
            work_type = form.cleaned_data.get("work_type_id")

            if not WorkType.objects.filter(pk=getattr(work_type, "pk", None)).exists():
                form.cleaned_data["work_type_id"] = None

            if form.new_instance is not None:
                form.new_instance.save()

            return Response(form.data, status=200)
        employee_id = request.data.get("employee_id")
        attendance_date = request.data.get("attendance_date", date.today())
        if Attendance.objects.filter(
            employee_id=employee_id, attendance_date=attendance_date
        ).exists():
            return Response(
                {error: list(message) for error, message in form.errors.items()},
                status=400,
            )
        return Response(form.errors, status=404)

    def put(self, request, pk):
        from attendance.forms import AttendanceRequestForm

        attendance = Attendance.objects.get(id=pk)
        form = AttendanceRequestForm(data=request.data, instance=attendance)
        if form.is_valid():
            attendance = Attendance.objects.get(id=form.instance.pk)
            instance = form.save()
            instance.employee_id = attendance.employee_id
            instance.id = attendance.id
            work_type = form.cleaned_data.get("work_type_id")

            if not WorkType.objects.filter(pk=getattr(work_type, "pk", None)).exists():
                form.cleaned_data["work_type_id"] = None
            if attendance.request_type != "create_request":
                attendance.requested_data = json.dumps(instance.serialize())
                attendance.request_description = instance.request_description
                # set the user level validation here
                attendance.is_validate_request = True
                attendance.save()
            else:
                instance.is_validate_request_approved = False
                instance.is_validate_request = True
                instance.save()
            return Response(form.data, status=200)
        return Response(form.errors, status=404)


class AttendanceRequestApproveView(APIView):
    """
    Approves and updates an attendance request.

    Method:
        put(request, pk): Approves the attendance request, updates attendance records, and handles related activities.
    """

    permission_classes = [IsAuthenticated]

    @manager_permission_required("attendance.change_attendance")
    def put(self, request, pk):
        try:
            attendance = Attendance.objects.get(id=pk)
            prev_attendance_date = attendance.attendance_date
            prev_attendance_clock_in_date = attendance.attendance_clock_in_date
            prev_attendance_clock_in = attendance.attendance_clock_in
            attendance.attendance_validated = True
            attendance.is_validate_request_approved = True
            attendance.is_validate_request = False
            attendance.request_description = None
            attendance.save()
            if attendance.requested_data is not None:
                requested_data = json.loads(attendance.requested_data)
                requested_data["attendance_clock_out"] = (
                    None
                    if requested_data["attendance_clock_out"] == "None"
                    else requested_data["attendance_clock_out"]
                )
                requested_data["attendance_clock_out_date"] = (
                    None
                    if requested_data["attendance_clock_out_date"] == "None"
                    else requested_data["attendance_clock_out_date"]
                )
                Attendance.objects.filter(id=pk).update(**requested_data)
                # DUE TO AFFECT THE OVERTIME CALCULATION ON SAVE METHOD, SAVE THE INSTANCE ONCE MORE
                attendance = Attendance.objects.get(id=pk)
                attendance.save()
            if (
                attendance.attendance_clock_out is None
                or attendance.attendance_clock_out_date is None
            ):
                attendance.attendance_validated = True
                activity = AttendanceActivity.objects.filter(
                    employee_id=attendance.employee_id,
                    attendance_date=prev_attendance_date,
                    clock_in_date=prev_attendance_clock_in_date,
                    clock_in=prev_attendance_clock_in,
                )
                if activity:
                    activity.update(
                        employee_id=attendance.employee_id,
                        attendance_date=attendance.attendance_date,
                        clock_in_date=attendance.attendance_clock_in_date,
                        clock_in=attendance.attendance_clock_in,
                    )

                else:
                    AttendanceActivity.objects.create(
                        employee_id=attendance.employee_id,
                        attendance_date=attendance.attendance_date,
                        clock_in_date=attendance.attendance_clock_in_date,
                        clock_in=attendance.attendance_clock_in,
                    )
        except Exception as E:
            return Response({"error": str(E)}, status=400)
        return Response({"status": "approved"}, status=200)


class AttendanceRequestCancelView(APIView):
    """
    Cancels an attendance request.

    Method:
        put(request, pk): Cancels the attendance request, resetting its status and data, and deletes the request if it was a create request.
    """

    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        try:
            attendance = Attendance.objects.get(id=pk)
            if (
                attendance.employee_id.employee_user_id == request.user
                or is_reportingmanager(request)
                or request.user.has_perm("attendance.change_attendance")
            ):
                attendance.is_validate_request_approved = False
                attendance.is_validate_request = False
                attendance.request_description = None
                attendance.requested_data = None
                attendance.request_type = None

                attendance.save()
                if attendance.request_type == "create_request":
                    attendance.delete()
        except Exception as E:
            return Response({"error": str(E)}, status=400)
        return Response({"status": "success"}, status=200)


class AttendanceOverTimeView(APIView):
    """
    Manages CRUD operations for attendance overtime records.

    Methods:
        get(request, pk=None): Retrieves a specific overtime record by `pk` or a list of records with filtering and pagination.
        post(request): Creates a new overtime record.
        put(request, pk): Updates an existing overtime record.
        delete(request, pk): Deletes a overtime record.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        if pk:
            attendance_ot = get_object_or_404(AttendanceOverTime, pk=pk)
            serializer = AttendanceOverTimeSerializer(attendance_ot)
            return Response(serializer.data, status=200)

        filterset_class = AttendanceOverTimeFilter(request.GET)
        queryset = filterset_class.qs
        self_account = queryset.filter(employee_id__employee_user_id=request.user)
        permission_based_queryset = filtersubordinates(
            request, queryset, "attendance.view_attendanceovertime"
        )
        queryset = permission_based_queryset | self_account
        field_name = request.GET.get("groupby_field", None)
        if field_name:
            # groupby workflow
            url = request.build_absolute_uri()
            return groupby_queryset(request, url, field_name, queryset)

        pagenation = PageNumberPagination()
        page = pagenation.paginate_queryset(queryset, request)
        serializer = AttendanceOverTimeSerializer(page, many=True)
        return pagenation.get_paginated_response(serializer.data)

    @manager_permission_required("attendance.add_attendanceovertime")
    def post(self, request):
        serializer = AttendanceOverTimeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)

    @manager_permission_required("attendance.change_attendanceovertime")
    def put(self, request, pk):
        attendance_ot = get_object_or_404(AttendanceOverTime, pk=pk)
        serializer = AttendanceOverTimeSerializer(
            instance=attendance_ot, data=request.data
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)

    @method_decorator(permission_required("attendance.delete_attendanceovertime"))
    def delete(self, request, pk):
        attendance = get_object_or_404(AttendanceOverTime, pk=pk)
        attendance.delete()

        return Response({"message": "Overtime deleted successfully"}, status=204)


class LateComeEarlyOutView(APIView):
    """
    Handles retrieval and deletion of late come and early out records.

    Methods:
        get(request, pk=None): Retrieves a list of late come and early out records with filtering.
        delete(request, pk=None): Deletes a specific late come or early out record by `pk`.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        data = LateComeEarlyOutFilter(request.GET)
        serializer = AttendanceLateComeEarlyOutSerializer(data.qs, many=True)
        return Response(serializer.data, status=200)

    def delete(self, request, pk=None):
        attendance = get_object_or_404(AttendanceLateComeEarlyOut, pk=pk)
        attendance.delete()
        return Response({"message": "Attendance deleted successfully"}, status=204)


class AttendanceActivityView(APIView):
    """
    Retrieves attendance activity records.

    Method:
        get(request, pk=None): Retrieves a list of all attendance activity records.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        user = request.user

        # If user is admin/staff, show all records
        if user.is_staff or user.is_superuser:
            queryset = AttendanceActivity.objects.all()
        else:
            # Otherwise, show only records for the employee
            employee_id = getattr(user, "employee_get", None)
            if employee_id:
                queryset = AttendanceActivity.objects.filter(employee_id=employee_id.id)
            else:
                queryset = AttendanceActivity.objects.none()
        serializer = AttendanceActivitySerializer(queryset, many=True)
        return Response(serializer.data, status=200)

    def delete(self, request, pk):
        if not pk:
            return Response({"error": "pk is required for deletion."}, status=400)

        attendance = get_object_or_404(AttendanceActivity, pk=pk)
        attendance.delete()
        return Response({"message": "Attendance deleted successfully"}, status=204)


class TodayAttendance(APIView):
    """
    Provides the ratio of marked attendances to expected attendances for the current day.

    Method:
        get(request): Calculates and returns the attendance ratio for today.
    """

    permission_classes = [IsAuthenticated]

    @document_api(
        operation_description="Get the attendance ratio (marked vs expected) for today",
        tags=["Attendance"],
    )
    def get(self, request):

        today = datetime.today()
        week_day = today.strftime("%A").lower()

        on_time = find_on_time(request, today=today, week_day=week_day)
        late_come = find_late_come(start_date=today)
        late_come_obj = len(late_come)

        marked_attendances = late_come_obj + on_time

        expected_attendances = find_expected_attendances(week_day=week_day)
        marked_attendances_ratio = 0
        if expected_attendances != 0:
            marked_attendances_ratio = (
                f"{(marked_attendances / expected_attendances) * 100:.2f}"
            )

        return Response(
            {"marked_attendances_ratio": marked_attendances_ratio}, status=200
        )


class OfflineEmployeesCountView(APIView):
    """
    Retrieves the count of active employees who have not clocked in today.

    Method:
        get(request): Returns the number of active employees who are not yet clocked in.
    """

    permission_classes = [IsAuthenticated]

    @document_api(
        operation_description="Get count of active employees who have not yet clocked in today",
        tags=["Attendance"],
    )
    def get(self, request):
        is_manager = (
            EmployeeWorkInformation.objects.filter(
                reporting_manager_id=request.user.employee_get
            )
            .only("id")
            .exists()
        )

        if request.user.has_perm("employee.view_enployee") or is_manager:
            count = (
                EmployeeFilter({"not_in_yet": date.today()})
                .qs.exclude(employee_work_info__isnull=True)
                .filter(is_active=True)
                .count()
            )
            return Response({"count": count}, status=200)
        return Response(
            {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
        )


class OfflineEmployeesListView(APIView):
    """
    Lists active employees who have not clocked in today, including their leave status.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        employee = getattr(user, "employee_get", None)
        today = date.today()

        # Manager access: get employees reporting to current user
        managed_employee_ids = EmployeeWorkInformation.objects.filter(
            reporting_manager_id=employee
        ).values_list("employee_id", flat=True)

        # Superusers or users with view permission see all employees
        if user.has_perm("employee.view_employee"):
            base_queryset = Employee.objects.all()
        elif managed_employee_ids.exists():
            base_queryset = Employee.objects.filter(id__in=managed_employee_ids)
        else:
            return Response(
                {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
            )

        # Apply filtering for offline employees
        filtered_qs = (
            EmployeeFilter({"not_in_yet": today}, queryset=base_queryset)
            .qs.exclude(employee_work_info__isnull=True)
            .filter(is_active=True)
            .select_related("employee_work_info")  # optimize joins
        )

        # Get leave status for the filtered employees
        leave_status = self.get_leave_status(filtered_qs)

        pagenation = PageNumberPagination()
        page = pagenation.paginate_queryset(leave_status, request)
        return pagenation.get_paginated_response(page)

    def get_leave_status(self, queryset):

        today = date.today()
        queryset = queryset.distinct()
        # Annotate each employee with their leave status
        employees_with_leave_status = queryset.annotate(
            leave_status=Case(
                # Define different cases based on leave requests and attendance
                When(
                    leaverequest__start_date__lte=today,
                    leaverequest__end_date__gte=today,
                    leaverequest__status="approved",
                    then=Value("On Leave"),
                ),
                When(
                    leaverequest__start_date__lte=today,
                    leaverequest__end_date__gte=today,
                    leaverequest__status="requested",
                    then=Value("Waiting Approval"),
                ),
                When(
                    leaverequest__start_date__lte=today,
                    leaverequest__end_date__gte=today,
                    then=Value("Canceled / Rejected"),
                ),
                When(
                    employee_attendances__attendance_date=today, then=Value("Working")
                ),
                default=Value("Expected working"),  # Default status
                output_field=CharField(),
            ),
            job_position_id=F("employee_work_info__job_position_id"),
        ).values(
            "employee_first_name",
            "employee_last_name",
            "leave_status",
            "employee_profile",
            "id",
            "job_position_id",
        )

        for employee in employees_with_leave_status:

            if employee["employee_profile"]:
                employee["employee_profile"] = (
                    settings.MEDIA_URL + employee["employee_profile"]
                )
        return employees_with_leave_status


class CheckingStatus(APIView):
    """
    Checks and provides the current attendance status for the authenticated user.

    Method:
        get(request): Returns the attendance status, duration at work, and clock-in time if available.
    """

    permission_classes = [IsAuthenticated]

    @classmethod
    def _format_seconds(cls, seconds):
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def get(self, request):
        attendance_activity = (
            AttendanceActivity.objects.filter(employee_id=request.user.employee_get)
            .order_by("-id")
            .first()
        )
        duration = None
        work_seconds = request.user.employee_get.get_forecasted_at_work()[
            "forecasted_at_work_seconds"
        ]
        duration = CheckingStatus._format_seconds(int(work_seconds))
        status = False
        clock_in_time = None

        today = datetime.now().date()
        attendance_activity_first = (
            AttendanceActivity.objects.filter(
                employee_id=request.user.employee_get, clock_in_date=today
            )
            .order_by("in_datetime")
            .first()
        )
        if attendance_activity:
            try:
                clock_in_time = attendance_activity_first.clock_in.strftime("%I:%M %p")
                if attendance_activity.clock_out_date:
                    status = False
                else:
                    status = True
                    return Response(
                        {
                            "status": status,
                            "duration": duration,
                            "clock_in": clock_in_time,
                        },
                        status=200,
                    )
            except:
                return Response(
                    {"status": status, "duration": duration, "clock_in": clock_in_time},
                    status=200,
                )
        return Response(
            {"status": status, "duration": duration, "clock_in_time": clock_in_time},
            status=200,
        )


class MailTemplateView(APIView):
    """
    Retrieves a list of recruitment mail templates.

    Method:
        get(request): Returns all recruitment mail templates.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        instances = HorillaMailTemplate.objects.all()
        serializer = MailTemplateSerializer(instances, many=True)
        return Response(serializer.data, status=200)


class ConvertedMailTemplateConvert(APIView):
    """
    Renders a recruitment mail template with data from a specified employee.

    Method:
        put(request): Renders the mail template body with employee and user data and returns the result.
    """

    permission_classes = [IsAuthenticated]

    def put(self, request):
        template_id = request.data.get("template_id", None)
        employee_id = request.data.get("employee_id", None)
        employee = Employee.objects.filter(id=employee_id).first()
        bdy = HorillaMailTemplate.objects.filter(id=template_id).first()
        template_bdy = template.Template(bdy.body)
        context = template.Context(
            {"instance": employee, "self": request.user.employee_get}
        )
        render_bdy = template_bdy.render(context)
        return Response(render_bdy)


class OfflineEmployeeMailsend(APIView):
    """
    Sends an email with attachments and rendered templates to a specified employee.

    Method:
        post(request): Renders email templates with employee and user data, attaches files, and sends the email.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        employee_id = request.POST.get("employee_id")
        subject = request.POST.get("subject", "")
        bdy = request.POST.get("body", "")
        other_attachments = request.FILES.getlist("other_attachments")
        attachments = [
            (file.name, file.read(), file.content_type) for file in other_attachments
        ]
        email_backend = ConfiguredEmailBackend()
        host = email_backend.dynamic_username
        employee = Employee.objects.get(id=employee_id)
        template_attachment_ids = request.POST.getlist("template_attachments")
        bodys = list(
            HorillaMailTemplate.objects.filter(
                id__in=template_attachment_ids
            ).values_list("body", flat=True)
        )
        for html in bodys:
            # due to not having solid template we first need to pass the context
            template_bdy = template.Template(html)
            context = template.Context(
                {"instance": employee, "self": request.user.employee_get}
            )
            render_bdy = template_bdy.render(context)
            attachments.append(
                (
                    "Document",
                    generate_pdf(render_bdy, {}, path=False, title="Document").content,
                    "application/pdf",
                )
            )

        template_bdy = template.Template(bdy)
        context = template.Context(
            {"instance": employee, "self": request.user.employee_get}
        )
        render_bdy = template_bdy.render(context)

        email = EmailMessage(
            subject,
            render_bdy,
            host,
            [employee.employee_work_info.email],
        )
        email.content_subtype = "html"

        email.attachments = attachments
        try:
            email.send()
            if employee.employee_work_info.email:
                return Response(f"Mail sent to {employee.get_full_name()}")
            else:
                return Response(f"Email not set for {employee.get_full_name()}")
        except Exception as e:
            return Response("Something went wrong")


class UserAttendanceView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserAttendanceDetailedSerializer

    def get(self, request):
        employee_id = request.user.employee_get.id

        attendance_queryset = Attendance.objects.filter(
            employee_id=employee_id
        ).order_by("-id")

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(attendance_queryset, request)

        serializer = self.serializer_class(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AttendanceTypeAccessCheck(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        employee_id = user.employee_get.id

        if user.has_perm("attendance.view_attendance"):
            return Response(status=200)

        is_manager = (
            EmployeeWorkInformation.objects.filter(reporting_manager_id=employee_id)
            .only("id")
            .exists()
        )

        if is_manager:
            return Response(status=200)

        return Response(
            {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
        )


class UserAttendanceDetailedView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        attendance = get_object_or_404(Attendance, pk=id)
        if attendance.employee_id == request.user.employee_get:
            serializer = UserAttendanceDetailedSerializer(attendance)
            return Response(serializer.data, status=200)
        return Response(
            {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
        )


class AttendanceWorkRecordsAPIView(APIView):
    """
    Returns a list of attendance work records for the authenticated user (or all, if admin).
    Optional query params: month (YYYY-MM), employee_id
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        qs = Attendance.objects.all()
        month = request.GET.get("month")
        employee_id = request.GET.get("employee_id")
        if not user.is_superuser and not user.is_staff:
            qs = qs.filter(employee_id=user.employee_get.id)
        if employee_id:
            qs = qs.filter(employee_id=employee_id)
        if month:
            try:
                year, month_num = map(int, month.split("-"))
                if month_num < 1 or month_num > 12:
                    raise ValueError("month out of range")
                qs = qs.filter(
                    attendance_date__year=year, attendance_date__month=month_num
                )
            except Exception:
                return Response(
                    {"error": "Invalid month format. Use YYYY-MM (e.g., 2026-03)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        qs = qs.order_by("-attendance_date")
        serializer = UserAttendanceDetailedSerializer(qs, many=True)
        return Response(serializer.data)
