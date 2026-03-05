from rest_framework import serializers

from employee.models import Employee

from .models import ProjectNew


class ProjectNewCreateSerializer(serializers.ModelSerializer):

    managers = serializers.ListField(child=serializers.IntegerField(), write_only=True)
    members = serializers.ListField(child=serializers.IntegerField(), write_only=True)

    class Meta:
        model = ProjectNew
        fields = [
            "id",
            "project_name",
            "managers",
            "members",
            "status",
            "start_date",
            "end_date",
            "description",
        ]

    def validate_managers(self, value):
        qs = Employee.objects.filter(employee_user_id_id__in=value)
        if qs.count() != len(set(value)):
            raise serializers.ValidationError(
                "One or more project manager user IDs do not exist."
            )
        return value

    def validate_members(self, value):
        qs = Employee.objects.filter(employee_user_id_id__in=value)
        if qs.count() != len(set(value)):
            raise serializers.ValidationError(
                "One or more project member user IDs do not exist."
            )
        return value

    def validate(self, data):
        valid_status = dict(ProjectNew.PROJECT_STATUS).keys()
        if data["status"] not in valid_status:
            raise serializers.ValidationError({"status": "Invalid project status."})

        if data.get("end_date") and data["end_date"] < data["start_date"]:
            raise serializers.ValidationError(
                {"end_date": "End date cannot be before start date."}
            )

        return data


class ProjectNewReadSerializer(serializers.ModelSerializer):
    managers = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()
    project_file = serializers.SerializerMethodField()

    class Meta:
        model = ProjectNew
        fields = [
            "id",
            "project_name",
            "managers",
            "members",
            "status",
            "start_date",
            "end_date",
            "project_file",
            "description",
        ]

    def get_managers(self, obj):
        return [
            f"{emp.employee_first_name} {emp.employee_last_name}"
            for emp in Employee._base_manager.filter(
                managed_projects_new=obj  # ✅ CORRECT
            )
        ]

    def get_members(self, obj):
        return [
            f"{emp.employee_first_name} {emp.employee_last_name}"
            for emp in Employee._base_manager.filter(
                member_projects_new=obj  # ✅ CORRECT
            )
        ]

    def get_project_file(self, obj):
        request = self.context.get("request")
        project_file = getattr(obj, "project_file", None)
        if project_file and request:
            return request.build_absolute_uri(project_file.url)
        return None


### task serlializer here

from rest_framework import serializers

from employee.models import Employee

from .models import ProjectNew, TaskNew, TimeSheetNew


class TaskNewCreateSerializer(serializers.ModelSerializer):
    task_managers = serializers.ListField(
        child=serializers.IntegerField(), write_only=True
    )
    task_members = serializers.ListField(
        child=serializers.IntegerField(), write_only=True
    )
    stage_id = serializers.IntegerField(
        write_only=True, required=False, allow_null=True
    )
    project_stage = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )

    class Meta:
        model = TaskNew
        fields = [
            "id",
            "title",
            "project",
            "stage_id",
            "project_stage",
            "task_managers",
            "task_members",
            "status",
            "start_date",
            "end_date",
            "description",
        ]

    def validate_project(self, value):
        if not ProjectNew.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("Project does not exist.")
        return value

    def validate_stage_id(self, value):
        # Backward compatibility input. Database stores project_stage as text.
        return value

    def validate_task_managers(self, value):
        qs = Employee.objects.filter(employee_user_id_id__in=value)
        if qs.count() != len(set(value)):
            raise serializers.ValidationError(
                "One or more task manager user IDs do not exist."
            )
        return value

    def validate_task_members(self, value):
        qs = Employee.objects.filter(employee_user_id_id__in=value)
        if qs.count() != len(set(value)):
            raise serializers.ValidationError(
                "One or more task member user IDs do not exist."
            )
        return value

    def validate(self, data):
        # 🔹 Date validation
        if data.get("end_date") and data["end_date"] < data["start_date"]:
            raise serializers.ValidationError(
                {"end_date": "End date cannot be before start date."}
            )

        return data

    def create(self, validated_data):
        # Backward compatibility: map stage_id input into project_stage text field.
        stage_id = validated_data.pop("stage_id", None)
        if stage_id is not None and not validated_data.get("project_stage"):
            validated_data["project_stage"] = str(stage_id)
        return TaskNew.objects.create(**validated_data)


class TaskNewReadSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.project_name", read_only=True)
    task_managers = serializers.SerializerMethodField()
    task_members = serializers.SerializerMethodField()
    stage = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = TaskNew
        fields = [
            "id",
            "title",
            "project",
            "project_name",
            "stage",
            "task_managers",
            "task_members",
            "status",
            "start_date",
            "end_date",
            "description",
        ]

    def get_task_managers(self, obj):
        return [
            f"{emp.employee_first_name} {emp.employee_last_name}"
            for emp in Employee._base_manager.filter(managed_tasks_new=obj)
        ]

    def get_task_members(self, obj):
        return [
            f"{emp.employee_first_name} {emp.employee_last_name}"
            for emp in Employee._base_manager.filter(member_tasks_new=obj)
        ]

    def get_stage(self, obj):
        # Database stores stage as text in project_stage.
        stage_value = getattr(obj, "project_stage", None)
        if stage_value:
            return {"id": None, "title": stage_value}
        return None


### time sheet serializer start here
from rest_framework import serializers

from employee.models import Employee

from .models import TaskNew, TimeSheetNew


class TimeSheetNewCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = TimeSheetNew
        fields = [
            "id",
            "task",
            "date",
            "hours_spent",
            "status",
            "description",
        ]

    def validate_hours_spent(self, value):
        if value <= 0 or value > 24:
            raise serializers.ValidationError("Hours spent must be between 0 and 24.")
        return value

    def validate(self, data):
        if data.get("end_date"):
            pass
        return data


class TimeSheetNewReadSerializer(serializers.ModelSerializer):
    timesheet_id = serializers.IntegerField(source="id", read_only=True)
    employee_name = serializers.SerializerMethodField()
    project_name = serializers.CharField(
        source="task.project.project_name", read_only=True
    )
    task_name = serializers.CharField(source="task.title", read_only=True)

    class Meta:
        model = TimeSheetNew
        fields = [
            "timesheet_id",
            "employee_name",
            "project_name",
            "task_name",
            "date",
            "hours_spent",
            "status",
            "description",
        ]

    def get_employee_name(self, obj):
        # ✅ Comes from TimeSheet.employee (creator)
        emp = obj.employee
        return f"{emp.employee_first_name} {emp.employee_last_name}"


### ProjectNewStage serializers

from rest_framework import serializers

from .models import ProjectNewStage


class ProjectNewStageCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating ProjectNewStage
    """

    project_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = ProjectNewStage
        fields = [
            "id",
            "project_id",
            "title",
            "sequence",
            "is_end_stage",
        ]
        read_only_fields = ["id", "sequence"]

    def validate_project_id(self, value):
        """Validate project exists"""
        if not ProjectNew.objects.filter(id=value).exists():
            raise serializers.ValidationError("Project does not exist.")
        return value

    def validate(self, data):
        """Validate stage title"""
        if not data.get("title"):
            raise serializers.ValidationError({"title": "Stage title is required."})

        if len(data.get("title", "")) > 200:
            raise serializers.ValidationError(
                {"title": "Title cannot exceed 200 characters."}
            )

        return data

    def create(self, validated_data):
        """Create stage with project"""
        project_id = validated_data.pop("project_id")
        project = ProjectNew.objects.get(id=project_id)

        # Auto-calculate sequence if not provided
        if "sequence" not in validated_data or not validated_data["sequence"]:
            last_stage = (
                ProjectNewStage.objects.filter(project=project)
                .order_by("-sequence")
                .first()
            )
            validated_data["sequence"] = (last_stage.sequence + 1) if last_stage else 1

        stage = ProjectNewStage.objects.create(project=project, **validated_data)
        return stage


class ProjectNewStageReadSerializer(serializers.ModelSerializer):
    """
    Serializer for reading ProjectNewStage with project details
    """

    project_name = serializers.CharField(source="project.project_name", read_only=True)

    class Meta:
        model = ProjectNewStage
        fields = [
            "id",
            "project",
            "project_name",
            "title",
            "sequence",
            "is_end_stage",
            "created_at",
            "updated_at",
        ]
