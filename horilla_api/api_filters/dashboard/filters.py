"""
Dashboard Filters for API endpoints
"""

from datetime import date, datetime

import django_filters
from django.db.models import Q

from attendance.models import Attendance
from employee.models import Department, Employee
from leave.models import LeaveRequest


class EmployeeFilter(django_filters.FilterSet):
    """Filter employees by various criteria"""

    search = django_filters.CharFilter(
        method="filter_search", label="Search by name, email, or badge"
    )
    department = django_filters.NumberFilter(
        field_name="department_id__id", label="Department ID"
    )
    company = django_filters.NumberFilter(
        field_name="company_id__id", label="Company ID"
    )
    is_active = django_filters.BooleanFilter(field_name="is_active", label="Active")
    status = django_filters.CharFilter(
        field_name="employee_work_status", label="Work Status"
    )

    class Meta:
        model = Employee
        fields = ["department", "company", "is_active", "status"]

    def filter_search(self, queryset, name, value):
        """Search in multiple fields"""
        return queryset.filter(
            Q(employee_first_name__icontains=value)
            | Q(employee_last_name__icontains=value)
            | Q(email__icontains=value)
            | Q(badge_id__icontains=value)
        )


class AttendanceFilter(django_filters.FilterSet):
    """Filter attendance records"""

    date_from = django_filters.DateFilter(
        field_name="attendance_date", lookup_expr="gte", label="From Date"
    )
    date_to = django_filters.DateFilter(
        field_name="attendance_date", lookup_expr="lte", label="To Date"
    )
    employee = django_filters.NumberFilter(
        field_name="employee_id__id", label="Employee ID"
    )
    department = django_filters.NumberFilter(
        field_name="employee_id__department_id__id", label="Department ID"
    )
    company = django_filters.NumberFilter(
        field_name="employee_id__company_id__id", label="Company ID"
    )
    status = django_filters.CharFilter(
        method="filter_status", label="Status (present/absent)"
    )
    validated = django_filters.BooleanFilter(
        field_name="attendance_validated", label="Validated"
    )

    class Meta:
        model = Attendance
        fields = ["employee", "department", "company", "validated"]

    def filter_status(self, queryset, name, value):
        """Filter by attendance status"""
        if value.lower() == "present":
            return queryset.filter(attendance_validated=True)
        elif value.lower() == "absent":
            return queryset.filter(attendance_validated=False)
        return queryset


class LeaveRequestFilter(django_filters.FilterSet):
    """Filter leave requests"""

    status = django_filters.CharFilter(
        field_name="status", lookup_expr="iexact", label="Status"
    )
    employee = django_filters.NumberFilter(
        field_name="employee_id__id", label="Employee ID"
    )
    leave_type = django_filters.NumberFilter(
        field_name="leave_type_id__id", label="Leave Type ID"
    )
    department = django_filters.NumberFilter(
        field_name="employee_id__department_id__id", label="Department ID"
    )
    company = django_filters.NumberFilter(
        field_name="employee_id__company_id__id", label="Company ID"
    )
    date_from = django_filters.DateFilter(
        field_name="start_date", lookup_expr="gte", label="From Date"
    )
    date_to = django_filters.DateFilter(
        field_name="end_date", lookup_expr="lte", label="To Date"
    )

    class Meta:
        model = LeaveRequest
        fields = ["status", "employee", "leave_type", "department", "company"]


class DepartmentFilter(django_filters.FilterSet):
    """Filter departments"""

    search = django_filters.CharFilter(
        method="filter_search", label="Search department name"
    )
    company = django_filters.NumberFilter(
        field_name="company_id__id", label="Company ID"
    )

    class Meta:
        model = Department
        fields = ["company"]

    def filter_search(self, queryset, name, value):
        """Search in department name"""
        return queryset.filter(dept_name__icontains=value)
