"""
Dashboard API URLs
"""

from django.urls import path

from horilla_api.api_views.dashboard.views import (
    ActivitiesListAPIView,
    AttendanceListAPIView,
    AttendanceStatsAPIView,
    AttendanceTrendAPIView,
    DashboardOverviewAPIView,
    DashboardSummaryAPIView,
    DepartmentStatsAPIView,
    EmployeeDetailAPIView,
    EmployeeListAPIView,
    HoursChartAPIView,
    LeaveRequestListAPIView,
    MyAttendanceAPIView,
)

urlpatterns = [
    # Dashboard overview
    path("", DashboardOverviewAPIView.as_view(), name="api-dashboard-overview"),
    path("summary/", DashboardSummaryAPIView.as_view(), name="api-dashboard-summary"),
    # Attendance
    path("attendance/", AttendanceListAPIView.as_view(), name="api-attendance-list"),
    path(
        "attendance/stats/",
        AttendanceStatsAPIView.as_view(),
        name="api-attendance-stats",
    ),
    path(
        "attendance/trends/",
        AttendanceTrendAPIView.as_view(),
        name="api-attendance-trends",
    ),
    path("hours-chart/", HoursChartAPIView.as_view(), name="api-hours-chart"),
    # Employees
    path("employees/", EmployeeListAPIView.as_view(), name="api-employees-list"),
    path(
        "employees/<int:employee_id>/",
        EmployeeDetailAPIView.as_view(),
        name="api-employee-detail",
    ),
    path("me/", MyAttendanceAPIView.as_view(), name="api-my-attendance"),
    # Leave requests
    path("leaves/", LeaveRequestListAPIView.as_view(), name="api-leave-requests-list"),
    # Department statistics
    path(
        "departments/stats/",
        DepartmentStatsAPIView.as_view(),
        name="api-departments-stats",
    ),
    # Activities
    path("activities/", ActivitiesListAPIView.as_view(), name="api-activities-list"),
]
