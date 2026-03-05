from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from attendance.models import AttendanceActivity


class LateComeEarlyOutCustomAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        # 1. Setup Filters
        badge_id = request.query_params.get("Badge_id")
        attendance_date = request.query_params.get("Attendance_Date")
        filters = {}

        # Only fetch records that actually have a flag
        from django.db.models import Q

        query = Q(is_late_come=True) | Q(is_early_out=True)

        if badge_id:
            filters["employee_id__badge_id"] = badge_id
        if attendance_date:
            filters["attendance_date"] = attendance_date

        # 2. Permission-based Queryset
        user = request.user
        if user.is_superuser or user.is_staff:
            queryset = AttendanceActivity.objects.filter(
                query, **filters
            ).select_related("employee_id")
        else:
            employee = getattr(user, "employee_get", None)
            if employee:
                queryset = AttendanceActivity.objects.filter(
                    query, employee_id=employee, **filters
                ).select_related("employee_id")
            else:
                return Response([], status=200)

        # 3. Format Results
        results = []
        for activity in queryset:
            employee = activity.employee_id
            results.append(
                {
                    "id": activity.id,
                    "employee_id": employee.id,
                    "Employee_name": f"{employee.employee_first_name} {employee.employee_last_name or ''}",
                    "Badge_id": employee.badge_id,
                    "is_late_come": activity.is_late_come,
                    "is_early_out": activity.is_early_out,
                    "Attendance_Date": str(activity.attendance_date),
                    "Check-In": str(activity.clock_in) if activity.clock_in else None,
                    "Check-Out": (
                        str(activity.clock_out) if activity.clock_out else None
                    ),
                    "In_Date": str(activity.clock_in_date),
                    "Out_Date": str(activity.clock_out_date),
                    # "Penalities": activity.get_penalties() if you have this method,
                    "Action": "View/Approve",
                }
            )

        return Response(results)

    def delete(self, request, pk=None):
        if pk is not None:
            try:
                obj = AttendanceActivity.objects.get(pk=pk)
                # Usually you don't delete the activity, you might just reset the flags
                obj.is_late_come = False
                obj.is_early_out = False
                obj.save()
                return Response({"message": "Flags reset successfully"}, status=200)
            except AttendanceActivity.DoesNotExist:
                return Response({"detail": "Not found."}, status=404)
        return Response({"detail": "Provide ID"}, status=400)
