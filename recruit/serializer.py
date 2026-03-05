from rest_framework import serializers

from .models import Candidate


class CandidateSerializer(serializers.ModelSerializer):

    resume_link = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Candidate
        fields = [
            "id",
            "name",
            "portfolio",
            "email",
            "mobile",
            "recruitment_type",
            "job_position",
            "date_of_birth",
            "gender",
            "address",
            "zip_code",
            "source",
            "referral",
            "status",
            "resume",
            "resume_link",
        ]

    def get_resume_link(self, obj):
        request = self.context.get("request")
        if obj.resume and request:
            return request.build_absolute_uri(obj.resume.url)
        return None


from rest_framework import serializers

from .models import Interview


class InterviewSerializer(serializers.ModelSerializer):

    candidate_name = serializers.CharField(source="candidate.name", read_only=True)
    interviewer_name = serializers.SerializerMethodField()
    resume_link = serializers.SerializerMethodField()

    class Meta:
        model = Interview
        fields = [
            "id",
            "candidate",
            "candidate_name",
            "interviewer",
            "interviewer_name",
            "interview_date",
            "interview_time",
            "description",
            "status",
            "resume_link",
        ]

    def get_interviewer_name(self, obj):
        if obj.interviewer:
            return f"{obj.interviewer.employee_first_name} {obj.interviewer.employee_last_name}"
        return None

    def get_resume_link(self, obj):
        request = self.context.get("request")
        if obj.candidate.resume and request:
            return request.build_absolute_uri(obj.candidate.resume.url)
        return None


from rest_framework import serializers

from .models import CandidateSkill, SkillZone


# ==========================
# SKILL SERIALIZER
# ==========================
class SkillZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkillZone
        fields = ["id", "name"]


# ==========================
# CANDIDATE SKILL SERIALIZER
# ==========================
class CandidateSkillSerializer(serializers.ModelSerializer):
    candidate_name = serializers.CharField(source="candidate.name", read_only=True)
    skill_name = serializers.CharField(source="skill.name", read_only=True)

    class Meta:
        model = CandidateSkill
        fields = [
            "id",
            "candidate",
            "candidate_name",
            "skill",
            "skill_name",
        ]
