from rest_framework import serializers

from base.models import Department, JobPosition
from employee.models import Employee
from recruitment.models import Candidate, Recruitment


class RecruitmentFlexibleField(serializers.RelatedField):
    def to_internal_value(self, data):
        if data in (None, ""):
            raise serializers.ValidationError("Recruitment is required.")
        value = str(data).strip()

        if value.isdigit():
            obj = Recruitment.objects.filter(id=int(value)).first()
            if obj:
                return obj

        obj = Recruitment.objects.filter(title__iexact=value).first()
        if obj:
            return obj

        # Auto-create recruitment to support name-based onboarding API payloads.
        obj = Recruitment.objects.create(
            title=value,
            description="Auto-created from onboarding candidate API",
            is_event_based=True,
            is_published=False,
            vacancy=1,
        )
        return obj

    def to_representation(self, value):
        return value.title


class JobPositionFlexibleField(serializers.RelatedField):
    def to_internal_value(self, data):
        if data in (None, ""):
            raise serializers.ValidationError("Job Position is required.")
        value = str(data).strip()

        if value.isdigit():
            obj = JobPosition.objects.filter(id=int(value)).first()
            if obj:
                return obj

        obj = JobPosition.objects.filter(job_position__iexact=value).first()
        if obj:
            return obj

        # Auto-create job position with a default department when not found.
        department = Department.objects.filter(department__iexact="General").first()
        if not department:
            department = Department.objects.create(department="General")
        obj = JobPosition.objects.create(job_position=value, department_id=department)
        return obj

    def to_representation(self, value):
        return value.job_position


class OnboardingCandidateSerializer(serializers.ModelSerializer):
    recruitment = RecruitmentFlexibleField(
        source="recruitment_id", queryset=Recruitment.objects.all()
    )
    job_position = JobPositionFlexibleField(
        source="job_position_id", queryset=JobPosition.objects.all()
    )
    referral = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        required=False,
        allow_null=True,
    )
    resume = serializers.FileField(required=False, allow_null=True)
    gender = serializers.CharField(required=False)
    source = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Candidate
        fields = [
            "id",
            "name",
            "portfolio",
            "email",
            "mobile",
            "recruitment",
            "job_position",
            "dob",
            "gender",
            "address",
            "source",
            "country",
            "state",
            "zip",
            "resume",
            "referral",
        ]

    def to_internal_value(self, data):
        if hasattr(data, "copy"):
            mutable = data.copy()
        else:
            mutable = dict(data)
        aliases = {
            "Name": "name",
            "Portfolio": "portfolio",
            "Email": "email",
            "Mobile": "mobile",
            "Recruitment": "recruitment",
            "Job Position": "job_position",
            "Date of Birth": "dob",
            "Gender": "gender",
            "Address": "address",
            "Source": "source",
            "Country": "country",
            "State": "state",
            "Zip Code": "zip",
            "Resume": "resume",
            "Referral": "referral",
        }
        for incoming_key, target_key in aliases.items():
            if incoming_key in mutable and target_key not in mutable:
                mutable[target_key] = mutable[incoming_key]
        return super().to_internal_value(mutable)

    def validate_gender(self, value):
        if value in (None, ""):
            return value
        normalized = str(value).strip().lower()
        allowed = {"male", "female", "other"}
        if normalized not in allowed:
            raise serializers.ValidationError("Gender must be Male, Female, or Other.")
        return normalized

    def validate_source(self, value):
        if value in (None, ""):
            return value
        normalized = str(value).strip().lower()
        source_map = {
            "application form": "application",
            "application": "application",
            "inside software": "software",
            "software": "software",
            "others": "other",
            "other": "other",
        }
        if normalized not in source_map:
            raise serializers.ValidationError(
                "Source must be Application Form, Inside software, or Others."
            )
        return source_map[normalized]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        recruitment = attrs.get("recruitment_id")
        job_position = attrs.get("job_position_id")
        if recruitment and job_position:
            # Candidate.save enforces job_position to be part of recruitment.open_positions.
            if not recruitment.open_positions.filter(id=job_position.id).exists():
                recruitment.open_positions.add(job_position)
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        source_display = {
            "application": "Application Form",
            "software": "Inside software",
            "other": "Others",
        }
        if instance.source:
            data["source"] = source_display.get(instance.source, instance.source)
        if instance.gender:
            data["gender"] = instance.gender.capitalize()
        return data
