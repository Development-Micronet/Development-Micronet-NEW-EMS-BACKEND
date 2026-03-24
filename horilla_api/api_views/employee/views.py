from datetime import date

from django.conf import settings
from django.db.models import ProtectedError, Q
from django.http import Http404
from django.utils.decorators import method_decorator
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from attendance.models import Attendance, AttendanceActivity
from employee.filters import (
    DisciplinaryActionFilter,
    DocumentRequestFilter,
    EmployeeFilter,
)
from employee.models import (
    Actiontype,
    DisciplinaryAction,
    Employee,
    EmployeeBankDetails,
    EmployeeType,
    EmployeeWorkInformation,
    Policy,
    WorkTypeRequest,
)
from employee.views import work_info_export, work_info_import
from horilla.decorators import owner_can_enter
from horilla_api.api_decorators.base.decorators import permission_required
from horilla_api.api_methods.employee.methods import get_next_badge_id
from horilla_api.api_methods.import_data import (
    EMPLOYEE_IMPORT_HEADERS,
    import_employee_dataframe,
    read_import_file,
    validate_headers,
)
from horilla_documents.models import Document, DocumentRequest
from notifications.signals import notify

from ...api_decorators.base.decorators import (
    manager_or_owner_permission_required,
    manager_permission_required,
)
from ...api_decorators.employee.decorators import or_condition
from ...api_methods.base.methods import groupby_queryset, permission_based_queryset
from ...api_serializers.employee.serializers import (
    ActiontypeSerializer,
    DisciplinaryActionSerializer,
    DocumentRequestSerializer,
    DocumentSerializer,
    EmployeeBankDetailsSerializer,
    EmployeeListSerializer,
    EmployeePolicySerializer,
    EmployeeSelectorSerializer,
    EmployeeSerializer,
    EmployeeTypeSerializer,
    EmployeeWorkInformationSerializer,
    PolicySerializer,
    WorkTypeRequestSerializer,
)
from ...docs import document_api


# --- WorkTypeRequest APIView ---
class WorkTypeRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = WorkTypeRequest.objects.all()
        serializer = WorkTypeRequestSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = WorkTypeRequestSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk=None):
        queryset = WorkTypeRequest.objects.filter(employee_id=pk)
        if not queryset.exists():
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        updated_fields = {}
        permanent_request = request.data.get("permanent_request", None)
        for instance in queryset:
            serializer = WorkTypeRequestSerializer(
                instance, data=request.data, partial=True
            )
            if serializer.is_valid():
                obj = serializer.save()
                # Update status based on permanent_request
                if permanent_request is not None:
                    if permanent_request:
                        obj.status = "approve"
                    else:
                        obj.status = "reject"
                    obj.save()
                for field in request.data:
                    updated_fields[field] = request.data[field]
        return Response(
            {
                "employee_id": pk,
                "updated_fields": updated_fields,
                "message": "Work type request updated successfully.",
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk=None):
        queryset = WorkTypeRequest.objects.filter(employee_id=pk)
        if not queryset.exists():
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        deleted_ids = [obj.id for obj in queryset]
        queryset.delete()
        return Response(
            {"employee_id": pk, "deleted_request_ids": deleted_ids},
            status=status.HTTP_204_NO_CONTENT,
        )


class WorkTypeRequestApproveRejectView(APIView):
    permission_classes = [IsAuthenticated]

    @method_decorator(permission_required("employee.change_worktyperequest"))
    def post(self, request, id, status_text):
        if status_text not in ["approve", "reject"]:
            return Response(
                {"error": "status must be either 'approve' or 'reject'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        work_type_request = WorkTypeRequest.objects.filter(id=id).first()
        if work_type_request is not None:
            work_type_request.status = status_text
            work_type_request.save(update_fields=["status"])
            return Response(
                {
                    "mode": "request_id",
                    "id": work_type_request.id,
                    "employee_id": work_type_request.employee.id,
                    "status": work_type_request.status,
                    "message": f"Work type request {status_text}d successfully.",
                },
                status=status.HTTP_200_OK,
            )

        # Backward-compatible fallback: treat path id as employee id.
        queryset = WorkTypeRequest.objects.filter(employee_id=id)
        if not queryset.exists():
            return Response(
                {
                    "error": (
                        "Work type request not found for the given request id "
                        "or employee id"
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        updated_ids = list(queryset.values_list("id", flat=True))
        queryset.update(status=status_text)
        return Response(
            {
                "mode": "employee_id",
                "employee_id": id,
                "updated_request_ids": updated_ids,
                "status": status_text,
                "message": (
                    f"{len(updated_ids)} work type request(s) {status_text}d "
                    "successfully."
                ),
            },
            status=status.HTTP_200_OK,
        )


from employee.models_shift_request import ShiftRequest
from horilla_api.api_serializers.employee.shift_request_serializer import (
    ShiftRequestSerializer,
)


def permission_check(request, perm):
    return request.user.has_perm(perm)


def object_check(cls, pk):
    try:
        obj = cls.objects.get(id=pk)
        return obj
    except cls.DoesNotExist:
        return None


def object_delete(cls, pk):
    try:
        cls.objects.get(id=pk).delete()
        return "", 200
    except Exception as e:
        return {"error": str(e)}, 400


class AuthenticatedEmployeeListAPIView(APIView):
    """
    Returns only the authenticated user's employee record.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        employee = getattr(user, "employee_get", None)
        if employee:
            serializer = EmployeeListSerializer([employee], many=True)
            return Response(
                {"count": 1, "next": None, "previous": None, "results": serializer.data}
            )
        else:
            return Response({"count": 0, "next": None, "previous": None, "results": []})


class EmployeeTypeAPIView(APIView):
    """
    Retrieves and manages employee types.

    Methods:
        get(request, pk=None): Returns a single employee type if pk is provided, otherwise returns all employee types.
        post(request, pk=None): Creates a new employee type.
        put(request, pk=None): Updates an employee type.
        patch(request, pk=None): Partially updates an employee type.
        delete(request, pk=None): Deletes an employee type.
    """

    permission_classes = [IsAuthenticated]

    @document_api(
        operation_description="Get employee types - retrieve specific type or list all employee types",
        tags=["Employee Management"],
    )
    def get(self, request, pk=None):
        if pk:
            try:
                employee_type = EmployeeType.objects.get(id=pk)
                serializer = EmployeeTypeSerializer(employee_type)
                return Response(serializer.data, status=200)
            except EmployeeType.DoesNotExist:
                return Response(
                    {"error": "Employee type does not exist"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # List with pagination
        paginator = PageNumberPagination()
        employee_types = EmployeeType.objects.all()
        page = paginator.paginate_queryset(employee_types, request)
        if page is not None:
            serializer = EmployeeTypeSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = EmployeeTypeSerializer(employee_types, many=True)
        return Response({"results": serializer.data}, status=200)

    def post(self, request, pk=None):
        """Create a new employee type"""
        if pk:
            return Response(
                {
                    "error": "Cannot POST to a specific employee type ID. Use POST without ID to create."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = EmployeeTypeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @method_decorator(permission_required("employee.change_employeetype"))
    def put(self, request, pk=None):
        """Update an employee type"""
        if not pk:
            return Response(
                {
                    "error": "Employee type ID is required for update. Use PUT /employee-type/{id}/."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            employee_type = EmployeeType.objects.get(id=pk)
        except EmployeeType.DoesNotExist:
            return Response(
                {"error": "Employee type does not exist"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = EmployeeTypeSerializer(
            employee_type, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk=None):
        """Partially update an employee type"""
        if not pk:
            return Response(
                {
                    "error": "Employee type ID is required for update. Use PATCH /employee-type/{id}/."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            employee_type = EmployeeType.objects.get(id=pk)
        except EmployeeType.DoesNotExist:
            return Response(
                {"error": "Employee type does not exist"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = EmployeeTypeSerializer(
            employee_type, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @method_decorator(permission_required("employee.delete_employeetype"))
    def delete(self, request, pk=None):
        """Delete an employee type"""
        if not pk:
            return Response(
                {
                    "error": "Employee type ID is required for deletion. Use DELETE /employee-type/{id}/."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            employee_type = EmployeeType.objects.get(id=pk)
            employee_type.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except EmployeeType.DoesNotExist:
            return Response(
                {"error": "Employee type does not exist"},
                status=status.HTTP_404_NOT_FOUND,
            )


from django.db import IntegrityError, transaction

from performance.models import Meeting, Objective


class EmployeeAPIView(APIView):
    """
    Handles CRUD operations for employees.
    """

    filter_backends = [DjangoFilterBackend]
    filterset_class = EmployeeFilter
    permission_classes = [IsAuthenticated]
    queryset = Employee.objects.all()

    @document_api(
        operation_description="Get employee details by ID",
        tags=["Employee Management"],
    )
    def get(self, request, pk):
        user = request.user
        try:
            # fetch full employee for detail
            employee = Employee.objects.get(pk=pk)
        except Employee.DoesNotExist:
            return Response(
                {"error": "Employee does not exist"}, status=status.HTTP_404_NOT_FOUND
            )

        # Admin detection and admin-token header
        admin_token = request.META.get("HTTP_X_ADMIN_TOKEN")
        admin_token_valid = bool(
            admin_token
            and admin_token == getattr(settings, "EMPLOYEE_ADMIN_ACCESS_TOKEN", None)
        )
        is_admin_user = False
        if (
            hasattr(user, "employee_get")
            and getattr(user.employee_get, "role", None) == "admin"
        ):
            is_admin_user = True
        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
            is_admin_user = True

        # If admin with valid token -> return limited admin view (list serializer)
        if is_admin_user and admin_token_valid:
            serializer = EmployeeListSerializer(employee)
            return Response(serializer.data)

        # Users (excluding admins) with global view permission can see full details
        if user.has_perm("employee.view_employee") and not is_admin_user:
            serializer = EmployeeSerializer(employee)
            return Response(serializer.data)

        # If employee is in user's subordinates -> full view
        if hasattr(user, "employee_get"):
            subordinates = user.employee_get.get_subordinate_employees()
            if subordinates.filter(pk=pk).exists():
                serializer = EmployeeSerializer(employee)
                return Response(serializer.data)

        # If requesting own data -> full view
        if hasattr(user, "employee_get") and employee.pk == user.employee_get.id:
            serializer = EmployeeSerializer(employee)
            return Response(serializer.data)

        # If target employee has tokenized access -> limited view
        if getattr(employee, "is_tokenized", False):
            serializer = EmployeeListSerializer(employee)
            return Response(serializer.data)

        return Response(
            {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
        )

        # paginator = PageNumberPagination()
        # if request.user.has_perm('employee.view_employee'):
        #     employees_queryset = Employee.objects.all()
        # elif request.user.employee_get.get_subordinate_employees():
        #     employees_queryset = request.user.employee_get.get_subordinate_employees()
        # else:
        #     employees_queryset = [request.user.employee_get]
        # employees_filter_queryset = self.filterset_class(
        #     request.GET, queryset=employees_queryset).qs
        # field_name = request.GET.get("groupby_field", None)
        # if field_name:
        #     url = request.build_absolute_uri()
        #     return groupby_queryset(request, url, field_name, employees_filter_queryset)
        # page = paginator.paginate_queryset(employees_filter_queryset, request)
        # serializer = EmployeeSerializer(page, many=True)
        # return paginator.get_paginated_response(serializer.data)

    @method_decorator(permission_required("employee.add_employee"))
    def post(self, request):
        serializer = EmployeeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        user = request.user
        employee = Employee.objects.get(pk=pk)
        if (
            employee
            in [user.employee_get, request.user.employee_get.get_reporting_manager()]
        ) or user.has_perm("employee.change_employee"):
            serializer = EmployeeSerializer(employee, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response({"error": "You don't have permission"}, status=400)

    @method_decorator(permission_required("employee.delete_employee"))
    def delete(self, request, pk):
        def _run_cleanup_step(operation):
            """
            Execute one best-effort cleanup step inside its own savepoint so a
            failing relation does not break the outer force-delete transaction.
            """
            try:
                with transaction.atomic():
                    operation()
            except Exception:
                return False
            return True

        def _cleanup_employee_reverse_relations(employee_obj):
            """
            Best-effort cleanup for force delete:
            - clear M2M links
            - null nullable FK/O2O links
            - delete non-nullable related rows
            """
            for rel in employee_obj._meta.related_objects:
                accessor_name = rel.get_accessor_name()
                if not accessor_name:
                    continue

                try:
                    related_accessor = getattr(employee_obj, accessor_name)
                except Exception:
                    continue

                if rel.many_to_many:
                    _run_cleanup_step(lambda accessor=related_accessor: accessor.clear())
                    continue

                rel_field_name = rel.field.name

                # Reverse FK (one employee -> many related rows)
                if rel.one_to_many:
                    queryset = related_accessor.all()
                    if rel.field.null:
                        _run_cleanup_step(
                            lambda qs=queryset, field=rel_field_name: qs.update(
                                **{field: None}
                            )
                        )
                    else:
                        _run_cleanup_step(lambda qs=queryset: qs.delete())
                    continue

                # Reverse one-to-one
                if rel.one_to_one:
                    try:
                        related_obj = related_accessor
                    except rel.related_model.DoesNotExist:
                        continue
                    except Exception:
                        continue

                    if rel.field.null:
                        def clear_one_to_one(obj=related_obj, field=rel_field_name):
                            setattr(obj, field, None)
                            obj.save(update_fields=[field])

                        _run_cleanup_step(clear_one_to_one)
                    else:
                        _run_cleanup_step(lambda obj=related_obj: obj.delete())

        def _cleanup_user_reverse_relations(user_obj):
            """
            Best-effort cleanup for linked auth user references before deleting
            the user record. This is needed for older tables that still behave
            like DO_NOTHING/NO ACTION at the database level.
            """
            for rel in user_obj._meta.related_objects:
                accessor_name = rel.get_accessor_name()
                if not accessor_name:
                    continue

                try:
                    related_accessor = getattr(user_obj, accessor_name)
                except Exception:
                    continue

                if rel.many_to_many:
                    _run_cleanup_step(lambda accessor=related_accessor: accessor.clear())
                    continue

                rel_field_name = rel.field.name

                if rel.one_to_many:
                    queryset = related_accessor.all()
                    if rel.field.null:
                        _run_cleanup_step(
                            lambda qs=queryset, field=rel_field_name: qs.update(
                                **{field: None}
                            )
                        )
                    else:
                        _run_cleanup_step(lambda qs=queryset: qs.delete())
                    continue

                if rel.one_to_one:
                    try:
                        related_obj = related_accessor
                    except rel.related_model.DoesNotExist:
                        continue
                    except Exception:
                        continue

                    if rel.field.null:
                        def clear_user_one_to_one(obj=related_obj, field=rel_field_name):
                            setattr(obj, field, None)
                            obj.save(update_fields=[field])

                        _run_cleanup_step(clear_user_one_to_one)
                    else:
                        _run_cleanup_step(lambda obj=related_obj: obj.delete())

        try:
            employee = Employee.objects.get(pk=pk)
            force_delete = (
                str(request.query_params.get("force", "false")).strip().lower()
                == "true"
            )

            if force_delete:
                # Remove known related records first, then force-delete employee.
                from django.apps import apps

                with transaction.atomic():
                    AttendanceActivity.objects.filter(employee_id=employee).delete()
                    Attendance.objects.filter(employee_id=employee).delete()

                    if apps.is_installed("payroll"):
                        from payroll.models.models import Contract

                        Contract.objects.filter(employee_id=employee).delete()

                    if apps.is_installed("pms"):
                        from pms.models import (
                            Answer,
                            Comment,
                            EmployeeBonusPoint,
                            EmployeeObjective,
                            Feedback,
                            KeyResultFeedback,
                            MeetingsAnswer,
                        )

                        Comment.objects.filter(employee_id=employee).delete()
                        Answer.objects.filter(employee_id=employee).delete()
                        KeyResultFeedback.objects.filter(employee_id=employee).delete()
                        MeetingsAnswer.objects.filter(employee_id=employee).delete()
                        EmployeeBonusPoint.objects.filter(employee_id=employee).delete()
                        Feedback.objects.filter(employee_id=employee).delete()
                        Feedback.objects.filter(manager_id=employee).delete()
                        EmployeeObjective.objects.filter(employee_id=employee).delete()

                    # Safety net: remove/null any remaining reverse relations.
                    _cleanup_employee_reverse_relations(employee)

                    user = employee.employee_user_id
                    employee.delete()
                    if user:
                        _cleanup_user_reverse_relations(user)
                        with transaction.atomic():
                            user.delete()
                    return Response(status=status.HTTP_204_NO_CONTENT)

            user = employee.employee_user_id
            employee.delete()
            if user:
                _cleanup_user_reverse_relations(user)
                with transaction.atomic():
                    user.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        except ProtectedError as e:
            blocked = sorted(
                {
                    str(getattr(obj._meta, "verbose_name", obj.__class__.__name__))
                    for obj in e.protected_objects
                }
            )
            return Response(
                {
                    "error": "Deletion blocked by protected related records.",
                    "blocked": blocked,
                    "hint": "Use ?force=true to remove known related records first.",
                },
                status=status.HTTP_409_CONFLICT,
            )

        except IntegrityError as e:
            return Response(
                {
                    "error": "Deletion failed due to related records constraint.",
                    "details": str(e),
                    "hint": (
                        "This employee is still referenced by one or more records. "
                        "Use ?force=true, or remove linked records first."
                    ),
                },
                status=status.HTTP_409_CONFLICT,
            )

        except Employee.DoesNotExist:
            return Response(
                {"error": "Employee does not exist"}, status=status.HTTP_404_NOT_FOUND
            )

    # class EmployeeListAPIView(APIView):
    """
    Retrieves a paginated list of employees with optional search functionality.
    Also handles POST and PUT requests for creating and updating employees.
    """

    permission_classes = [IsAuthenticated]

    @document_api(
        operation_description="Get list of employees with pagination and optional search by name or email",
        tags=["Employee Management"],
    )
    def get(self, request):
        user = request.user
        search = request.query_params.get("search")

        # Start with a base queryset with only required fields
        employees_queryset = Employee.objects.only(
            "id", "employee_first_name", "employee_last_name"
        )

        # Only return tokenized employees for regular users; admins see all
        # For /api/employee/list/employees/, return all employees for any authenticated user
        # (Assumes this view is used for both /employees/ and /list/employees/)
        # If you want /employees/ to remain self-only, split logic by request.path
        employees_queryset = Employee.objects.only(
            "id", "employee_first_name", "employee_last_name"
        )

        # Apply search filter if provided
        if search:
            employees_queryset = employees_queryset.filter(
                Q(employee_first_name__icontains=search)
                | Q(employee_last_name__icontains=search)
            )

        # Paginate
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(employees_queryset, request)
        page_employee_ids = [employee.id for employee in page] if page else []
        attendance_checked_in_ids = set(
            Attendance.objects.filter(
                employee_id_id__in=page_employee_ids,
                attendance_date=date.today(),
                attendance_clock_in__isnull=False,
                attendance_clock_out__isnull=True,
            ).values_list("employee_id_id", flat=True)
        )
        activity_checked_in_ids = set(
            AttendanceActivity.objects.filter(
                employee_id_id__in=page_employee_ids,
                attendance_date=date.today(),
                clock_in__isnull=False,
                clock_out__isnull=True,
            ).values_list("employee_id_id", flat=True)
        )
        checked_in_employee_ids = attendance_checked_in_ids | activity_checked_in_ids
        serializer = EmployeeListSerializer(
            page,
            many=True,
            context={"checked_in_employee_ids": checked_in_employee_ids},
        )
        return paginator.get_paginated_response(serializer.data)

    @method_decorator(permission_required("employee.add_employee"))
    def post(self, request):
        """Create a new employee"""
        data = request.data.copy()
        data["is_active"] = False
        serializer = EmployeeSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @method_decorator(permission_required("employee.change_employee"))
    def put(self, request):
        """Update an existing employee"""
        employee_id = request.data.get("id")
        if not employee_id:
            return Response(
                {"error": "Employee ID is required for update"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            employee = Employee.objects.get(pk=employee_id)
        except Employee.DoesNotExist:
            return Response(
                {"error": "Employee does not exist"},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = request.data.copy()
        data.pop("role", None)  # Remove id from data to avoid issues
        serializer = EmployeeSerializer(employee, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EmployeeListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    # allow file uploads (profile images) alongside JSON data
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @document_api(
        operation_description="Get list of employees with pagination and optional search by name",
        tags=["Employee Management"],
    )
    def get(self, request):
        search = request.query_params.get("search")

        # 🔹 Exclude soft deleted employees
        employees_queryset = Employee.objects.get_queryset()
        if any(field.name == "is_deleted" for field in Employee._meta.fields):
            employees_queryset = employees_queryset.filter(is_deleted=False)

        if search:
            employees_queryset = employees_queryset.filter(
                Q(employee_first_name__icontains=search)
                | Q(employee_last_name__icontains=search)
            )

        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(employees_queryset, request)

        page_employee_ids = [employee.id for employee in page] if page else []
        attendance_checked_in_ids = set(
            Attendance.objects.filter(
                employee_id_id__in=page_employee_ids,
                attendance_date=date.today(),
                attendance_clock_in__isnull=False,
                attendance_clock_out__isnull=True,
            ).values_list("employee_id_id", flat=True)
        )
        activity_checked_in_ids = set(
            AttendanceActivity.objects.filter(
                employee_id_id__in=page_employee_ids,
                attendance_date=date.today(),
                clock_in__isnull=False,
                clock_out__isnull=True,
            ).values_list("employee_id_id", flat=True)
        )
        checked_in_employee_ids = attendance_checked_in_ids | activity_checked_in_ids
        serializer = EmployeeListSerializer(
            page,
            many=True,
            context={"checked_in_employee_ids": checked_in_employee_ids},
        )
        return paginator.get_paginated_response(serializer.data)

    @method_decorator(permission_required("employee.add_employee"))
    def post(self, request):
        data = request.data.copy()
        data["is_active"] = False
        if any(field.name == "is_deleted" for field in Employee._meta.fields):
            data["is_deleted"] = False

        serializer = EmployeeSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @method_decorator(permission_required("employee.change_employee"))
    def put(self, request, pk):
        try:
            if any(field.name == "is_deleted" for field in Employee._meta.fields):
                employee = Employee.objects.get(pk=pk, is_deleted=False)
            else:
                employee = Employee.objects.get(pk=pk)
        except Employee.DoesNotExist:
            return Response(
                {"error": "Employee does not exist"},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = request.data.copy()
        data.pop("role", None)  # Prevent role update

        serializer = EmployeeSerializer(employee, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)


class EmployeeBankDetailsAPIView(APIView):
    """
    Manage employee bank details with CRUD operations.

    Methods:
        get(request, pk=None):
            - Retrieves bank details for a specific employee if `pk` is provided.
            - Returns a paginated list of all employee bank details if `pk` is not provided.

        post(request):
            - Creates a new bank detail entry for an employee.

        put(request, pk):
            - Updates existing bank details for an employee identified by `pk`.

        delete(request, pk):
            - Deletes bank details for an employee identified by `pk`.
    """

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return EmployeeBankDetails.objects.none()

        user = self.request.user
        if not user.is_authenticated:
            return EmployeeBankDetails.objects.none()

        queryset = EmployeeBankDetails._base_manager.all()
        perm = "employee.view_employeebankdetails"
        return permission_based_queryset(user, perm, queryset)

    @document_api(
        operation_description="Get employee bank details - retrieve specific employee's details or list all bank details with pagination",
        tags=["Employee Management"],
    )
    def get(self, request, pk=None):
        raw_count = EmployeeBankDetails.objects.count()
        filtered_count = self.get_queryset().count()

        print("RAW COUNT:", raw_count)
        print("FILTERED COUNT:", filtered_count)
        queryset = self.get_queryset()

        if pk is None:
            paginator = PageNumberPagination()
            page = paginator.paginate_queryset(queryset, request)
            serializer = EmployeeBankDetailsSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        try:
            bank_detail = queryset.get(pk=pk)
        except EmployeeBankDetails.DoesNotExist:
            return Response(
                {"error": "Bank details do not exist"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = EmployeeBankDetailsSerializer(bank_detail)
        return Response(serializer.data)

    @manager_or_owner_permission_required(
        EmployeeBankDetails, "employee.add_employeebankdetails"
    )
    def post(self, request):
        employee = request.data.get("employee_id")

        instance = EmployeeBankDetails.objects.filter(employee_id=employee).first()

        serializer = EmployeeBankDetailsSerializer(
            instance=instance, data=request.data, partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=400)

    @manager_or_owner_permission_required(
        EmployeeBankDetails, "employee.add_employeebankdetails"
    )
    def put(self, request, pk):
        try:
            bank_detail = EmployeeBankDetails.objects.get(pk=pk)
        except EmployeeBankDetails.DoesNotExist:
            return Response(
                {"error": "Bank details do not exist"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = EmployeeBankDetailsSerializer(bank_detail, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @manager_permission_required("employee.change_employeebankdetails")
    def delete(self, request, pk):
        try:
            bank_detail = EmployeeBankDetails.objects.get(pk=pk)
            bank_detail.delete()
        except EmployeeBankDetails.DoesNotExist:
            return Response(
                {"error": "Bank details do not exist"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as E:
            return Response({"error": str(E)}, status=400)

        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminEmployeeBankDetailsAPIView(APIView):
    """Return EmployeeBankDetails records only for employees with role='admin'.

    GET /api/employee/employee-bank-details/admin/ - list
    GET /api/employee/employee-bank-details/admin/<pk>/ - detail
    Access restricted to admin users (employee.role == 'admin' OR is_staff/is_superuser).
    """

    permission_classes = [IsAuthenticated]

    @document_api(
        operation_description="Get bank details for admin employees only (list or detail)",
        tags=["Employee Management"],
    )
    def get(self, request, pk=None):
        user = request.user
        # admin check: employee role or staff/superuser
        is_admin = False
        if (
            hasattr(user, "employee_get")
            and getattr(user.employee_get, "role", None) == "admin"
        ):
            is_admin = True
        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
            is_admin = True
        if not is_admin:
            return Response(
                {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
            )

        if pk is None:
            queryset = EmployeeBankDetails.objects.filter(employee_id__role="admin")
            paginator = PageNumberPagination()
            page = paginator.paginate_queryset(queryset, request)
            serializer = EmployeeBankDetailsSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        # detail
        try:
            bank_detail = EmployeeBankDetails.objects.get(
                pk=pk, employee_id__role="admin"
            )
        except EmployeeBankDetails.DoesNotExist:
            return Response(
                {"error": "Bank details do not exist or not an admin employee"},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = EmployeeBankDetailsSerializer(bank_detail)
        return Response(serializer.data)


class EmployeeWorkInformationAPIView(APIView):
    """
    Manage employee work information with CRUD operations.

    Methods:
        get(request, pk=None):
            - If pk provided: Retrieves work information for a specific employee
            - If pk not provided: Returns list of all work information

        post(request):
            - Creates a new work information entry for an employee.

        put(request, pk):
            - Updates existing work information for an employee identified by `pk`.

        delete(request, pk):
            - Deletes work information for an employee identified by `pk`.
    """

    permission_classes = [IsAuthenticated]

    @document_api(
        operation_description="Get employee work information - retrieve specific employee or list all work information with pagination",
        tags=["Employee Management"],
    )
    def get(self, request, pk=None):
        print(
            "GET EmployeeWorkInformation - PK:",
            pk,
            "Query Params:",
            request.query_params,
        )
        # Allow lookup by employee_id as well as pk
        employee_id = request.query_params.get("employee_id")
        if employee_id:
            try:
                work_info = EmployeeWorkInformation.objects.get(employee_id=employee_id)
            except EmployeeWorkInformation.DoesNotExist:
                return Response(
                    {"error": "Work information not found for this employee_id"},
                    status=404,
                )
            serializer = EmployeeWorkInformationSerializer(work_info)
            return Response(serializer.data, status=200)
        if pk is None:
            queryset = (
                EmployeeWorkInformation._base_manager.select_related("employee_id")
                .all()
                .order_by("employee_id_id")
            )
            # ✅ order
            print("WORK INFO COUNT:", queryset.count())
            paginator = PageNumberPagination()
            paginator.page_size = 10

            page = paginator.paginate_queryset(queryset, request)

            if page is not None:
                serializer = EmployeeWorkInformationSerializer(page, many=True)
                return paginator.get_paginated_response(serializer.data)

            # 🔸 fallback (no pagination)
            serializer = EmployeeWorkInformationSerializer(queryset, many=True)
            return Response(serializer.data, status=200)
        else:
            # Get specific work information by PK
            try:
                work_info = EmployeeWorkInformation.objects.get(pk=pk)
            except EmployeeWorkInformation.DoesNotExist:
                return Response({"error": "Work information not found"}, status=404)
            serializer = EmployeeWorkInformationSerializer(work_info)
            return Response(serializer.data, status=200)
 
    @manager_permission_required("employee.change_employeeworkinformation")
    

    def put(self, request, pk=None):
        employee_id = request.data.get("employee_id")
        print("PUT EmployeeWorkInformation - PK:", pk, "Employee ID:", employee_id)

        try:
            if employee_id:
                work_info = EmployeeWorkInformation.objects.get(
                    employee_id_id=employee_id
                )
            else:
                work_info = EmployeeWorkInformation.objects.get(pk=pk)
        except EmployeeWorkInformation.DoesNotExist:
            return Response(
                {"error": "Work information not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = request.data.copy()

        # ✅ translate employee_id → user_id for serializer
        if "employee_id" in data:
            data.pop("employee_id")

        serializer = EmployeeWorkInformationSerializer(
            work_info, data=data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)

    @method_decorator(
        permission_required("employee.delete_employeeworkinformation"), name="dispatch"
    )
    def delete(self, request, pk=None):
        employee_id = request.data.get("employee_id") or request.query_params.get(
            "employee_id"
        )
        if employee_id:
            try:
                work_info = EmployeeWorkInformation.objects.get(employee_id=employee_id)
            except EmployeeWorkInformation.DoesNotExist:
                return Response(
                    {"error": "Work information not found for this employee_id"},
                    status=404,
                )
        elif pk is not None:
            try:
                work_info = EmployeeWorkInformation.objects.get(pk=pk)
            except EmployeeWorkInformation.DoesNotExist:
                return Response({"error": "Work information not found"}, status=404)
        else:
            return Response({"error": "employee_id or pk required"}, status=400)
        work_info.delete()
        return Response(
            {"message": "Work information deleted successfully."},
            status=status.HTTP_200_OK,
        )


class EmployeeWorkInfoExportView(APIView):
    """
    Endpoint for exporting employee work information.

    Methods:
        get(request):
            - Exports work information data based on user permissions.
    """


class EmployeeMyWorkInfoAPIView(APIView):
    """Returns the authenticated user's EmployeeWorkInformation.

    GET /api/employee/work-info/
    - Requires authentication (`Authorization: Token <token>`)
    - Returns 200 with the user's `EmployeeWorkInformation` if it exists
    - Returns 404 if the user has no employee record or work information

    Note: Admins also use this endpoint but will only receive *their own* work information.
    """

    permission_classes = [IsAuthenticated]

    @document_api(
        operation_description="Get the authenticated employee's work information",
        tags=["Employee Management"],
    )
    def get(self, request):
        user = request.user
        employee = getattr(user, "employee_get", None)
        if not employee:
            return Response(
                {"error": "No employee record found for the authenticated user."},
                status=404,
            )
        try:
            work_info = EmployeeWorkInformation.objects.get(employee_id=employee)
        except EmployeeWorkInformation.DoesNotExist:
            return Response(
                {"error": "Work information not found for this employee."}, status=404
            )
        serializer = EmployeeWorkInformationSerializer(work_info)
        return Response(serializer.data, status=200)


class EmployeeWorkInfoImportView(APIView):
    """
    Endpoint for importing employee work information.

    Methods:
        get(request):
            - Handles the importing of work information data based on user permissions.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @manager_permission_required("employee.add_employeeworkinformation")
    def get(self, request):
        return work_info_import(request)

    @manager_permission_required("employee.add_employeeworkinformation")
    def post(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return Response({"error": "No file uploaded."}, status=400)

        try:
            data_frame = read_import_file(upload)
            valid, error_message = validate_headers(data_frame, EMPLOYEE_IMPORT_HEADERS)
            if not valid:
                return Response({"error": error_message}, status=400)
            return Response(import_employee_dataframe(data_frame), status=200)
        except Exception as exc:
            return Response({"error": str(exc)}, status=400)


class EmployeeBulkUpdateView(APIView):
    """
    Endpoint for bulk updating employee and work information.

    Permissions:
        - Requires authentication and "change_employee" permission.

    Methods:
        put(request):
            - Updates multiple employees and their work information.
    """

    permission_classes = [IsAuthenticated]

    @method_decorator(permission_required("employee.change_employee"), name="dispatch")
    def put(self, request):
        employee_ids = request.data.get("ids", [])
        employees = Employee.objects.filter(id__in=employee_ids)
        employee_work_info = EmployeeWorkInformation.objects.filter(
            employee_id__in=employees
        )
        employee_data = request.data.get("employee_data", {})
        work_info_data = request.data.get("employee_work_info", {})
        fields_to_remove = [
            "badge_id",
            "employee_first_name",
            "employee_last_name",
            "is_active",
            "email",
            "phone",
            "employee_bank_details__account_number",
        ]
        for field in fields_to_remove:
            employee_data.pop(field, None)
            work_info_data.pop(field, None)

        try:
            employees.update(**employee_data)
            employee_work_info.update(**work_info_data)
        except Exception as e:
            return Response({"error": str(e)}, status=400)
        return Response({"status": "success"}, status=200)


class ActiontypeView(APIView):
    serializer_class = ActiontypeSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        if pk:
            action_type = object_check(Actiontype, pk)
            if action_type is None:
                return Response({"error": "Actiontype not found"}, status=404)
            serializer = self.serializer_class(action_type)
            return Response(serializer.data, status=200)
        action_types = Actiontype.objects.all()
        paginater = PageNumberPagination()
        page = paginater.paginate_queryset(action_types, request)
        serializer = self.serializer_class(page, many=True)
        return paginater.get_paginated_response(serializer.data)

    def post(self, request):
        if permission_check(request, "employee.add_actiontype") is False:
            return Response({"error": "No permission"}, status=401)
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

    def put(self, request, pk):
        if permission_check(request, "employee.change_actiontype") is False:
            return Response({"error": "No permission"}, status=401)
        action_type = object_check(Actiontype, pk)
        if action_type is None:
            return Response({"error": "Actiontype not found"}, status=404)
        serializer = self.serializer_class(action_type, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)

    def delete(self, request, pk):
        if permission_check(request, "employee.delete_actiontype") is False:
            return Response({"error": "No permission"}, status=401)
        action_type = object_check(Actiontype, pk)
        if action_type is None:
            return Response({"error": "Actiontype not found"}, status=404)
        response, status_code = object_delete(Actiontype, pk)
        return Response(response, status=status_code)


class DisciplinaryActionAPIView(APIView):
    """
    Endpoint for managing disciplinary actions.

    Permissions:
        - Requires authentication.

    Methods:
        get(request, pk=None):
            - Retrieves a specific disciplinary action by `pk` or lists all disciplinary actions with optional filtering.

        post(request):
            - Creates a new disciplinary action.

        put(request, pk):
            - Updates an existing disciplinary action by `pk`.

        delete(request, pk):
            - Deletes a specific disciplinary action by `pk`.
    """

    filterset_class = DisciplinaryActionFilter
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return DisciplinaryAction.objects.get(pk=pk)
        except DisciplinaryAction.DoesNotExist:
            raise Http404

    def get(self, request, pk=None):
        if pk:
            employee = request.user.employee_get
            disciplinary_action = self.get_object(pk)
            is_manager = (
                True
                if employee.get_subordinate_employees()
                & disciplinary_action.employee_id.all()
                else False
            )
            if (
                (employee == disciplinary_action.employee_id)
                or is_manager
                or request.user.has_perm("employee.view_disciplinaryaction")
            ):
                serializer = DisciplinaryActionSerializer(disciplinary_action)
                return Response(serializer.data, status=200)
            return Response({"error": "No permission"}, status=400)
        else:
            employee = request.user.employee_get
            is_manager = EmployeeWorkInformation.objects.filter(
                reporting_manager_id=employee
            ).exists()
            subordinates = employee.get_subordinate_employees()

            if request.user.has_perm("employee.view_disciplinaryaction"):
                queryset = DisciplinaryAction.objects.all()
            elif is_manager:
                queryset_subordinates = DisciplinaryAction.objects.filter(
                    employee_id__in=subordinates
                )
                queryset_employee = DisciplinaryAction.objects.filter(
                    employee_id=employee
                )
                queryset = queryset_subordinates | queryset_employee
            else:
                queryset = DisciplinaryAction.objects.filter(employee_id=employee)

            paginator = PageNumberPagination()
            disciplinary_actions = queryset
            disciplinary_action_filter_queryset = self.filterset_class(
                request.GET, queryset=disciplinary_actions
            ).qs
            page = paginator.paginate_queryset(
                disciplinary_action_filter_queryset, request
            )
            serializer = DisciplinaryActionSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        if permission_check(request, "employee.add_disciplinaryaction") is False:
            return Response({"error": "No permission"}, status=401)
        serializer = DisciplinaryActionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        if permission_check(request, "employee.add_disciplinaryaction") is False:
            return Response({"error": "No permission"}, status=401)
        disciplinary_action = self.get_object(pk)
        serializer = DisciplinaryActionSerializer(
            disciplinary_action, data=request.data
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        if permission_check(request, "employee.add_disciplinaryaction") is False:
            return Response({"error": "No permission"}, status=401)
        disciplinary_action = self.get_object(pk)
        disciplinary_action.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PolicyAPIView(APIView):
    """
    Endpoint for managing policies.

    Permissions:
        - Requires authentication.

    Methods:
        get(request, pk=None):
            - Retrieves a specific policy by `pk` or lists all policies with optional search functionality.

        post(request):
            - Creates a new policy.

        put(request, pk):
            - Updates an existing policy by `pk`.

        delete(request, pk):
            - Deletes a specific policy by `pk`.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _is_admin(self, request):
        user = request.user
        employee = getattr(user, "employee_get", None)
        return bool(
            user.is_superuser
            or user.is_staff
            or (employee and getattr(employee, "role", None) == "admin")
        )

    def get_object(self, pk):
        try:
            return Policy.objects.get(pk=pk)
        except Policy.DoesNotExist:
            raise Http404

    def get(self, request, pk=None):
        if pk:
            policy = self.get_object(pk)
            serializer = EmployeePolicySerializer(policy, context={"request": request})
            return Response(serializer.data)
        else:
            search = request.GET.get("search", None)
            if search:
                policies = Policy.objects.filter(title__icontains=search)
            else:
                policies = Policy.objects.all()
            paginator = PageNumberPagination()
            page = paginator.paginate_queryset(policies, request)
            serializer = EmployeePolicySerializer(
                page, many=True, context={"request": request}
            )
            return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        if not self._is_admin(request):
            return Response(
                {"error": "Only admin can create policies."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = EmployeePolicySerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

    def put(self, request, pk):
        if permission_check(request, "employee.change_policy") is False:
            return Response({"error": "No permission"}, status=401)
        policy = self.get_object(pk)
        serializer = EmployeePolicySerializer(
            policy, data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, pk):
        if permission_check(request, "employee.delete_policy") is False:
            return Response({"error": "No permission"}, status=401)
        policy = self.get_object(pk)
        policy.delete()
        return Response(status=204)


class DocumentRequestAPIView(APIView):
    """
    Endpoint for managing document requests.

    Permissions:
        - Requires authentication.
        - Specific actions require manager-level permissions.

    Methods:
        get(request, pk=None):
            - Retrieves a specific document request by `pk` or lists all document requests with pagination.

        post(request):
            - Creates a new document request and notifies relevant employees.

        put(request, pk):
            - Updates an existing document request by `pk`.

        delete(request, pk):
            - Deletes a specific document request by `pk`.
    """

    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return DocumentRequest.objects.get(pk=pk)
        except DocumentRequest.DoesNotExist:
            raise Http404

    def get(self, request, pk=None):
        if pk:
            document_request = self.get_object(pk)
            serializer = DocumentRequestSerializer(document_request)
            data = serializer.data
            data.pop("id", None)
            return Response(data)
        else:
            document_requests = DocumentRequest.objects.all()
            pagination = PageNumberPagination()
            page = pagination.paginate_queryset(document_requests, request)
            serializer = DocumentRequestSerializer(page, many=True)
            results = serializer.data
            for item in results:
                item.pop("id", None)
            return pagination.get_paginated_response(results)

    @manager_permission_required("horilla_documents.add_documentrequests")
    def post(self, request):
        serializer = DocumentRequestSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            obj = serializer.save()
            try:
                employees = [user.employee_user_id for user in obj.employee_id.all()]

                notify.send(
                    request.user.employee_get,
                    recipient=employees,
                    verb=f"{request.user.employee_get} requested a document.",
                    verb_ar=f"طلب {request.user.employee_get} مستنداً.",
                    verb_de=f"{request.user.employee_get} hat ein Dokument angefordert.",
                    verb_es=f"{request.user.employee_get} solicitó un documento.",
                    verb_fr=f"{request.user.employee_get} a demandé un document.",
                    redirect="/employee/employee-profile",
                    icon="chatbox-ellipses",
                    api_redirect=f"/api/employee/document-request/{obj.id}",
                )
            except:
                pass
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @manager_permission_required("horilla_documents.change_documentrequests")
    def put(self, request, pk):
        # pk is employee_id, update all document requests for this employee
        from horilla_documents.models import DocumentRequest

        document_requests = DocumentRequest.objects.filter(employee_id__id=pk)
        if not document_requests.exists():
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        updated = []
        for dr in document_requests:
            serializer = DocumentRequestSerializer(
                dr, data=request.data, partial=True, context={"request": request}
            )
            if serializer.is_valid():
                serializer.save()
                data = serializer.data
                data.pop("id", None)
                updated.append(data)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"employee_id": pk, "updated_requests": updated}, status=status.HTTP_200_OK
        )

    @method_decorator(permission_required("employee.delete_employee"))
    def delete(self, request, pk):
        # pk is employee_id, delete all document requests for this employee
        from horilla_documents.models import Document, DocumentRequest

        document_requests = DocumentRequest.objects.filter(employee_id__id=pk)
        if not document_requests.exists():
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        deleted_ids = list(document_requests.values_list("id", flat=True))
        # Delete related Document objects first
        for dr in document_requests:
            Document.objects.filter(document_request_id=dr).delete()
        document_requests.delete()
        return Response(
            {"employee_id": pk, "deleted_request_ids": deleted_ids},
            status=status.HTTP_200_OK,
        )


class DocumentAPIView(APIView):
    filterset_class = DocumentRequestFilter
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Document.objects.get(pk=pk)
        except Document.DoesNotExist:
            raise Http404

    def get(self, request, pk=None):
        if pk:
            document = self.get_object(pk)
            serializer = DocumentSerializer(document)
            return Response(serializer.data)
        else:
            documents = Document.objects.all()
            document_requests_filtered = self.filterset_class(
                request.GET, queryset=documents
            ).qs
            paginator = PageNumberPagination()
            page = paginator.paginate_queryset(document_requests_filtered, request)
            serializer = DocumentSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

    @manager_or_owner_permission_required(
        DocumentRequest, "horilla_documents.add_document"
    )
    def post(self, request):
        serializer = DocumentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            try:
                notify.send(
                    request.user.employee_get,
                    recipient=request.user.employee_get.get_reporting_manager().employee_user_id,
                    verb=f"{request.user.employee_get} uploaded a document",
                    verb_ar=f"قام {request.user.employee_get} بتحميل مستند",
                    verb_de=f"{request.user.employee_get} hat ein Dokument hochgeladen",
                    verb_es=f"{request.user.employee_get} subió un documento",
                    verb_fr=f"{request.user.employee_get} a téléchargé un document",
                    redirect=f"/employee/employee-view/{request.user.employee_get.id}/",
                    icon="chatbox-ellipses",
                    api_redirect=f"/api/employee/documents/",
                )
            except:
                pass
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @method_decorator(owner_can_enter("horilla_documents.change_document", Employee))
    def put(self, request, pk):
        document = self.get_object(pk)
        serializer = DocumentSerializer(document, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @method_decorator(owner_can_enter("horilla_documents.delete_document", Employee))
    def delete(self, request, pk):
        document = self.get_object(pk)
        document.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentRequestApproveRejectView(APIView):
    permission_classes = [IsAuthenticated]

    @manager_permission_required("horilla_documents.add_document")
    def post(self, request, id, status):
        document = Document.objects.filter(id=id).first()
        document.status = status
        document.save()
        return Response({"status": "success"}, status=200)


class DocumentBulkApproveRejectAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @manager_permission_required("horilla_documents.add_document")
    def put(self, request):
        ids = request.data.get("ids", None)
        status = request.data.get("status", None)
        status_code = 200

        if ids:
            documents = Document.objects.filter(id__in=ids)
            response = []
            for document in documents:
                if not document.document:
                    status_code = 400
                    response.append({"id": document.id, "error": "No documents"})
                    continue
                response.append({"id": document.id, "status": "success"})
                document.status = status
                document.save()
        return Response(response, status=status_code)


class EmployeeBulkArchiveView(APIView):
    permission_classes = [IsAuthenticated]

    @method_decorator(permission_required("employee.delete_employee"))
    def post(self, request, is_active):
        ids = request.data.get("ids")
        error = []
        for employee_id in ids:
            employee = Employee.objects.get(id=employee_id)
            employee.is_active = is_active
            employee.employee_user_id.is_active = is_active
            if employee.get_archive_condition() is False:
                employee.save()
            error.append(
                {
                    "employee": str(employee),
                    "error": "Related model found for this employee. ",
                }
            )
        return Response(error, status=200)


class EmployeeArchiveView(APIView):
    permission_classes = [IsAuthenticated]

    @method_decorator(permission_required("employee.delete_employee"))
    def post(self, request, id, is_active):
        employee = Employee.objects.get(id=id)
        employee.is_active = is_active
        employee.employee_user_id.is_active = is_active
        response = None
        if employee.get_archive_condition() is False:
            employee.save()
        else:
            response = {
                "employee": str(employee),
                "error": employee.get_archive_condition(),
            }
        return Response(response, status=200)


class EmployeeSelectorView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee = request.user.employee_get
        employees = Employee.objects.filter(employee_user_id=request.user)

        is_manager = EmployeeWorkInformation.objects.filter(
            reporting_manager_id=employee
        ).exists()

        if is_manager:
            employees = Employee.objects.filter(
                Q(pk=employee.pk) | Q(employee_work_info__reporting_manager_id=employee)
            )
        if request.user.has_perm("employee.view_employee"):
            employees = Employee.objects.all()

        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(employees, request)
        serializer = EmployeeSelectorSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class ReportingManagerCheck(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if Employee.objects.filter(
            employee_work_info__reporting_manager_id=request.user.employee_get
        ):
            return Response(status=200)
        return Response(status=404)


class ShiftRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        if pk:
            shift_request = ShiftRequest.objects.get(pk=pk)
            serializer = ShiftRequestSerializer(shift_request)
            data = serializer.data
            data.pop("id", None)
            if "employee" in data:
                data["employee_id"] = data.pop("employee")
            return Response(data)
        else:
            shift_requests = ShiftRequest.objects.all()
            paginator = PageNumberPagination()
            page = paginator.paginate_queryset(shift_requests, request)
            serializer = ShiftRequestSerializer(page, many=True)
            results = serializer.data
            for item in results:
                item.pop("id", None)
                if "employee" in item:
                    item["employee_id"] = item.pop("employee")
            return paginator.get_paginated_response(results)

    def post(self, request):
        serializer = ShiftRequestSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        # pk is employee_id, update all shift requests for this employee
        from employee.models_shift_request import ShiftRequest

        shift_requests = ShiftRequest.objects.filter(employee__id=pk)
        if not shift_requests.exists():
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        updated = []
        for sr in shift_requests:
            serializer = ShiftRequestSerializer(sr, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                data = serializer.data
                data.pop("id", None)
                if "employee" in data:
                    data["employee_id"] = data.pop("employee")
                updated.append(data)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"employee_id": pk, "updated_requests": updated}, status=status.HTTP_200_OK
        )

    def patch(self, request, pk):
        shift_request = ShiftRequest.objects.get(pk=pk)
        serializer = ShiftRequestSerializer(
            shift_request, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            data = serializer.data
            data.pop("id", None)
            if "employee" in data:
                data["employee_id"] = data.pop("employee")
            return Response(data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        # pk is employee_id, delete all shift requests for this employee
        from employee.models_shift_request import ShiftRequest

        shift_requests = ShiftRequest.objects.filter(employee__id=pk)
        if not shift_requests.exists():
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        deleted_ids = list(shift_requests.values_list("id", flat=True))
        shift_requests.delete()
        return Response(
            {"employee_id": pk, "deleted_request_ids": deleted_ids},
            status=status.HTTP_200_OK,
        )


from django.shortcuts import get_object_or_404


class DeletedEmployeeAPIView(APIView):
    """
    GET  -> List all archived (inactive) employees
    PUT  -> Restore an archived employee
    """

    permission_classes = [IsAuthenticated]

    # =========================
    # LIST DELETED EMPLOYEES
    # =========================
    @method_decorator(permission_required("employee.view_employee"))
    def get(self, request):
        deleted_employees = Employee.objects.filter(is_active=False)

        serializer = EmployeeListSerializer(deleted_employees, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # =========================
    # UNDELETE EMPLOYEE
    # =========================
    @method_decorator(permission_required("employee.change_employee"))
    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Employee ID required"}, status=status.HTTP_400_BAD_REQUEST
            )

        employee = get_object_or_404(Employee, pk=pk, is_active=False)

        employee.is_active = True
        update_fields = ["is_active"]
        if employee.employee_user_id:
            employee.employee_user_id.is_active = True
            employee.employee_user_id.save(update_fields=["is_active"])
        employee.save(update_fields=update_fields)

        return Response(
            {"message": "Employee restored successfully", "employee_id": employee.id},
            status=status.HTTP_200_OK,
        )
