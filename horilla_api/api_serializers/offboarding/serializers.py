from datetime import date

from django.db import IntegrityError
from rest_framework import serializers

from base.models import (
    Company,
    Department,
    EmployeeShift,
    EmployeeType,
    JobPosition,
    JobRole,
    WorkType,
)
from employee.models import Employee, EmployeeWorkInformation
from offboarding.models import Offboarding, OffboardingEmployee, OffboardingStage


class OffboardingSerializer(serializers.ModelSerializer):
    company = serializers.PrimaryKeyRelatedField(
        source="company_id", queryset=Company.objects.all(), required=False
    )
    company_name = serializers.CharField(source="company_id.company", read_only=True)
    managers = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), many=True, required=False
    )
    manager_users = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    status = serializers.CharField(required=False)

    class Meta:
        model = Offboarding
        fields = [
            "id",
            "title",
            "description",
            "managers",
            "manager_users",
            "status",
            "company",
            "company_name",
        ]
        extra_kwargs = {
            "title": {"required": False, "allow_blank": True},
            "description": {"required": False, "allow_blank": True},
        }

    def to_internal_value(self, data):
        if hasattr(data, "copy"):
            mutable = data.copy()
        else:
            mutable = dict(data)
        aliases = {
            "Title": "title",
            "Description": "description",
            "Managers": "managers",
            "Manager Users": "manager_users",
            "Status": "status",
            "Company": "company",
        }
        for incoming, target in aliases.items():
            if incoming in mutable and target not in mutable:
                mutable[target] = mutable[incoming]
        company_value = mutable.get("company")
        if company_value not in (None, ""):
            try:
                company_pk = int(company_value)
            except (TypeError, ValueError):
                mutable.pop("company", None)
            else:
                if not Company.objects.filter(pk=company_pk).exists():
                    mutable.pop("company", None)
        return super().to_internal_value(mutable)

    def validate_status(self, value):
        value = str(value).strip().lower()
        status_map = {"ongoing": "ongoing", "completed": "completed"}
        if value not in status_map:
            raise serializers.ValidationError("Status must be Ongoing or Completed.")
        return status_map[value]

    def _collect_managers(self, validated_data):
        managers = list(validated_data.pop("managers", []))
        manager_users = validated_data.pop("manager_users", [])
        if manager_users:
            user_managers = Employee.objects.filter(
                employee_user_id__id__in=manager_users
            )
            managers.extend(list(user_managers))
        unique_managers = list({manager.id: manager for manager in managers}.values())
        return unique_managers

    def create(self, validated_data):
        if not validated_data.get("title"):
            validated_data["title"] = "Offboarding"
        if not validated_data.get("description"):
            validated_data["description"] = ""
        if not validated_data.get("company_id"):
            validated_data["company_id"] = (
                Company.objects.filter(pk=1).first() or Company.objects.first()
            )
        managers = self._collect_managers(validated_data)
        offboarding = Offboarding.objects.create(**validated_data)
        if managers:
            offboarding.managers.set(managers)
        return offboarding

    def update(self, instance, validated_data):
        managers_provided = (
            "managers" in validated_data or "manager_users" in validated_data
        )
        managers = self._collect_managers(validated_data) if managers_provided else None
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if managers_provided:
            instance.managers.set(managers)
        return instance


class OffboardingEmployeeSerializer(serializers.ModelSerializer):
    employee = serializers.PrimaryKeyRelatedField(
        source="employee_id", queryset=Employee.objects.all(), required=False
    )
    offboarding = serializers.PrimaryKeyRelatedField(
        queryset=Offboarding.objects.all(), write_only=True, required=False
    )
    stage = serializers.PrimaryKeyRelatedField(
        source="stage_id",
        queryset=OffboardingStage.objects.all(),
        required=False,
        allow_null=True,
    )
    department = serializers.IntegerField(required=False, allow_null=True)
    job_position = serializers.IntegerField(required=False, allow_null=True)
    job_role = serializers.IntegerField(required=False, allow_null=True)
    employee_type = serializers.IntegerField(required=False, allow_null=True)
    shift = serializers.IntegerField(required=False, allow_null=True)
    work_type = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = OffboardingEmployee
        fields = [
            "id",
            "employee",
            "offboarding",
            "stage",
            "notice_period_starts",
            "notice_period_ends",
            "department",
            "job_position",
            "job_role",
            "employee_type",
            "shift",
            "work_type",
        ]

    def to_internal_value(self, data):
        if hasattr(data, "copy"):
            mutable = data.copy()
        else:
            mutable = dict(data)
        aliases = {
            "Employee": "employee",
            "Offboarding": "offboarding",
            "Stage": "stage",
            "Notice Period Starts": "notice_period_starts",
            "Notice Period Ends": "notice_period_ends",
            "Department": "department",
            "Job Position": "job_position",
            "Job Role": "job_role",
            "Employee Type": "employee_type",
            "Shift": "shift",
            "Work Type": "work_type",
        }
        for incoming, target in aliases.items():
            if incoming in mutable and target not in mutable:
                mutable[target] = mutable[incoming]
        stage_value = mutable.get("stage")
        if stage_value not in (None, ""):
            try:
                stage_pk = int(stage_value)
            except (TypeError, ValueError):
                mutable.pop("stage", None)
            else:
                if not OffboardingStage.objects.filter(pk=stage_pk).exists():
                    mutable.pop("stage", None)
        return super().to_internal_value(mutable)

    def _get_stage_from_offboarding(self, offboarding):
        return (
            OffboardingStage.objects.filter(offboarding_id=offboarding)
            .order_by("sequence", "id")
            .first()
        )

    def _get_related_work_info(self, employee):
        work_info, _ = EmployeeWorkInformation.objects.get_or_create(
            employee_id=employee
        )
        return work_info

    def _set_work_info_field(self, work_info, field_name, model_class, pk):
        if pk is None:
            setattr(work_info, field_name, None)
            return
        obj = model_class.objects.filter(pk=pk).first()
        if not obj:
            raise serializers.ValidationError({field_name: f"Invalid id: {pk}"})
        setattr(work_info, field_name, obj)

    def _sync_notice_period_days(self, instance):
        if instance.notice_period_starts and instance.notice_period_ends:
            start = instance.notice_period_starts
            end = instance.notice_period_ends
            if isinstance(start, date) and isinstance(end, date):
                diff_days = (end - start).days
                instance.notice_period = diff_days if diff_days > 0 else None
                instance.unit = "day" if diff_days > 0 else instance.unit

    def create(self, validated_data):
        offboarding = validated_data.pop("offboarding", None)
        department = validated_data.pop("department", None)
        job_position = validated_data.pop("job_position", None)
        job_role = validated_data.pop("job_role", None)
        employee_type = validated_data.pop("employee_type", None)
        shift = validated_data.pop("shift", None)
        work_type = validated_data.pop("work_type", None)

        employee = validated_data.get("employee_id")
        if not employee:
            request = self.context.get("request")
            request_employee = getattr(
                getattr(request, "user", None), "employee_get", None
            )
            if request_employee:
                validated_data["employee_id"] = request_employee
            else:
                raise serializers.ValidationError({"employee": "Employee is required."})

        stage = validated_data.get("stage_id")
        if offboarding and not stage:
            stage = self._get_stage_from_offboarding(offboarding)
            validated_data["stage_id"] = stage
        if offboarding and stage and stage.offboarding_id_id != offboarding.id:
            raise serializers.ValidationError(
                {"stage": "Provided stage does not belong to selected offboarding."}
            )
        if not stage:
            raise serializers.ValidationError(
                {"stage": "A valid stage or offboarding is required."}
            )

        if OffboardingEmployee.objects.filter(
            employee_id=validated_data["employee_id"]
        ).exists():
            raise serializers.ValidationError(
                {
                    "employee": "This employee is already in offboarding. Use PUT /api/offboarding/employees/{id}/ to update."
                }
            )

        try:
            instance = OffboardingEmployee.objects.create(**validated_data)
        except IntegrityError:
            raise serializers.ValidationError(
                {
                    "employee": "This employee is already in offboarding. Use PUT /api/offboarding/employees/{id}/ to update."
                }
            )
        self._sync_notice_period_days(instance)
        instance.save()

        work_info = self._get_related_work_info(instance.employee_id)
        self._set_work_info_field(work_info, "department_id", Department, department)
        self._set_work_info_field(
            work_info, "job_position_id", JobPosition, job_position
        )
        self._set_work_info_field(work_info, "job_role_id", JobRole, job_role)
        self._set_work_info_field(
            work_info, "employee_type_id", EmployeeType, employee_type
        )
        self._set_work_info_field(work_info, "shift_id", EmployeeShift, shift)
        self._set_work_info_field(work_info, "work_type_id", WorkType, work_type)
        work_info.save()
        return instance

    def update(self, instance, validated_data):
        offboarding = validated_data.pop("offboarding", None)
        department = (
            validated_data.pop("department", None)
            if "department" in validated_data
            else ...
        )
        job_position = (
            validated_data.pop("job_position", None)
            if "job_position" in validated_data
            else ...
        )
        job_role = (
            validated_data.pop("job_role", None)
            if "job_role" in validated_data
            else ...
        )
        employee_type = (
            validated_data.pop("employee_type", None)
            if "employee_type" in validated_data
            else ...
        )
        shift = validated_data.pop("shift", None) if "shift" in validated_data else ...
        work_type = (
            validated_data.pop("work_type", None)
            if "work_type" in validated_data
            else ...
        )

        stage = validated_data.get("stage_id")
        if offboarding and not stage:
            validated_data["stage_id"] = self._get_stage_from_offboarding(offboarding)
            stage = validated_data["stage_id"]
        if offboarding and stage and stage.offboarding_id_id != offboarding.id:
            raise serializers.ValidationError(
                {"stage": "Provided stage does not belong to selected offboarding."}
            )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        self._sync_notice_period_days(instance)
        instance.save()

        work_info = self._get_related_work_info(instance.employee_id)
        if department is not ...:
            self._set_work_info_field(
                work_info, "department_id", Department, department
            )
        if job_position is not ...:
            self._set_work_info_field(
                work_info, "job_position_id", JobPosition, job_position
            )
        if job_role is not ...:
            self._set_work_info_field(work_info, "job_role_id", JobRole, job_role)
        if employee_type is not ...:
            self._set_work_info_field(
                work_info, "employee_type_id", EmployeeType, employee_type
            )
        if shift is not ...:
            self._set_work_info_field(work_info, "shift_id", EmployeeShift, shift)
        if work_type is not ...:
            self._set_work_info_field(work_info, "work_type_id", WorkType, work_type)
        work_info.save()
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        work_info = getattr(instance.employee_id, "employee_work_info", None)
        data["department"] = getattr(
            getattr(work_info, "department_id", None), "id", None
        )
        data["job_position"] = getattr(
            getattr(work_info, "job_position_id", None), "id", None
        )
        data["job_role"] = getattr(getattr(work_info, "job_role_id", None), "id", None)
        data["employee_type"] = getattr(
            getattr(work_info, "employee_type_id", None), "id", None
        )
        data["shift"] = getattr(getattr(work_info, "shift_id", None), "id", None)
        data["work_type"] = getattr(
            getattr(work_info, "work_type_id", None), "id", None
        )
        data["offboarding"] = (
            instance.stage_id.offboarding_id_id if instance.stage_id else None
        )
        return data


class OffboardingStageSerializer(serializers.ModelSerializer):
    offboarding = serializers.PrimaryKeyRelatedField(
        source="offboarding_id", queryset=Offboarding.objects.all()
    )
    status = serializers.CharField(source="type")

    class Meta:
        model = OffboardingStage
        fields = ["id", "offboarding", "status", "title", "managers", "sequence"]
        read_only_fields = ["sequence"]

    def to_internal_value(self, data):
        if hasattr(data, "copy"):
            mutable = data.copy()
        else:
            mutable = dict(data)
        aliases = {
            "Offboarding": "offboarding",
            "Status": "status",
            "Title": "title",
            "Managers": "managers",
        }
        for incoming, target in aliases.items():
            if incoming in mutable and target not in mutable:
                mutable[target] = mutable[incoming]
        return super().to_internal_value(mutable)

    def validate_type(self, value):
        normalized = str(value).strip().lower().replace("-", " ").replace("_", " ")
        status_map = {
            "notice period": "notice_period",
            "fnf settlement": "fnf",
            "fnf": "fnf",
            "other": "other",
            "interview": "interview",
            "work handover": "handover",
            "handover": "handover",
            "archived": "archived",
        }
        mapped = status_map.get(normalized)
        if not mapped:
            raise serializers.ValidationError(
                "Status must be one of: Notice Period, Fnf Settlement, Other, Interview, Work Handover, Archived."
            )
        return mapped

    def _default_title(self, stage_type):
        title_map = {
            "notice_period": "Notice Period",
            "fnf": "Fnf Settlement",
            "other": "Other",
            "interview": "Interview",
            "handover": "Work handover",
            "archived": "Archived",
        }
        return title_map.get(stage_type, "Stage")

    def create(self, validated_data):
        if not validated_data.get("title"):
            validated_data["title"] = self._default_title(validated_data["type"])
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "type" in validated_data and "title" not in validated_data:
            validated_data["title"] = self._default_title(validated_data["type"])
        return super().update(instance, validated_data)


class OffboardingManagerStatusSerializer(serializers.ModelSerializer):
    managers = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), many=True, required=False
    )
    manager_users = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    status = serializers.CharField(required=False)

    class Meta:
        model = Offboarding
        fields = ["id", "managers", "manager_users", "status"]

    def to_internal_value(self, data):
        if hasattr(data, "copy"):
            mutable = data.copy()
        else:
            mutable = dict(data)
        aliases = {
            "Managers": "managers",
            "Manager Users": "manager_users",
            "Status": "status",
        }
        for incoming, target in aliases.items():
            if incoming in mutable and target not in mutable:
                mutable[target] = mutable[incoming]
        return super().to_internal_value(mutable)

    def validate_status(self, value):
        value = str(value).strip().lower()
        if value not in {"ongoing", "completed"}:
            raise serializers.ValidationError("Status must be Ongoing or Completed.")
        return value

    def _collect_managers(self, validated_data):
        managers = list(validated_data.pop("managers", []))
        manager_users = validated_data.pop("manager_users", [])
        if manager_users:
            user_managers = Employee.objects.filter(
                employee_user_id__id__in=manager_users
            )
            managers.extend(list(user_managers))
        return list({manager.id: manager for manager in managers}.values())

    def create(self, validated_data):
        managers = self._collect_managers(validated_data)
        company = Company.objects.first()
        offboarding = Offboarding.objects.create(
            title="Offboarding",
            description="",
            status=validated_data.get("status", "ongoing"),
            company_id=company,
        )
        if managers:
            offboarding.managers.set(managers)
        return offboarding

    def update(self, instance, validated_data):
        managers_provided = (
            "managers" in validated_data or "manager_users" in validated_data
        )
        managers = self._collect_managers(validated_data) if managers_provided else None
        if "status" in validated_data:
            instance.status = validated_data["status"]
        instance.save()
        if managers_provided:
            instance.managers.set(managers)
        return instance
