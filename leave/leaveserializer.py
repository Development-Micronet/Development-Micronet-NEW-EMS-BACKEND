from rest_framework import serializers

from .models import LeaveNew, LeaveTypeNew


class LeaveNewCreateSerializer(serializers.ModelSerializer):
    end_date_breakdown = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, write_only=True
    )

    class Meta:
        model = LeaveNew
        fields = [
            "id",
            "leave_type",
            "start_date",
            "start_date_breakdown",
            "end_date",
            "end_date_breakdown",
            "description",
        ]

    def validate(self, data):
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "End date cannot be before start date."}
            )

        return data


class LeaveNewEmployeeReadSerializer(serializers.ModelSerializer):
    leave_id = serializers.IntegerField(source="id", read_only=True)
    end_date_breakdown = serializers.SerializerMethodField()

    class Meta:
        model = LeaveNew
        fields = [
            "leave_id",
            "leave_type",
            "start_date",
            "start_date_breakdown",
            "end_date",
            "end_date_breakdown",
            "number_of_days",
            "status",
            "description",
            "comments",
        ]

    def get_end_date_breakdown(self, obj):
        return getattr(obj, "end_date_breakdown", "full_day")


class LeaveNewAdminReadSerializer(serializers.ModelSerializer):
    leave_id = serializers.IntegerField(source="id", read_only=True)
    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = LeaveNew
        fields = [
            "leave_id",
            "employee_name",
            "leave_type",
            "start_date",
            "end_date",
            "number_of_days",
            "status",
            "description",
            "comments",
        ]

    def get_employee_name(self, obj):
        emp = obj.employee
        return f"{emp.employee_first_name} {emp.employee_last_name}"


class LeaveNewAdminUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveNew
        fields = [
            "status",
            "comments",
        ]

    def validate_status(self, value):
        allowed = ["approved", "rejected", "cancelled"]
        if value not in allowed:
            raise serializers.ValidationError(
                "Status must be approved, rejected, or cancelled."
            )
        return value


# leave/leaveserializer.py


class LeaveTypeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveTypeNew
        fields = ["id", "name", "is_paid", "total_days"]


# leave/leaveserializer.py


class AdminAssignLeaveSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    leave_type_id = serializers.IntegerField()

    def validate(self, data):
        from employee.models import Employee
        from leave.models import LeaveTypeNew

        if not Employee.objects.filter(id=data["employee_id"]).exists():
            raise serializers.ValidationError("Invalid employee")

        if not LeaveTypeNew.objects.filter(id=data["leave_type_id"]).exists():
            raise serializers.ValidationError("Invalid leave type")

        return data
