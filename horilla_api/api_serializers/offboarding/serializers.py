from datetime import date

from django.contrib.auth.models import User
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
from offboarding.models import (
    Offboarding,
    OffboardingEmployee,
    OffboardingStage,
    ResignationLetter,
)


class AdminManagerRelatedField(serializers.PrimaryKeyRelatedField):
    default_error_messages = {
        "does_not_exist": 'Invalid pk "{pk_value}" - object does not exist.',
        "not_admin": "Managers must reference admin users only.",
        "incorrect_type": "Incorrect type. Expected pk value, received {data_type}.",
    }

    def _ensure_admin_employee_for_user(self, user):
        if not (user.is_superuser or user.is_staff):
            self.fail("not_admin")
        employee, _created = Employee.objects.get_or_create(
            employee_user_id=user,
            defaults={
                "employee_first_name": user.first_name or user.username,
                "employee_last_name": user.last_name or "",
                "email": user.email or f"{user.username}-{user.id}@example.com",
                "phone": "0000000000",
                "role": "admin",
            },
        )
        updates = {}
        if employee.role != "admin":
            updates["role"] = "admin"
        if not employee.email:
            updates["email"] = user.email or f"{user.username}-{user.id}@example.com"
        if not employee.phone:
            updates["phone"] = "0000000000"
        if updates:
            Employee.objects.filter(pk=employee.pk).update(**updates)
            for field, value in updates.items():
                setattr(employee, field, value)
        return employee

    def to_internal_value(self, data):
        if isinstance(data, dict):
            data = data.get("user_id") or data.get("employee_id") or data.get("id")
        if isinstance(data, str):
            data = data.strip()
        if isinstance(data, bool) or not isinstance(data, (str, int)):
            self.fail("incorrect_type", data_type=type(data).__name__)
        if isinstance(data, str):
            if not data.isdigit():
                self.fail("does_not_exist", pk_value=data)
            data = int(data)

        user = User.objects.filter(pk=data).first()
        if user:
            employee = Employee.objects.filter(employee_user_id=user).first()
            if employee:
                user = getattr(employee, "employee_user_id", None)
                if user and (user.is_superuser or user.is_staff):
                    return employee
                if user and user.groups.filter(name="Admin User").exists():
                    return employee
                if employee.role == "admin":
                    return employee
                self.fail("not_admin")
            if user.groups.filter(name="Admin User").exists():
                employee = Employee.objects.filter(employee_user_id=user).first()
                if employee:
                    return employee
            return self._ensure_admin_employee_for_user(user)

        employee = Employee.objects.filter(pk=data).first()
        if employee:
            user = getattr(employee, "employee_user_id", None)
            if user and (user.is_superuser or user.is_staff):
                return employee
            if user and user.groups.filter(name="Admin User").exists():
                return employee
            if employee.role == "admin":
                return employee
            self.fail("not_admin")

        self.fail("does_not_exist", pk_value=data)


class UserOrEmployeeRelatedField(serializers.PrimaryKeyRelatedField):
    default_error_messages = {
        "does_not_exist": 'Invalid pk "{pk_value}" - object does not exist.',
        "incorrect_type": "Incorrect type. Expected pk value, received {data_type}.",
    }

    def _ensure_employee_for_admin_user(self, user):
        if not (user.is_superuser or user.is_staff):
            self.fail("does_not_exist", pk_value=user.pk)
        employee, _created = Employee.objects.get_or_create(
            employee_user_id=user,
            defaults={
                "employee_first_name": user.first_name or user.username,
                "employee_last_name": user.last_name or "",
                "email": user.email or f"{user.username}-{user.id}@example.com",
                "phone": "0000000000",
                "role": "admin",
            },
        )
        updates = {}
        if not employee.email:
            updates["email"] = user.email or f"{user.username}-{user.id}@example.com"
        if not employee.phone:
            updates["phone"] = "0000000000"
        if (user.is_superuser or user.is_staff) and employee.role != "admin":
            updates["role"] = "admin"
        if updates:
            Employee.objects.filter(pk=employee.pk).update(**updates)
            for field, value in updates.items():
                setattr(employee, field, value)
        return employee

    def to_internal_value(self, data):
        if isinstance(data, dict):
            data = data.get("user_id") or data.get("employee_id") or data.get("id")
        if isinstance(data, str):
            data = data.strip()
        if isinstance(data, bool) or not isinstance(data, (str, int)):
            self.fail("incorrect_type", data_type=type(data).__name__)
        if isinstance(data, str):
            if not data.isdigit():
                self.fail("does_not_exist", pk_value=data)
            data = int(data)

        user = User.objects.filter(pk=data).first()
        if user:
            linked_employee = Employee.objects.filter(employee_user_id=user).first()
            if linked_employee:
                return linked_employee
            return self._ensure_employee_for_admin_user(user)

        employee = Employee.objects.filter(pk=data).first()
        if employee:
            return employee

        self.fail("does_not_exist", pk_value=data)


class OffboardingSerializer(serializers.ModelSerializer):
    company = serializers.PrimaryKeyRelatedField(
        source="company_id", queryset=Company.objects.all(), required=False
    )
    managers = AdminManagerRelatedField(
        queryset=Employee.objects.all(), many=True, required=False
    )
    status = serializers.CharField(required=False)

    class Meta:
        model = Offboarding
        fields = [
            "id",
            "title",
            "description",
            "managers",
            "status",
            "company",
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
            "Status": "status",
            "Company": "company",
        }
        for incoming, target in aliases.items():
            if incoming in mutable and target not in mutable:
                mutable[target] = mutable[incoming]
        mutable.pop("manager_users", None)
        mutable.pop("Manager Users", None)
        if "managers" in mutable:
            manager_values = (
                mutable.getlist("managers")
                if hasattr(mutable, "getlist")
                else mutable.get("managers")
            )
            if not isinstance(manager_values, list):
                manager_values = [manager_values]
            normalized_managers = self._normalize_manager_values(manager_values)
            if hasattr(mutable, "setlist"):
                mutable.setlist("managers", [str(value) for value in normalized_managers])
            else:
                mutable["managers"] = normalized_managers
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

    def _is_admin_employee(self, employee):
        user = getattr(employee, "employee_user_id", None)
        if user and (user.is_superuser or user.is_staff):
            return True
        if user and user.groups.filter(name="Admin User").exists():
            return True
        return employee.role == "admin"

    def _normalize_manager_values(self, manager_values):
        normalized = []
        for value in manager_values:
            if value in (None, ""):
                continue
            if isinstance(value, dict):
                value = (
                    value.get("user_id")
                    or value.get("employee_id")
                    or value.get("id")
                )
            if isinstance(value, str):
                value = value.strip()
            if isinstance(value, int) or (
                isinstance(value, str) and value.isdigit()
            ):
                lookup_value = int(value)
                employee = Employee.objects.filter(
                    employee_user_id__id=lookup_value
                ).first()
                if employee and self._is_admin_employee(employee):
                    normalized.append(employee.pk)
                    continue
                employee = Employee.objects.filter(pk=lookup_value).first()
                if employee and self._is_admin_employee(employee):
                    normalized.append(employee.pk)
                    continue
            normalized.append(value)
        return normalized

    def validate_managers(self, value):
        invalid_managers = [
            manager.id for manager in value if not self._is_admin_employee(manager)
        ]
        if invalid_managers:
            raise serializers.ValidationError(
                f"Managers must reference admin users only. Invalid employee ids: {invalid_managers}"
            )
        return list({manager.id: manager for manager in value}.values())

    def _collect_managers(self, validated_data):
        managers = list(validated_data.pop("managers", []))
        return list({manager.id: manager for manager in managers}.values())

    def _get_fallback_managers(self, instance):
        managers = list(instance.managers.all())
        if managers:
            return managers

        created_by = getattr(instance, "created_by", None)
        created_by_employee = getattr(created_by, "employee_get", None)
        if created_by_employee and self._is_admin_employee(created_by_employee):
            return [created_by_employee]

        request = self.context.get("request")
        request_employee = getattr(
            getattr(request, "user", None), "employee_get", None
        )
        if request_employee and self._is_admin_employee(request_employee):
            return [request_employee]
        return []

    def _get_offboarding_employees(self, instance):
        return OffboardingEmployee.objects.filter(stage_id__offboarding_id=instance).select_related(
            "employee_id", "stage_id"
        ).order_by("-id")

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
        if not managers:
            request = self.context.get("request")
            request_employee = getattr(
                getattr(request, "user", None), "employee_get", None
            )
            if request_employee and self._is_admin_employee(request_employee):
                managers = [request_employee]
        offboarding = Offboarding.objects.create(**validated_data)
        if managers:
            offboarding.managers.set(managers)
        return offboarding

    def update(self, instance, validated_data):
        managers_provided = "managers" in validated_data
        managers = self._collect_managers(validated_data) if managers_provided else None
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if managers_provided:
            instance.managers.set(managers)
        return instance

    def to_representation(self, instance):
        managers = self._get_fallback_managers(instance)
        employees = self._get_offboarding_employees(instance)
        return {
            "id": instance.id,
            "title": instance.title,
            "description": instance.description,
            "managers": [
                {"id": manager.id, "name": manager.get_full_name()}
                for manager in managers
            ],
            "status": instance.status,
            "company": (
                {
                    "id": instance.company_id.id,
                    "company": instance.company_id.company,
                }
                if instance.company_id
                else None
            ),
            "employees": OffboardingEmployeeSerializer(employees, many=True).data,
        }


class OffboardingEmployeeSerializer(serializers.ModelSerializer):
    employee = UserOrEmployeeRelatedField(
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
            "stage",
            "notice_period_starts",
            "notice_period_ends",
            "offboarding",
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
        return {
            "id": instance.id,
            "employee": {
                "id": instance.employee_id.id,
                "name": instance.employee_id.get_full_name(),
            }
            if instance.employee_id
            else None,
            "stage": {
                "id": instance.stage_id.id,
                "title": instance.stage_id.title,
            }
            if instance.stage_id
            else None,
            "notice_period_starts": instance.notice_period_starts,
            "notice_period_ends": instance.notice_period_ends,
        }


class OffboardingStageSerializer(serializers.ModelSerializer):
    offboarding = serializers.PrimaryKeyRelatedField(
        source="offboarding_id", queryset=Offboarding.objects.all()
    )
    type = serializers.CharField()
    managers = AdminManagerRelatedField(
        queryset=Employee.objects.all(), many=True, required=False
    )

    class Meta:
        model = OffboardingStage
        fields = ["id", "offboarding", "type", "title", "managers", "sequence"]
        read_only_fields = ["sequence"]

    def to_internal_value(self, data):
        if hasattr(data, "copy"):
            mutable = data.copy()
        else:
            mutable = dict(data)
        aliases = {
            "Offboarding": "offboarding",
            "Status": "type",
            "Type": "type",
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

    def to_representation(self, instance):
        return {
            "id": instance.id,
            "offboarding": {
                "id": instance.offboarding_id.id,
                "title": instance.offboarding_id.title,
            }
            if instance.offboarding_id
            else None,
            "title": instance.title,
            "type": instance.get_type_display(),
            "managers": [
                {"id": manager.id, "name": manager.get_full_name()}
                for manager in instance.managers.all()
            ],
        }


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


class ResignationRequestSerializer(serializers.ModelSerializer):
    employee = UserOrEmployeeRelatedField(
        source="employee_id", queryset=Employee.objects.all()
    )
    status = serializers.CharField(required=False)

    class Meta:
        model = ResignationLetter
        fields = [
            "id",
            "employee",
            "title",
            "description",
            "planned_to_leave_on",
            "status",
        ]

    def to_internal_value(self, data):
        if hasattr(data, "copy"):
            mutable = data.copy()
        else:
            mutable = dict(data)
        aliases = {
            "Employee": "employee",
            "Title": "title",
            "Description": "description",
            "Planned To Leave On": "planned_to_leave_on",
            "Status": "status",
        }
        for incoming, target in aliases.items():
            if incoming in mutable and target not in mutable:
                mutable[target] = mutable[incoming]
        return super().to_internal_value(mutable)

    def validate_status(self, value):
        value = str(value).strip().lower()
        if value not in {"requested", "approved", "rejected"}:
            raise serializers.ValidationError(
                "Status must be Requested, Approved, or Rejected."
            )
        return value

    def to_representation(self, instance):
        return {
            "id": instance.id,
            "employee": {
                "id": instance.employee_id.id,
                "name": instance.employee_id.get_full_name(),
            }
            if instance.employee_id
            else None,
            "title": instance.title,
            "description": instance.description,
            "planned_to_leave_on": instance.planned_to_leave_on,
            "status": instance.status.capitalize() if instance.status else None,
        }
