from rest_framework import serializers

from employee.models import DisciplinaryAction


class DisciplinaryActionSerializer(serializers.ModelSerializer):
    employee_names = serializers.SerializerMethodField(read_only=True)
    action_type = serializers.CharField(source="action.title", read_only=True)
    attachment_url = serializers.SerializerMethodField(read_only=True)
    attachment = serializers.FileField(write_only=True, required=False, allow_null=True)

    # Accept action as string or PK
    action = serializers.CharField(write_only=True)

    class Meta:
        model = DisciplinaryAction
        fields = [
            "id",
            "employee_id",
            "employee_names",
            "action",
            "action_type",
            "description",
            "unit_in",
            "days",
            "hours",
            "start_date",
            "attachment",
            "attachment_url",
        ]

    def get_employee_names(self, obj):
        return ", ".join(
            [
                f"{e.employee_first_name} {e.employee_last_name}".strip()
                for e in obj.employee_id.all()
            ]
        )

    def get_attachment_url(self, obj):
        return obj.attachment.url if obj.attachment else None

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Show action_type as the human-readable name
        rep["action_type"] = instance.action.title if instance.action else None
        return rep

    def to_internal_value(self, data):
        # Backward-compatible alias support
        mutable = data.copy()
        if "action" not in mutable and "action_type" in mutable:
            mutable["action"] = mutable.get("action_type")

        # Accept single employee id as well as list
        employee_value = mutable.get("employee_id")
        if employee_value is not None and not isinstance(employee_value, list):
            mutable["employee_id"] = [employee_value]

        return super().to_internal_value(mutable)

    def validate_action(self, value):
        from employee.models import Actiontype

        # If already an Actiontype instance, return as is
        if isinstance(value, Actiontype):
            return value
        # If value is int or digit string, treat as PK
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            try:
                return Actiontype.objects.get(pk=int(value))
            except Actiontype.DoesNotExist:
                raise serializers.ValidationError(
                    "Actiontype with this ID does not exist."
                )
        # Otherwise, treat as title (case-insensitive)
        if isinstance(value, str):
            action, _ = Actiontype.objects.get_or_create(
                title=value, defaults={"action_type": "warning"}
            )
            return action
        raise serializers.ValidationError("Invalid type for action field.")

    def create(self, validated_data):
        from django.utils import timezone

        action_value = validated_data.pop("action", None)
        if action_value:
            validated_data["action"] = self.validate_action(action_value)
        employees = validated_data.pop("employee_id", [])
        if not validated_data.get("start_date"):
            validated_data["start_date"] = timezone.localdate()
        instance = DisciplinaryAction.objects.create(**validated_data)
        if employees:
            instance.employee_id.set(employees)
        return instance

    def update(self, instance, validated_data):
        action_value = validated_data.pop("action", None)
        if action_value:
            validated_data["action"] = self.validate_action(action_value)
        employees = validated_data.pop("employee_id", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if employees is not None:
            instance.employee_id.set(employees)
        return instance


import datetime

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import serializers

from base.models import (
    Company,
    Department,
    EmployeeShift,
    EmployeeShiftDay,
    EmployeeShiftSchedule,
    JobPosition,
    JobRole,
    RotatingShift,
    RotatingShiftAssign,
    RotatingWorkType,
    RotatingWorkTypeAssign,
    ShiftRequest,
    WorkType,
    WorkTypeRequest,
)
from horilla import horilla_middlewares


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = "__all__"


class JobPositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobPosition
        fields = "__all__"


class JobRoleSerializer(serializers.ModelSerializer):
    """Accept only `job_role` on POST and auto-assign a default JobPosition.

    POST body example accepted:
        { "job_role": "Junior Developer" }
    """

    class Meta:
        model = JobRole
        fields = ["id", "job_role"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        # Auto-assign first existing JobPosition as fallback
        job_position = JobPosition.objects.first()
        if job_position is None:
            raise serializers.ValidationError(
                "No JobPosition exists. Create a Job Position first."
            )
        obj = JobRole(job_position_id=job_position, **validated_data)
        try:
            obj.save()
        except IntegrityError:
            raise serializers.ValidationError(
                {
                    "job_role": [
                        "This job role already exists for the default job position."
                    ]
                }
            )
        except DjangoValidationError as e:
            raise serializers.ValidationError(e)

        return obj


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = "__all__"

    def create(self, validated_data):
        comapny_id = validated_data.pop("company_id", [])
        obj = Department(**validated_data)
        obj.save()
        obj.company_id.set(comapny_id)
        return obj


class WorkTypeSerializer(serializers.ModelSerializer):

    class Meta:
        model = WorkType
        fields = "__all__"

    def validate(self, attrs):
        # Create an instance of the model with the provided data
        instance = WorkType(**attrs)

        # Call the model's clean method for validation
        try:
            instance.clean()
        except DjangoValidationError as e:
            # Raise DRF's ValidationError with the same message
            raise serializers.ValidationError(e)

        return attrs

    def create(self, validated_data):
        return super().create(validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.clean()  # Call clean method before saving the instance
        instance.save()
        return instance


class RotatingWorkTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RotatingWorkType
        fields = "__all__"

    def validate(self, attrs):
        # Create an instance of the model with the provided data
        instance = RotatingWorkType(**attrs)

        # Call the model's clean method for validation
        try:
            instance.clean()
        except DjangoValidationError as e:
            # Raise DRF's ValidationError with the same message
            raise serializers.ValidationError(e)

        return attrs

    def create(self, validated_data):
        return super().create(validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.clean()  # Call clean method before saving the instance
        instance.save()
        return instance


class RotatingWorkTypeAssignSerializer(serializers.ModelSerializer):
    rotating_work_type_name = serializers.SerializerMethodField(read_only=True)
    current_work_type_name = serializers.SerializerMethodField(read_only=True)
    next_work_type_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = RotatingWorkTypeAssign
        fields = "__all__"

    def get_current_work_type_name(self, instance):
        current_work_type = instance.current_work_type
        if current_work_type:
            return current_work_type.work_type
        else:
            return None  # Return null if previous_work_type_id doesn't exist

    def get_next_work_type_name(self, instance):
        next_work_type = instance.next_work_type
        if next_work_type:
            return next_work_type.work_type
        else:
            return None  # Return null if previous_work_type_id doesn't exist

    def get_rotating_work_type_name(self, instance):
        rotating_work_type_id = instance.rotating_work_type_id
        if rotating_work_type_id:
            return rotating_work_type_id.name
        else:
            return None  # Return null if previous_work_type_id doesn't exist

    def validate(self, attrs):
        if self.instance:
            return attrs
        # Create an instance of the model with the provided data
        instance = RotatingWorkTypeAssign(**attrs)
        # Call the model's clean method for validation
        try:
            instance.clean()
        except DjangoValidationError as e:
            # Raise DRF's ValidationError with the same message
            raise serializers.ValidationError(e)
        return attrs

    def create(self, validated_data):
        return super().create(validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class EmployeeShiftDaySerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeShiftDay
        fields = "__all__"


class EmployeeShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeShift
        fields = "__all__"

    def validate(self, attrs):
        # Create an instance of the model with the provided data
        instance = EmployeeShift(**attrs)

        # Call the model's clean method for validation
        try:
            instance.clean()
        except DjangoValidationError as e:
            # Raise DRF's ValidationError with the same message
            raise serializers.ValidationError(e)

        return attrs

    def create(self, validated_data):
        return super().create(validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.clean()  # Call clean method before saving the instance
        instance.save()
        return instance


class EmployeeShiftScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeShiftSchedule
        fields = "__all__"


class RotatingShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = RotatingShift
        fields = "__all__"

    def validate(self, attrs):
        # Create an instance of the model with the provided data
        instance = RotatingShift(**attrs)

        # Call the model's clean method for validation
        try:
            instance.clean()
        except DjangoValidationError as e:
            # Raise DRF's ValidationError with the same message
            raise serializers.ValidationError(e)

        return attrs

    def create(self, validated_data):
        return super().create(validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.clean()  # Call clean method before saving the instance
        instance.save()
        return instance


class RotatingShiftAssignSerializer(serializers.ModelSerializer):
    def get_fields(self):
        fields = super().get_fields()
        # If rotating_shift is present in input, make rotating_shift_id not required
        request = self.context.get("request", None)
        data = getattr(request, "data", {}) if request else {}
        if data.get("rotating_shift"):
            fields["rotating_shift_id"].required = False
        return fields

    current_shift_name = serializers.SerializerMethodField(read_only=True)
    next_shift_name = serializers.SerializerMethodField(read_only=True)
    rotating_shift_name = serializers.SerializerMethodField(read_only=True)
    rotate = serializers.CharField(read_only=True)

    class Meta:
        model = RotatingShiftAssign
        fields = "__all__"
        extra_kwargs = {
            "rotating_shift_id": {"required": False, "allow_null": True},
        }

    # Accept rotating_shift as a name for dynamic assignment
    rotating_shift = serializers.CharField(write_only=True, required=False)

    def validate(self, attrs):
        # Remove rotating_shift if present to avoid TypeError
        attrs_for_instance = dict(attrs)
        attrs_for_instance.pop("rotating_shift", None)
        instance = (
            self.instance
            if self.instance
            else RotatingShiftAssign(**attrs_for_instance)
        )

        # Update instance attributes with validated data
        for attr, value in attrs_for_instance.items():
            setattr(instance, attr, value)

        # Call the model's clean method for validation
        try:
            instance.clean()
        except DjangoValidationError as e:
            # Raise DRF's ValidationError with the same message
            raise serializers.ValidationError(e)

        return attrs

    def create(self, validated_data):
        # Pop rotating_shift name if provided
        rotating_shift_name = validated_data.pop("rotating_shift", None)
        if rotating_shift_name:
            # Get or create RotatingShift by name
            rotating_shift_obj, _ = RotatingShift.objects.get_or_create(
                name=rotating_shift_name
            )
            validated_data["rotating_shift_id"] = rotating_shift_obj
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Support updating rotating_shift by name
        rotating_shift_name = validated_data.pop("rotating_shift", None)
        if rotating_shift_name:
            rotating_shift_obj, _ = RotatingShift.objects.get_or_create(
                name=rotating_shift_name
            )
            validated_data["rotating_shift_id"] = rotating_shift_obj
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.clean()  # Call clean method before saving the instance
        instance.save()
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        if instance.based_on == "after":
            representation["rotate"] = f"Rotate after {instance.rotate_after_day} days"
        elif instance.based_on == "weekly":
            representation["rotate"] = f"Weekly every {instance.rotate_every_weekend}"
        elif instance.based_on == "monthly":
            if instance.rotate_every == "1":
                representation["rotate"] = (
                    f"Rotate every {instance.rotate_every}st day of month"
                )
            elif instance.rotate_every == "2":
                representation["rotate"] = (
                    f"Rotate every {instance.rotate_every}nd day of month"
                )
            elif instance.rotate_every == "3":
                representation["rotate"] = (
                    f"Rotate every {instance.rotate_every}rd day of month"
                )
            elif instance.rotate_every == "last":
                representation["rotate"] = "Rotate every last day of month"
            else:
                representation["rotate"] = (
                    f"Rotate every {instance.rotate_every}th day of month"
                )

        return representation

    def get_rotating_shift_name(self, instance):
        rotating_shift_id = instance.rotating_shift_id
        if rotating_shift_id:
            return rotating_shift_id.name
        else:
            return None  # Return null if previous_work_type_id doesn't exist

    def get_next_shift_name(self, instance):
        next_shift = instance.next_shift
        if next_shift:
            return next_shift.employee_shift
        else:
            return None  # Return null if previous_work_type_id doesn't exist

    def get_current_shift_name(self, instance):
        current_shift = instance.current_shift
        if current_shift:
            return current_shift.employee_shift
        else:
            return None  # Return null if previous_work_type_id doesn't exist

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.clean()  # Call clean method before saving the instance
        instance.save()
        return instance


class WorkTypeRequestSerializer(serializers.ModelSerializer):
    employee_first_name = serializers.CharField(
        source="employee_id.employee_first_name", read_only=True
    )
    employee_last_name = serializers.CharField(
        source="employee_id.employee_last_name", read_only=True
    )
    work_type_name = serializers.CharField(
        source="work_type_id.work_type", read_only=True
    )
    previous_work_type_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = WorkTypeRequest
        fields = "__all__"

    def validate(self, attrs):
        request = getattr(horilla_middlewares._thread_locals, "request", None)
        # Check if the user is not a superuser
        requested_date = attrs.get("requested_date", None)

        if request and not request.user.is_superuser:

            if requested_date and requested_date < datetime.datetime.today().date():
                raise serializers.ValidationError(
                    {"requested_date": "Date must be greater than or equal to today."}
                )

        # Validate requested_till is not earlier than requested_date
        requested_till = attrs.get("requested_till", None)
        if requested_till and requested_till < requested_date:
            raise serializers.ValidationError(
                {
                    "requested_till": (
                        "End date must be greater than or equal to start date."
                    )
                }
            )

        # Check if any work type request already exists
        if self.instance and self.instance.is_any_work_type_request_exists():
            raise serializers.ValidationError(
                {"error": "A work type request already exists during this time period."}
            )

        # Validate if `is_permanent_work_type` is False, `requested_till` must be provided
        if not attrs.get("is_permanent_work_type", False):
            if not requested_till:
                raise serializers.ValidationError(
                    {"requested_till": ("Requested till field is required.")}
                )

        return attrs

    def create(self, validated_data):
        return super().create(validated_data)

    def get_previous_work_type_name(self, instance):
        previous_work_type = instance.previous_work_type_id
        if previous_work_type:
            return previous_work_type.work_type
        else:
            return None  # Return null if previous_work_type_id doesn't exist

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.clean()  # Call clean method before saving the instance
        instance.save()
        return instance


class ShiftRequestSerializer(serializers.ModelSerializer):
    employee_first_name = serializers.CharField(
        source="employee_id.employee_first_name", read_only=True
    )
    employee_last_name = serializers.CharField(
        source="employee_id.employee_last_name", read_only=True
    )
    shift_name = serializers.SerializerMethodField(read_only=True)
    previous_shift_name = serializers.SerializerMethodField(read_only=True)

    def get_previous_shift_name(self, instance):
        previous_shift_id = instance.previous_shift_id
        if previous_shift_id:
            return previous_shift_id.employee_shift
        else:
            return None  # Re

    def get_shift_name(self, instance):
        shift_id = instance.shift_id
        if shift_id:
            return shift_id.employee_shift
        else:
            return None  # Re

    def validate(self, attrs):
        # Create an instance of the model with the provided data
        instance = ShiftRequest(**attrs)

        # Call the model's clean method for validation
        try:
            instance.clean()
        except DjangoValidationError as e:
            # Raise DRF's ValidationError with the same message
            raise serializers.ValidationError(e)

        return attrs

    def create(self, validated_data):
        return super().create(validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.clean()  # Call clean method before saving the instance
        instance.save()
        return instance

    class Meta:
        model = ShiftRequest
        fields = "__all__"

