from datetime import date

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from employee.filters import EmployeeFilter


class OfflineEmployeesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = date.today()
        queryset = (
            EmployeeFilter({"not_in_yet": today})
            .qs.exclude(employee_work_info__isnull=True)
            .filter(is_active=True)
        )
        results = []
        for emp in queryset:
            results.append(
                {
                    "id": emp.id,
                    "first_name": emp.employee_first_name,
                    "last_name": emp.employee_last_name,
                    "badge_id": emp.badge_id,
                    "email": emp.email,
                    "is_active": emp.is_active,
                }
            )
        return Response(results)
