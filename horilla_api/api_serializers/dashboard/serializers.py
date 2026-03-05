"""
Dashboard Serializers for React Frontend
Optimized for comprehensive dashboard views
"""

from datetime import date, datetime, timedelta

from django.contrib.auth.models import User
from django.db.models import Count, Q
from rest_framework import serializers

from asset.models import AssetAssignment
from attendance.models import Attendance, AttendanceActivity
from employee.models import Employee
from leave.models import LeaveRequest
from recruitment.models import JobPosition, Recruitment


class EmployeeBasicSerializer(serializers.ModelSerializer):
    """Minimal employee data for lists"""

    full_name = serializers.SerializerMethodField()
    profile_image = serializers.SerializerMethodField()
    company_name = serializers.CharField(source="company_id.company", read_only=True)
    department_name = serializers.CharField(
        source="department_id.dept_name", read_only=True
    )
    designation_name = serializers.CharField(
        source="designation_id.designation_name", read_only=True
    )

    class Meta:
        model = Employee
        fields = [
            "id",
            "badge_id",
            "full_name",
            "profile_image",
            "email",
            "phone",
            "company_name",
            "department_name",
            "designation_name",
        ]

    def get_full_name(self, obj):
        return f"{obj.employee_first_name} {obj.employee_last_name}"

    def get_profile_image(self, obj):
        if obj.employee_profile:
            return obj.employee_profile.url
        return None


class AttendanceBasicSerializer(serializers.ModelSerializer):
    """Attendance data for dashboard"""

    employee = EmployeeBasicSerializer(source="employee_id", read_only=True)
    shift_name = serializers.CharField(source="shift_id.employee_shift", read_only=True)
    status_display = serializers.SerializerMethodField()
    date_formatted = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = [
            "id",
            "employee",
            "shift_name",
            "attendance_date",
            "date_formatted",
            "status_display",
            "in_time",
            "out_time",
            "overtime_second",
        ]

    def get_status_display(self, obj):
        """Return readable attendance status"""
        if obj.attendance_validated:
            return "validated"
        if obj.in_time and obj.out_time:
            return "complete"
        elif obj.in_time:
            return "in_progress"
        return "absent"

    def get_date_formatted(self, obj):
        if obj.attendance_date:
            return obj.attendance_date.strftime("%d %b %Y")
        return None


class AttendanceListSerializer(serializers.ModelSerializer):
    """Serializer for the attendance list API with flattened employee info"""

    employee_name = serializers.SerializerMethodField()
    badge_id = serializers.CharField(source="employee_id.badge_id", read_only=True)
    employee_profile_url = serializers.SerializerMethodField()
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    modified_by = serializers.PrimaryKeyRelatedField(read_only=True)
    employee_id = serializers.PrimaryKeyRelatedField(read_only=True)
    shift_id = serializers.PrimaryKeyRelatedField(read_only=True, allow_null=True)
    work_type_id = serializers.PrimaryKeyRelatedField(read_only=True, allow_null=True)
    batch_attendance_id = serializers.PrimaryKeyRelatedField(
        read_only=True, allow_null=True
    )
    approved_by = serializers.PrimaryKeyRelatedField(read_only=True, allow_null=True)

    class Meta:
        model = Attendance
        fields = [
            "id",
            "employee_name",
            "badge_id",
            "employee_profile_url",
            "created_at",
            "is_active",
            "attendance_date",
            "attendance_clock_in_date",
            "attendance_clock_in",
            "attendance_clock_out_date",
            "attendance_clock_out",
            "attendance_worked_hour",
            "minimum_hour",
            "attendance_overtime_approve",
            "attendance_validated",
            "is_bulk_request",
            "is_holiday",
            "created_by",
            "modified_by",
            "employee_id",
            "shift_id",
            "work_type_id",
            "batch_attendance_id",
            "approved_by",
        ]

    def get_employee_name(self, obj):
        if obj.employee_id:
            return f"{obj.employee_id.employee_first_name} {obj.employee_id.employee_last_name or ''}".strip()
        return None

    def get_employee_profile_url(self, obj):
        try:
            if obj.employee_id and obj.employee_id.employee_profile:
                return obj.employee_id.employee_profile.url
        except Exception:
            pass
        return None


class LeaveRequestBasicSerializer(serializers.ModelSerializer):
    """Leave request data for dashboard"""

    employee = EmployeeBasicSerializer(source="employee_id", read_only=True)
    leave_type_name = serializers.CharField(
        source="leave_type_id.leave_type", read_only=True
    )
    status_display = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()

    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "employee",
            "leave_type_name",
            "start_date",
            "end_date",
            "duration",
            "status_display",
            "created_at",
        ]

    def get_status_display(self, obj):
        return obj.status.lower()

    def get_duration(self, obj):
        if obj.start_date and obj.end_date:
            return (obj.end_date - obj.start_date).days + 1
        return 0


class DashboardStatsSerializer(serializers.Serializer):
    """Dashboard statistics"""

    total_employees = serializers.IntegerField()
    total_departments = serializers.IntegerField()
    present_today = serializers.IntegerField()
    absent_today = serializers.IntegerField()
    on_leave_today = serializers.IntegerField()
    pending_approvals = serializers.IntegerField()
    total_assets = serializers.IntegerField()
    open_positions = serializers.IntegerField()
    pending_leave_requests = serializers.IntegerField()
    pending_attendance_requests = serializers.IntegerField()


class DashboardAttendanceStatsSerializer(serializers.Serializer):
    """Attendance specific statistics"""

    date = serializers.DateField()
    total_employees = serializers.IntegerField()
    present = serializers.IntegerField()
    absent = serializers.IntegerField()
    on_leave = serializers.IntegerField()
    late = serializers.IntegerField()
    work_from_home = serializers.IntegerField()
    percentage_present = serializers.FloatField()


class EmployeeDetailedSerializer(serializers.ModelSerializer):
    """Complete employee details for detail view"""

    full_name = serializers.SerializerMethodField()
    profile_image = serializers.SerializerMethodField()
    company_name = serializers.CharField(source="company_id.company", read_only=True)
    department_name = serializers.CharField(
        source="department_id.dept_name", read_only=True
    )
    designation_name = serializers.CharField(
        source="designation_id.designation_name", read_only=True
    )
    manager_name = serializers.SerializerMethodField()
    recent_attendance = serializers.SerializerMethodField()
    current_status = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            "id",
            "badge_id",
            "full_name",
            "email",
            "phone",
            "profile_image",
            "company_name",
            "department_name",
            "designation_name",
            "manager_name",
            "date_joining",
            "address",
            "dob",
            "gender",
            "emergency_contact",
            "emergency_contact_name",
            "recent_attendance",
            "current_status",
        ]

    def get_full_name(self, obj):
        return f"{obj.employee_first_name} {obj.employee_last_name}"

    def get_profile_image(self, obj):
        if obj.employee_profile:
            return obj.employee_profile.url
        return None

    def get_manager_name(self, obj):
        if obj.reporting_manager_id:
            manager = obj.reporting_manager_id
            return f"{manager.employee_first_name} {manager.employee_last_name}"
        return None

    def get_recent_attendance(self, obj):
        recent = Attendance.objects.filter(employee_id=obj).order_by(
            "-attendance_date"
        )[:7]
        return AttendanceBasicSerializer(recent, many=True).data

    def get_current_status(self, obj):
        today = date.today()
        today_attendance = Attendance.objects.filter(
            employee_id=obj, attendance_date=today
        ).first()

        if not today_attendance:
            return "absent"
        if today_attendance.out_time:
            return "off_duty"
        if today_attendance.in_time:
            return "on_duty"
        return "unknown"


class EmployeeComprehensiveSerializer(serializers.ModelSerializer):
    """Comprehensive employee details with all fields"""

    employee_work_info_id = serializers.SerializerMethodField()
    employee_bank_details_id = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            "id",
            "employee_work_info_id",
            "employee_bank_details_id",
            "badge_id",
            "employee_first_name",
            "employee_last_name",
            "employee_profile",
            "email",
            "phone",
            "address",
            "country",
            "state",
            "city",
            "zip",
            "dob",
            "gender",
            "qualification",
            "experience",
            "marital_status",
            "children",
            "emergency_contact",
            "emergency_contact_name",
            "emergency_contact_relation",
            "is_active",
            "additional_info",
            "is_from_onboarding",
            "is_directly_converted",
            "employee_user_id",
        ]

    def get_employee_work_info_id(self, obj):
        if hasattr(obj, "employee_work_info") and obj.employee_work_info:
            return str(obj.employee_work_info.id)
        return None

    def get_employee_bank_details_id(self, obj):
        try:
            bank_details = obj.employeebankdetails
            return str(bank_details.id) if bank_details else None
        except:
            return None


class LeaveBalanceSerializer(serializers.Serializer):
    """Leave balance information"""

    leave_type = serializers.CharField()
    available_days = serializers.FloatField()
    used_days = serializers.FloatField()
    pending_days = serializers.FloatField()


class AssetSerializer(serializers.ModelSerializer):
    """Asset information"""

    asset_name = serializers.CharField(source="asset_id.asset_name", read_only=True)
    asset_category = serializers.CharField(
        source="asset_id.asset_category_id.asset_category", read_only=True
    )
    status = serializers.SerializerMethodField()

    class Meta:
        model = AssetAssignment
        fields = [
            "id",
            "asset_name",
            "asset_category",
            "assignment_date",
            "status",
        ]

    def get_status(self, obj):
        return "assigned" if obj.assignment_date and not obj.return_date else "returned"


class DepartmentStatisticsSerializer(serializers.Serializer):
    """Department level statistics"""

    department_id = serializers.IntegerField()
    department_name = serializers.CharField()
    total_employees = serializers.IntegerField()
    present_today = serializers.IntegerField()
    absent_today = serializers.IntegerField()
    on_leave_today = serializers.IntegerField()
    percentage_present = serializers.FloatField()


class AttendanceTrendSerializer(serializers.Serializer):
    """Attendance trend over time"""

    date = serializers.DateField()
    present_count = serializers.IntegerField()
    absent_count = serializers.IntegerField()
    on_leave_count = serializers.IntegerField()


class ActivitySerializer(serializers.ModelSerializer):
    """User activity tracking"""

    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceActivity
        fields = [
            "id",
            "employee_name",
            "activity_date",
            "clock_in_time",
            "clock_out_time",
            "duration",
        ]

    def get_employee_name(self, obj):
        if hasattr(obj, "employee_id") and obj.employee_id:
            emp = obj.employee_id
            return f"{emp.employee_first_name} {emp.employee_last_name}"
        return "Unknown"
