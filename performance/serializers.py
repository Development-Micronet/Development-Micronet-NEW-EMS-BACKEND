from django.db import transaction
from rest_framework import serializers

from employee.models import Employee

from .models import KeyResult, Meeting, Objective, Question, QuestionTemplate


class EmployeeMiniSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = Employee
        fields = ["id", "full_name"]


class KeyResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = KeyResult
        fields = [
            "id",
            "title",
            "description",
            "progress_type",
            "target_value",
            "duration",
            "created_at",
            "updated_at",
        ]


class ObjectiveSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(
        source="employee.get_full_name", read_only=True
    )
    managers_detail = EmployeeMiniSerializer(
        source="managers", many=True, read_only=True
    )
    key_results = KeyResultSerializer(many=True, read_only=True)

    class Meta:
        model = Objective
        fields = [
            "id",
            "employee",
            "employee_name",
            "title",
            "objective",
            "description",
            "start_date",
            "end_date",
            "status",
            "managers",
            "managers_detail",
            "key_results",
        ]

    @transaction.atomic
    def create(self, validated_data):
        managers = validated_data.pop("managers", [])
        obj = Objective.objects.create(**validated_data)
        if managers:
            obj.managers.set(managers)
        return obj

    @transaction.atomic
    def update(self, instance, validated_data):
        managers = validated_data.pop("managers", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if managers is not None:
            instance.managers.set(managers)
        return instance


class MeetingSerializer(serializers.ModelSerializer):
    employees = serializers.PrimaryKeyRelatedField(
        queryset=Employee._base_manager.all(), many=True, required=False
    )
    answerable_employees = serializers.PrimaryKeyRelatedField(
        queryset=Employee._base_manager.all(), many=True, required=False
    )

    class Meta:
        model = Meeting
        fields = [
            "id",
            "title",
            "date",
            "employees",
            "manager",
            "answerable_employees",
            "question_template",
            "mom",
        ]

    def create(self, validated_data):
        employees = validated_data.pop("employees", [])
        answerable = validated_data.pop("answerable_employees", [])
        meeting = Meeting.objects.create(**validated_data)
        meeting.employees.set(employees)
        meeting.answerable_employees.set(answerable)
        return meeting

    def update(self, instance, validated_data):
        employees = validated_data.pop("employees", None)
        answerable = validated_data.pop("answerable_employees", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if employees is not None:
            instance.employees.set(employees)
        if answerable is not None:
            instance.answerable_employees.set(answerable)
        return instance


class QuestionTemplateSerializer(serializers.ModelSerializer):
    question_count = serializers.SerializerMethodField()

    class Meta:
        model = QuestionTemplate
        fields = ["id", "name", "question_count"]

    def get_question_count(self, obj):
        return obj.questions.count()


class QuestionSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source="template.name", read_only=True)

    class Meta:
        model = Question
        fields = ["id", "template", "template_name", "question", "answer_type"]

    def validate(self, attrs):
        answer_type = attrs.get("answer_type")
        if answer_type not in ["text", "mcq", "boolean", "rating"]:
            raise serializers.ValidationError({"answer_type": "Invalid answer type."})
        return attrs


from .models import Feedback


class FeedbackSerializer(serializers.ModelSerializer):

    employee_name = serializers.CharField(
        source="employee.get_full_name", read_only=True
    )

    class Meta:
        model = Feedback
        fields = [
            "id",
            "title",
            "employee",
            "employee_name",
            "start_date",
            "end_date",
            "question_template",
            "key_result",
            "status",
            "created_at",
        ]


from .models import FeedbackAnswer


class FeedbackAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedbackAnswer
        fields = [
            "id",
            "feedback",
            "question",
            "answer_text",
            "answer_boolean",
            "answer_rating",
        ]

    def validate(self, data):
        question = data.get("question")

        if question.answer_type == "text" and not data.get("answer_text"):
            raise serializers.ValidationError("Text answer required.")

        if question.answer_type == "boolean" and data.get("answer_boolean") is None:
            raise serializers.ValidationError("Boolean answer required.")

        if question.answer_type == "rating" and data.get("answer_rating") is None:
            raise serializers.ValidationError("Rating answer required.")

        return data


############# bonus point s #################

from .models import NewBonusEmployee


class NewBonusEmployeeSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = NewBonusEmployee
        fields = [
            "id",
            "employee",
            "employee_name",
            "bonus_points",
            "bonus_category",
            "reason",
            "awarded_date",
            "created_at",
            "updated_at",
        ]

    def get_employee_name(self, obj):
        return obj.employee.get_full_name()
