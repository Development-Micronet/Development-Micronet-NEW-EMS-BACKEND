from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from attendance.models import AttendanceOverTime
from employee.models import Employee


class AttendanceHourAccountAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        user = request.user
        # Only admin/staff can see all employees; regular users see only their own data
        if pk is not None:
            try:
                obj = AttendanceOverTime.objects.select_related("employee_id").get(
                    pk=pk
                )
            except AttendanceOverTime.DoesNotExist:
                return Response({"detail": "Not found."}, status=404)
            # If not admin/staff, restrict to own data
            if not (user.is_superuser or user.is_staff):
                if (
                    not hasattr(user, "employee_get")
                    or obj.employee_id != user.employee_get
                ):
                    return Response({"detail": "Not allowed."}, status=403)
            result = {
                "Employee_name": f"{obj.employee_id.employee_first_name} {obj.employee_id.employee_last_name or ''}",
                "id": obj.employee_id.id,
                "badge_id": obj.employee_id.badge_id,
                "Month": obj.month,
                "Year": obj.year,
                "worked Hours": obj.worked_hours,
                "Hours to Validate": obj.not_validated_hrs(),
                "Pending Hours": obj.pending_hours,
                "Overtime Hours": obj.overtime,
                "Not Approved OT Hours": obj.not_approved_ot_hrs(),
                "Action": "View/Approve",
            }
            return Response(result)
        # List view
        if user.is_superuser or user.is_staff:
            queryset = AttendanceOverTime.objects.select_related("employee_id").all()
        else:
            if hasattr(user, "employee_get"):
                queryset = AttendanceOverTime.objects.select_related(
                    "employee_id"
                ).filter(employee_id=user.employee_get)
            else:
                return Response([], status=200)
        results = []
        for obj in queryset:
            results.append(
                {
                    "Employee_name": f"{obj.employee_id.employee_first_name} {obj.employee_id.employee_last_name or ''}",
                    "id": obj.employee_id.id,
                    "badge_id": obj.employee_id.badge_id,
                    "Month": obj.month,
                    "Year": obj.year,
                    "worked Hours": obj.worked_hours,
                    "Hours to Validate": obj.not_validated_hrs(),
                    "Pending Hours": obj.pending_hours,
                    "Overtime Hours": obj.overtime,
                    "Not Approved OT Hours": obj.not_approved_ot_hrs(),
                    "Action": "View/Approve",
                }
            )
        return Response(results)

    def delete(self, request, pk=None):
        if pk is None:
            return Response({"detail": 'Method "DELETE" not allowed.'}, status=405)
        try:
            obj = AttendanceOverTime.objects.get(pk=pk)
            obj.delete()
            return Response({"message": "Overtime deleted successfully"}, status=204)
        except AttendanceOverTime.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
