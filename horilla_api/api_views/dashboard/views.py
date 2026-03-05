"""
Dashboard Views for React Frontend
Comprehensive API endpoints for dashboard functionality
"""

from datetime import date, datetime, timedelta

from django.db.models import Avg, Count, Q, Sum
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from asset.models import AssetAssignment
from attendance.models import Attendance, AttendanceActivity, AttendanceOverTime
from base.models import Company
from employee.models import Department, Employee
from leave.models import LeaveRequest, LeaveType
from recruitment.models import JobPosition, Recruitment

from ...api_decorators.base.decorators import permission_required
from ...api_methods.base.methods import permission_based_queryset
from ...api_serializers.dashboard.serializers import (
    ActivitySerializer,
    AttendanceBasicSerializer,
    AttendanceListSerializer,
    AttendanceTrendSerializer,
    DashboardAttendanceStatsSerializer,
    DashboardStatsSerializer,
    DepartmentStatisticsSerializer,
    EmployeeBasicSerializer,
    EmployeeComprehensiveSerializer,
    EmployeeDetailedSerializer,
    LeaveRequestBasicSerializer,
)
from ...docs import document_api


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for API responses"""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class DashboardOverviewAPIView(APIView):
    """
    Get overview statistics for the dashboard
    """

    permission_classes = [IsAuthenticated]

    @document_api(
        operation_description="Get dashboard overview statistics including employee count, attendance, leaves, and pending approvals",
        tags=["Dashboard"],
    )
    def get(self, request):
        """Get dashboard overview statistics"""
        try:
            today = date.today()

            # Calculate statistics
            total_employees = Employee.objects.filter(is_active=True).count()
            total_departments = Department.objects.count()

            # Attendance for today
            today_attendance = Attendance.objects.filter(attendance_date=today)
            present_today = today_attendance.exclude(attendance_validated=False).count()
            absent_today = total_employees - today_attendance.count()

            # Leave requests
            leave_today = LeaveRequest.objects.filter(
                start_date__lte=today, end_date__gte=today, status="approved"
            ).count()

            # Pending approvals (if user is manager)
            pending_approvals = 0
            if hasattr(request.user, "employee_get"):
                pending_approvals = LeaveRequest.objects.filter(
                    reporting_manager_id=request.user.employee_get, status="pending"
                ).count()
                pending_approvals += Attendance.objects.filter(
                    employee_id__reporting_manager_id=request.user.employee_get,
                    request_description__isnull=False,
                    is_validate_request=False,
                ).count()

            # Assets and positions
            total_assets = AssetAssignment.objects.filter(
                return_date__isnull=True
            ).count()
            open_positions = (
                Recruitment.objects.filter(status="active").aggregate(
                    count=Count("id")
                )["count"]
                or 0
            )

            pending_leave_requests = LeaveRequest.objects.filter(
                status="pending"
            ).count()
            pending_attendance_requests = Attendance.objects.filter(
                is_validate_request=False, request_description__isnull=False
            ).count()

            stats = {
                "total_employees": total_employees,
                "total_departments": total_departments,
                "present_today": present_today,
                "absent_today": absent_today,
                "on_leave_today": leave_today,
                "pending_approvals": pending_approvals,
                "total_assets": total_assets,
                "open_positions": open_positions,
                "pending_leave_requests": pending_leave_requests,
                "pending_attendance_requests": pending_attendance_requests,
            }

            serializer = DashboardStatsSerializer(stats)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AttendanceStatsAPIView(APIView):
    """
    Get attendance statistics
    """

    permission_classes = [IsAuthenticated]

    @document_api(
        operation_description="Get attendance statistics for a date range including present, absent, and on-leave counts",
        tags=["Attendance"],
    )
    def get(self, request):
        """Get attendance statistics for a date or date range"""
        try:
            date_from = request.query_params.get("from", date.today())
            date_to = request.query_params.get("to", date.today())

            if isinstance(date_from, str):
                date_from = datetime.strptime(date_from, "%Y-%m-%d").date()
            if isinstance(date_to, str):
                date_to = datetime.strptime(date_to, "%Y-%m-%d").date()

            # Build date range
            attendance_records = (
                Attendance.objects.filter(
                    attendance_date__gte=date_from, attendance_date__lte=date_to
                )
                .values("attendance_date")
                .annotate(
                    present=Count("id", filter=Q(attendance_validated=True)),
                    absent=Count("id", filter=Q(attendance_validated=False)),
                    on_leave=Count("id", filter=Q(request_type="leave")),
                )
            )

            stats = []
            total_employees = Employee.objects.filter(is_active=True).count()

            for record in attendance_records:
                present = record["present"]
                absent = record["absent"]
                on_leave = record["on_leave"]

                percentage = (
                    (present / total_employees * 100) if total_employees > 0 else 0
                )

                stats.append(
                    {
                        "date": record["attendance_date"],
                        "total_employees": total_employees,
                        "present": present,
                        "absent": absent,
                        "on_leave": on_leave,
                        "late": 0,  # Can be calculated from in_time
                        "work_from_home": 0,  # Can be tracked in Attendance model
                        "percentage_present": round(percentage, 2),
                    }
                )

            serializer = DashboardAttendanceStatsSerializer(stats, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class EmployeeListAPIView(APIView):
    """
    List all employees with filtering and pagination
    """

    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    @document_api(
        operation_description="Get list of all active employees with basic information, filters for department/company/status and search by name/email",
        tags=["Employee Management"],
    )
    def get(self, request):
        """Get list of employees"""
        try:
            employees = Employee.objects.filter(is_active=True)

            # Filtering
            department = request.query_params.get("department")
            company = request.query_params.get("company")
            status_filter = request.query_params.get("status")
            search = request.query_params.get("search")

            if department:
                employees = employees.filter(department_id__id=department)
            if company:
                employees = employees.filter(company_id__id=company)
            if search:
                employees = employees.filter(
                    Q(employee_first_name__icontains=search)
                    | Q(employee_last_name__icontains=search)
                    | Q(email__icontains=search)
                    | Q(badge_id__icontains=search)
                )

            # Pagination
            paginator = self.pagination_class()
            paginated = paginator.paginate_queryset(employees, request)

            serializer = EmployeeComprehensiveSerializer(paginated, many=True)
            return paginator.get_paginated_response(serializer.data)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class EmployeeDetailAPIView(APIView):
    """
    Get detailed information about an employee
    """

    permission_classes = [IsAuthenticated]

    @document_api(
        operation_description="Get comprehensive details of a specific employee including personal info, work details, and contact information",
        tags=["Employee Management"],
    )
    def get(self, request, employee_id):
        """Get detailed employee information"""
        try:
            employee = Employee.objects.get(id=employee_id)
            serializer = EmployeeDetailedSerializer(employee)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Employee.DoesNotExist:
            return Response(
                {"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AttendanceListAPIView(APIView):
    """
    List attendance records with filtering
    """

    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    @document_api(
        operation_description="Get list of attendance records with optional filters by date range, employee, and status, with pagination",
        tags=["Attendance"],
    )
    def get(self, request):
        """Get attendance records"""
        try:
            attendance_records = Attendance.objects.select_related(
                "employee_id", "shift_id"
            ).order_by("-attendance_date")

            # Filtering
            date_from = request.query_params.get("from")
            date_to = request.query_params.get("to")
            employee = request.query_params.get("employee")
            status_filter = request.query_params.get("status")

            if date_from:
                date_from = datetime.strptime(date_from, "%Y-%m-%d").date()
                attendance_records = attendance_records.filter(
                    attendance_date__gte=date_from
                )
            if date_to:
                date_to = datetime.strptime(date_to, "%Y-%m-%d").date()
                attendance_records = attendance_records.filter(
                    attendance_date__lte=date_to
                )
            if employee:
                attendance_records = attendance_records.filter(employee_id__id=employee)
            if status_filter:
                if status_filter == "present":
                    attendance_records = attendance_records.filter(
                        attendance_validated=True
                    )
                elif status_filter == "absent":
                    attendance_records = attendance_records.filter(
                        attendance_validated=False
                    )

            # Pagination
            paginator = self.pagination_class()
            paginated = paginator.paginate_queryset(attendance_records, request)

            from ...api_serializers.dashboard.serializers import (
                AttendanceListSerializer,
            )

            serializer = AttendanceListSerializer(paginated, many=True)
            return paginator.get_paginated_response(serializer.data)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LeaveRequestListAPIView(APIView):
    """
    List leave requests with filtering
    """

    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    @document_api(
        operation_description="Get list of leave requests with optional filters by status, employee, and leave type, with pagination",
        tags=["Leave Management"],
    )
    def get(self, request):
        """Get leave requests"""
        try:
            leave_requests = LeaveRequest.objects.select_related(
                "employee_id", "leave_type_id"
            ).order_by("-created_at")

            # Filtering
            status_filter = request.query_params.get("status")
            employee = request.query_params.get("employee")
            leave_type = request.query_params.get("leave_type")

            if status_filter:
                leave_requests = leave_requests.filter(status=status_filter.lower())
            if employee:
                leave_requests = leave_requests.filter(employee_id__id=employee)
            if leave_type:
                leave_requests = leave_requests.filter(leave_type_id__id=leave_type)

            # Pagination
            paginator = self.pagination_class()
            paginated = paginator.paginate_queryset(leave_requests, request)

            serializer = LeaveRequestBasicSerializer(paginated, many=True)
            return paginator.get_paginated_response(serializer.data)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DepartmentStatsAPIView(APIView):
    """
    Get statistics for each department
    """

    permission_classes = [IsAuthenticated]

    @document_api(
        operation_description="Get attendance statistics for each department including employee counts, present/absent/on-leave breakdown",
        tags=["Dashboard"],
    )
    def get(self, request):
        """Get department-wise statistics"""
        try:
            today = date.today()
            departments = Department.objects.all()

            stats = []
            for dept in departments:
                dept_employees = Employee.objects.filter(
                    department_id=dept, is_active=True
                )
                total = dept_employees.count()

                present_today = Attendance.objects.filter(
                    employee_id__in=dept_employees,
                    attendance_date=today,
                    attendance_validated=True,
                ).count()

                absent_today = (
                    total
                    - Attendance.objects.filter(
                        employee_id__in=dept_employees, attendance_date=today
                    ).count()
                )

                on_leave_today = LeaveRequest.objects.filter(
                    employee_id__in=dept_employees,
                    start_date__lte=today,
                    end_date__gte=today,
                    status="approved",
                ).count()

                percentage = (present_today / total * 100) if total > 0 else 0

                stats.append(
                    {
                        "department_id": dept.id,
                        "department_name": dept.dept_name,
                        "total_employees": total,
                        "present_today": present_today,
                        "absent_today": absent_today,
                        "on_leave_today": on_leave_today,
                        "percentage_present": round(percentage, 2),
                    }
                )

            serializer = DepartmentStatisticsSerializer(stats, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AttendanceTrendAPIView(APIView):
    """
    Get attendance trend over time
    """

    permission_classes = [IsAuthenticated]

    @document_api(
        operation_description="Get attendance trend data for a specified number of days showing daily present/absent/on-leave counts",
        tags=["Attendance"],
    )
    def get(self, request):
        """Get attendance trend"""
        try:
            days = int(request.query_params.get("days", 30))
            date_from = date.today() - timedelta(days=days)

            # Get attendance records with employee details
            attendance_records = (
                Attendance.objects.filter(attendance_date__gte=date_from)
                .select_related("employee_id")
                .order_by("-attendance_date")
            )

            # Use comprehensive serializer to include all employee details
            serializer = AttendanceListSerializer(attendance_records, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class HoursChartAPIView(APIView):
    """
    Department-wise worked and pending hours chart data.
    """

    permission_classes = [IsAuthenticated]

    @document_api(
        operation_description="Get department-wise worked/pending hours. Optional query param: month=YYYY-MM",
        tags=["Dashboard"],
    )
    def get(self, request):
        try:
            month_param = request.query_params.get("month")
            records = AttendanceOverTime.objects.select_related(
                "employee_id__employee_work_info__department_id"
            )

            if month_param:
                year_str, month_str = month_param.split("-", 1)
                month_names = {
                    "01": "january",
                    "02": "february",
                    "03": "march",
                    "04": "april",
                    "05": "may",
                    "06": "june",
                    "07": "july",
                    "08": "august",
                    "09": "september",
                    "10": "october",
                    "11": "november",
                    "12": "december",
                }
                records = records.filter(
                    year=year_str,
                    month=month_names.get(month_str, ""),
                )

            dept_totals = {}
            for rec in records:
                work_info = getattr(rec.employee_id, "employee_work_info", None)
                dept_obj = getattr(work_info, "department_id", None)
                if not dept_obj:
                    continue
                dept = dept_obj.department
                if dept not in dept_totals:
                    dept_totals[dept] = {"pending": 0.0, "worked": 0.0}
                dept_totals[dept]["pending"] += (rec.hour_pending_second or 0) / 3600
                dept_totals[dept]["worked"] += (rec.hour_account_second or 0) / 3600

            labels = sorted(dept_totals.keys())
            pending_data = [round(dept_totals[d]["pending"], 2) for d in labels]
            worked_data = [round(dept_totals[d]["worked"], 2) for d in labels]

            return Response(
                {
                    "data": {
                        "labels": labels,
                        "datasets": [
                            {"label": "Pending Hours", "data": pending_data},
                            {"label": "Worked Hours", "data": worked_data},
                        ],
                    }
                },
                status=status.HTTP_200_OK,
            )
        except ValueError:
            return Response(
                {"error": "Invalid month format. Use YYYY-MM."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ActivitiesListAPIView(APIView):
    """
    Get recent activities
    """

    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    @document_api(
        operation_description="Get recent attendance activities (clock-in, clock-out) for a specified number of days with pagination",
        tags=["Attendance"],
    )
    def get(self, request):
        """Get recent activities"""
        try:
            activities = AttendanceActivity.objects.select_related(
                "employee_id"
            ).order_by("-activity_date")

            # Limit to recent activities
            days = int(request.query_params.get("days", 7))
            date_from = date.today() - timedelta(days=days)
            activities = activities.filter(activity_date__gte=date_from)

            # Pagination
            paginator = self.pagination_class()
            paginated = paginator.paginate_queryset(activities, request)

            serializer = ActivitySerializer(paginated, many=True)
            return paginator.get_paginated_response(serializer.data)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MyAttendanceAPIView(APIView):
    """
    Get current user's attendance and details
    """

    permission_classes = [IsAuthenticated]

    @document_api(
        operation_description="Get current authenticated user's employee profile information and attendance details",
        tags=["Employee Management"],
    )
    def get(self, request):
        """Get current user's attendance"""
        try:
            if not hasattr(request.user, "employee_get"):
                return Response(
                    {"error": "User is not an employee"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            employee = request.user.employee_get
            serializer = EmployeeDetailedSerializer(employee)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DashboardSummaryAPIView(APIView):
    """
    Get complete dashboard summary
    """

    permission_classes = [IsAuthenticated]

    @document_api(
        operation_description="Get comprehensive dashboard summary with all overview statistics, department stats, attendance trends, and recent activities",
        tags=["Dashboard"],
    )
    def get(self, request):
        """Get complete dashboard summary"""
        try:
            today = date.today()

            # Overview stats
            total_employees = Employee.objects.filter(is_active=True).count()
            today_attendance = Attendance.objects.filter(attendance_date=today)
            present_today = today_attendance.filter(attendance_validated=True).count()
            absent_today = total_employees - today_attendance.count()

            # Leave stats
            leave_today = LeaveRequest.objects.filter(
                start_date__lte=today, end_date__gte=today, status="approved"
            ).count()

            pending_requests = LeaveRequest.objects.filter(status="pending").count()
            pending_attendance = Attendance.objects.filter(
                is_validate_request=False, request_description__isnull=False
            ).count()

            # Recent activities
            recent_attendance = Attendance.objects.select_related(
                "employee_id", "shift_id"
            ).order_by("-attendance_date")[:10]

            recent_leaves = LeaveRequest.objects.select_related(
                "employee_id", "leave_type_id"
            ).order_by("-created_at")[:10]

            # Current user info
            user_data = None
            if hasattr(request.user, "employee_get"):
                user_data = EmployeeDetailedSerializer(request.user.employee_get).data

            response_data = {
                "overview": {
                    "total_employees": total_employees,
                    "present_today": present_today,
                    "absent_today": absent_today,
                    "on_leave_today": leave_today,
                    "pending_requests": pending_requests,
                    "pending_attendance": pending_attendance,
                },
                "recent_attendance": AttendanceBasicSerializer(
                    recent_attendance, many=True
                ).data,
                "recent_leaves": LeaveRequestBasicSerializer(
                    recent_leaves, many=True
                ).data,
                "current_user": user_data,
                "timestamp": datetime.now().isoformat(),
            }

            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
