from rest_framework import serializers

from base.models import WorkTypeRequestComment


class WorkTypeRequestCommentSerializer(serializers.ModelSerializer):
    employee_first_name = serializers.CharField(
        source="employee_id.employee_first_name", read_only=True
    )
    employee_last_name = serializers.CharField(
        source="employee_id.employee_last_name", read_only=True
    )

    class Meta:
        model = WorkTypeRequestComment
        fields = [
            "id",
            "employee_id",
            "employee_first_name",
            "employee_last_name",
            "comment",
        ]
