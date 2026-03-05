from rest_framework import serializers

from employee.models import Employee


class GetEmployeeSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = ["id", "full_name", "employee_profile"]

    def get_full_name(self, obj):
        return obj.get_full_name()


class LoginRequestSerializer(serializers.Serializer):
    """Simple request body for the login endpoint."""

    username = serializers.CharField()
    password = serializers.CharField()


class ForgotPasswordRequestSerializer(serializers.Serializer):
    """Request body for forgot password endpoint."""

    email = serializers.EmailField()


class ResetPasswordRequestSerializer(serializers.Serializer):
    """Request body for reset password endpoint."""

    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField()
    confirm_password = serializers.CharField()

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "New password and confirm password do not match."}
            )
        return attrs
