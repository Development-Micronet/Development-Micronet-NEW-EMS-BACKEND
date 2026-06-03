from rest_framework import serializers

from employee.models import Employee
from employee.models_shift_request import ShiftRequest


class ShiftRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = ShiftRequest
        fields = [
            "employee_id",
            "employee_name",
            "shift_name",
            "start_time",
            "end_time",
            "date",
            "reason",
            "status",
        ]

    employee_id = serializers.PrimaryKeyRelatedField(
        source="employee", queryset=Employee.objects.all()
    )

    def get_employee_name(self, obj):
        return obj.employee.get_full_name()
