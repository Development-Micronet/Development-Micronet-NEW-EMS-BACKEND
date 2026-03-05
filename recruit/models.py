import os
import uuid

# Create your models here.
from django.db import models
from django.utils import timezone

from employee.models import Employee


def candidate_resume_upload_path(instance, filename):
    ext = filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join("candidates/resumes/", filename)


class Candidate(models.Model):

    RECRUITMENT_TYPE_CHOICES = [
        ("future_drive", "Future Drive"),
        ("recruitment_drive", "Recruitment Drive"),
    ]

    SOURCE_CHOICES = [
        ("insider_software", "Insider Software"),
        ("application_form", "Application Form"),
    ]

    STATUS_CHOICES = [
        ("applied", "Applied"),
        ("initial", "Initial"),
        ("interview", "Interview"),
        ("hired", "Hired"),
        ("cancelled", "Cancelled"),
    ]

    name = models.CharField(max_length=200)
    portfolio = models.URLField(null=True, blank=True)
    email = models.EmailField()
    mobile = models.CharField(max_length=20)

    recruitment_type = models.CharField(max_length=50, choices=RECRUITMENT_TYPE_CHOICES)

    job_position = models.CharField(max_length=200)

    date_of_birth = models.DateField()
    gender = models.CharField(max_length=20)
    address = models.TextField()
    zip_code = models.CharField(max_length=20)

    source = models.CharField(max_length=50, choices=SOURCE_CHOICES)

    referral = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referred_candidates",
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="applied")

    resume = models.FileField(
        upload_to=candidate_resume_upload_path, null=True, blank=True
    )

    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name


from django.db import models

from employee.models import Employee


class Interview(models.Model):

    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("selected", "Selected"),
        ("rejected", "Rejected"),
    ]

    candidate = models.ForeignKey(
        "Candidate", on_delete=models.CASCADE, related_name="interviews"
    )

    interviewer = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        related_name="conducted_interviews",
    )

    interview_date = models.DateField()
    interview_time = models.TimeField()

    description = models.TextField(null=True, blank=True)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="scheduled"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.candidate.name} - {self.interview_date}"


from django.db import models

from employee.models import Employee


# ==========================
# SKILL ZONE
# ==========================
class SkillZone(models.Model):
    name = models.CharField(max_length=150, unique=True)

    def __str__(self):
        return self.name


# ==========================
# CANDIDATE SKILL MAPPING
# ==========================
class CandidateSkill(models.Model):
    candidate = models.ForeignKey(
        "Candidate", on_delete=models.CASCADE, related_name="skills"
    )
    skill = models.ForeignKey(
        SkillZone, on_delete=models.CASCADE, related_name="candidate_skills"
    )

    class Meta:
        unique_together = ("candidate", "skill")

    def __str__(self):
        return f"{self.candidate.name} - {self.skill.name}"
