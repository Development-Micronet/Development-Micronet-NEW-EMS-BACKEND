from django.urls import path

from horilla_api.api_views.attendance.attendance_hour_account_api import (
    AttendanceHourAccountAPIView,
)
from horilla_api.api_views.attendance.late_come_early_out_custom_api import (
    LateComeEarlyOutCustomAPIView,
)
from horilla_api.api_views.attendance.offline_employees_api import (
    OfflineEmployeesAPIView,
)
from horilla_api.api_views.attendance.permission_views import AttendancePermissionCheck
from horilla_api.api_views.attendance.views import *
from horilla_api.api_views.attendance.views import (
    OnBreakEmployeesAPIView,
    OnlineOfflineEmployeesAPIView,
)

urlpatterns = [
    path(
        "attendance/online-offline/",
        OnlineOfflineEmployeesAPIView.as_view(),
        name="attendance-online-offline-api",
    ),
    path(
        "attendance/bulk-validate/",
        AttendanceBulkValidateView.as_view(),
        name="attendance-bulk-validate",
    ),
    path(
        "attendance/import/",
        AttendanceImportAPIView.as_view(),
        name="attendance-import-api",
    ),
    path(
        "attendance/work-record-import/",
        WorkRecordImportAPIView.as_view(),
        name="work-record-import-api",
    ),
    path("overtime/pending/", OvertimePendingView.as_view(), name="overtime-pending"),
    path(
        "offline-employees/",
        OfflineEmployeesAPIView.as_view(),
        name="offline-employees-api",
    ),
    path(
        "attendance/on-break/",
        OnBreakEmployeesAPIView.as_view(),
        name="attendance-on-break-api",
    ),
    path("clock-in/", ClockInAPIView.as_view(), name="api-check-in"),
    path("clock-out/", ClockOutAPIView.as_view(), name="api-check-out"),
    path("attendance/", AttendanceView.as_view(), name="api-attendance-list"),
    path("attendance/<int:pk>", AttendanceView.as_view(), name="api-attendance-detail"),
    path(
        "attendance/list/<str:type>",
        AttendanceView.as_view(),
        name="api-attendance-list",
    ),
    path(
        "attendance-validate/employee/<int:employee_id>/",
        ValidateAttendanceByEmployeeView.as_view(),
    ),
    path("attendance-validate/<int:pk>", ValidateAttendanceView.as_view()),
    path(
        "attendance-request/",
        AttendanceRequestView.as_view(),
        name="api-attendance-request-view",
    ),
    path(
        "attendance-request/<int:pk>",
        AttendanceRequestView.as_view(),
        name="api-attendance-request-view",
    ),
    path(
        "attendance-request-approve/<int:pk>",
        AttendanceRequestApproveView.as_view(),
        name="api-",
    ),
    path(
        "attendance-request-cancel/<int:pk>",
        AttendanceRequestCancelView.as_view(),
        name="api-",
    ),
    path("overtime-approve/<int:pk>", OvertimeApproveView.as_view(), name="api-"),
    # Custom hour account API
    path(
        "attendance-hour-account/",
        AttendanceHourAccountAPIView.as_view(),
        name="attendance-hour-account-api",
    ),
    path(
        "attendance-hour-account/<int:pk>",
        AttendanceHourAccountAPIView.as_view(),
        name="attendance-hour-account-detail-api",
    ),
    path(
        "late-come-early-out-view/",
        LateComeEarlyOutCustomAPIView.as_view(),
        name="late-come-early-out-custom-api",
    ),
    path(
        "late-come-early-out-view/<int:pk>",
        LateComeEarlyOutCustomAPIView.as_view(),
        name="late-come-early-out-custom-detail-api",
    ),
    path("attendance-activity/", AttendanceActivityView.as_view(), name="api-"),
    path(
        "attendance-activity/<int:pk>/",
        AttendanceActivityView.as_view(),
        name="api-delete",
    ),
    # (import moved to top)
    path("today-attendance/", TodayAttendance.as_view(), name="api-"),
    path("offline-employees/count/", OfflineEmployeesCountView.as_view(), name="api-"),
    path("offline-employees/list/", OfflineEmployeesListView.as_view(), name="api-"),
    path("permission-check/attendance", AttendancePermissionCheck.as_view()),
    path("checking-in", CheckingStatus.as_view()),
    path("offline-employee-mail-send", OfflineEmployeeMailsend.as_view()),
    path("converted-mail-template", ConvertedMailTemplateConvert.as_view()),
    path("mail-templates", MailTemplateView.as_view()),
    path("my-attendance/", UserAttendanceView.as_view()),
    path("attendance-type-check/", AttendanceTypeAccessCheck.as_view()),
    path("my-attendance-detailed/<int:id>/", UserAttendanceDetailedView.as_view()),
    path(
        "attendance/work-records/",
        AttendanceWorkRecordsAPIView.as_view(),
        name="attendance-work-records-api",
    ),
]


class LateComeEarlyOutCustomAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        badge_id = request.query_params.get("Badge_id")
        attendance_date = request.query_params.get("Attendance_Date")
        record_id = request.query_params.get("Record_id")
        filters = {}
        if badge_id:
            filters["employee_id__badge_id"] = badge_id
        if attendance_date:
            filters["attendance_id__attendance_date"] = attendance_date
        if record_id:
            filters["id"] = record_id

        if pk is not None:
            try:
                obj = AttendanceLateComeEarlyOut.objects.select_related(
                    "employee_id", "attendance_id"
                ).get(pk=pk)
            except AttendanceLateComeEarlyOut.DoesNotExist:
                return Response({"detail": "Not found."}, status=404)
            attendance = obj.attendance_id
            employee = obj.employee_id
            result = {
                "Employee_name": f"{employee.employee_first_name} {employee.employee_last_name or ''}",
                "Badge_id": employee.badge_id,
                "Type": obj.type,
                "Attendance Date": str(attendance.attendance_date),
                "Check-In": str(attendance.attendance_clock_in),
                "In Date": str(attendance.attendance_clock_in_date),
                "Check-Out": str(attendance.attendance_clock_out),
                "Out Date": str(attendance.attendance_clock_out_date),
                "Min Hour": str(attendance.minimum_hour),
                "At Work": str(attendance.attendance_worked_hour),
                "Penalities": obj.get_penalties_count(),
                "Action": "View/Approve",
                "Record_id": obj.id,
            }
            return Response(result)

        user = request.user
        if user.is_superuser or user.is_staff:
            queryset = (
                AttendanceLateComeEarlyOut.objects.select_related(
                    "employee_id", "attendance_id"
                ).filter(**filters)
                if filters
                else AttendanceLateComeEarlyOut.objects.select_related(
                    "employee_id", "attendance_id"
                ).all()
            )
        else:
            employee = getattr(user, "employee_get", None)
            if employee is not None:
                queryset = (
                    AttendanceLateComeEarlyOut.objects.select_related(
                        "employee_id", "attendance_id"
                    ).filter(employee_id=employee, **filters)
                    if filters
                    else AttendanceLateComeEarlyOut.objects.select_related(
                        "employee_id", "attendance_id"
                    ).filter(employee_id=employee)
                )
            else:
                return Response([], status=200)
        results = []
        for obj in queryset:
            attendance = obj.attendance_id
            employee = obj.employee_id
            results.append(
                {
                    "Employee_name": f"{employee.employee_first_name} {employee.employee_last_name or ''}",
                    "Badge_id": employee.badge_id,
                    "Type": obj.type,
                    "Attendance Date": str(attendance.attendance_date),
                    "Check-In": str(attendance.attendance_clock_in),
                    "In Date": str(attendance.attendance_clock_in_date),
                    "Check-Out": str(attendance.attendance_clock_out),
                    "Out Date": str(attendance.attendance_clock_out_date),
                    "Min Hour": str(attendance.minimum_hour),
                    "At Work": str(attendance.attendance_worked_hour),
                    "Penalities": obj.get_penalties_count(),
                    "Action": "View/Approve",
                    "Record_id": obj.id,
                }
            )
        return Response(results)
