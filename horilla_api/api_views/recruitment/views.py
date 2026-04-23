import logging
from email.utils import formataddr

from django.conf import settings
from django.core.mail import EmailMessage
from django.shortcuts import get_object_or_404
from django.utils.html import escape
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from base.backends import ConfiguredEmailBackend
from base.models import BrevoEmailConfiguration
from employee.models import Employee
from horilla_api.api_serializers.onboarding.serializers import (
    OnboardingCandidateSerializer,
)
from horilla_api.api_serializers.recruitment.serializers import (
    RecruitmentInterviewSerializer,
    RecruitmentPipelineSerializer,
    RecruitmentSkillZoneCandidateSerializer,
    RecruitmentSkillZoneSerializer,
    RecruitmentStageSerializer,
    RecruitmentSurveyQuestionSerializer,
    RecruitmentSurveyTemplateSerializer,
)
from recruitment.models import (
    Candidate,
    InterviewSchedule,
    Recruitment,
    RecruitmentSurvey,
    SkillZone,
    SkillZoneCandidate,
    Stage,
    SurveyTemplate,
)

logger = logging.getLogger(__name__)
ACE_RECRUITMENT_FROM_NAME = "Ace Technologies Recruitment Team"

try:
    from brevo_email_sender import BrevoEmailSender

    BREVO_AVAILABLE = True
except ImportError:
    BREVO_AVAILABLE = False


def _get_company_name(candidate):
    brand_name = getattr(settings, "EMAIL_BRAND_NAME", "").strip()
    if brand_name:
        return brand_name
    company = getattr(getattr(candidate, "recruitment_id", None), "company_id", None)
    return getattr(company, "company", None) or "Ace Technologies"


def _get_recruitment_from_email():
    email_backend = ConfiguredEmailBackend()
    sender_email = getattr(email_backend, "dynamic_mail_sent_from", None) or getattr(
        email_backend, "dynamic_username", None
    ) or "noreply@acetechnologies.com"
    if sender_email:
        return formataddr((ACE_RECRUITMENT_FROM_NAME, sender_email))
    return ACE_RECRUITMENT_FROM_NAME


def _get_recruitment_mail_sender():
    from_email = getattr(settings, "BREVO_FROM_EMAIL", "").strip()
    from_name = getattr(settings, "BREVO_FROM_NAME", "").strip() or ACE_RECRUITMENT_FROM_NAME
    api_key = getattr(settings, "BREVO_API_KEY", "").strip()

    if not api_key:
        brevo_config = BrevoEmailConfiguration.objects.filter(is_active=True).first()
        if brevo_config:
            api_key = brevo_config.api_key
            from_email = brevo_config.from_email
            from_name = brevo_config.from_name or ACE_RECRUITMENT_FROM_NAME

    if not from_email:
        email_backend = ConfiguredEmailBackend()
        from_email = (
            getattr(email_backend, "dynamic_mail_sent_from", None)
            or getattr(email_backend, "dynamic_username", None)
            or "noreply@acetechnologies.com"
        )

    return {
        "api_key": api_key,
        "from_email": from_email,
        "from_name": from_name or ACE_RECRUITMENT_FROM_NAME,
    }


def _send_recruitment_email(candidate, subject, html_content, text_content):
    recipient_email = getattr(candidate, "email", None)
    if not recipient_email:
        return

    recipient_name = getattr(candidate, "name", None) or "Candidate"
    sender = _get_recruitment_mail_sender()

    if BREVO_AVAILABLE and sender["api_key"]:
        brevo_sender = BrevoEmailSender(
            api_key=sender["api_key"],
            from_email=sender["from_email"],
            from_name=sender["from_name"],
        )
        success, message, _message_id = brevo_sender.send_email(
            to_email=recipient_email,
            to_name=recipient_name,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
        )
        if success:
            logger.info(
                "Recruitment email sent via Brevo to %s with subject %s",
                recipient_email,
                subject,
            )
            return
        logger.warning(
            "Brevo email failed for %s with subject %s: %s",
            recipient_email,
            subject,
            message,
        )

    email = EmailMessage(
        subject=subject,
        body=html_content,
        from_email=formataddr((sender["from_name"], sender["from_email"])),
        to=[recipient_email],
        connection=ConfiguredEmailBackend(fail_silently=False),
    )
    email.content_subtype = "html"
    email.send(fail_silently=False)


def _format_interview_date(value):
    if not value:
        return ""
    return value.strftime("%A, %d %B %Y")


def _format_interview_time(value):
    if not value:
        return ""
    return value.strftime("%I:%M %p").lstrip("0")


def _get_recruitment_title(candidate):
    recruitment = getattr(candidate, "recruitment_id", None)
    if not recruitment:
        return "our team"

    if getattr(recruitment, "title", None):
        return recruitment.title

    job_position = getattr(recruitment, "job_position_id", None)
    if job_position and getattr(job_position, "job_position", None):
        return job_position.job_position

    return "our team"


def _send_interview_schedule_email(interview, is_update=False):
    candidate = getattr(interview, "candidate_id", None)
    candidate_email = getattr(candidate, "email", None)
    if not candidate or not candidate_email:
        return

    interviewer_names = [
        employee.get_full_name() or employee.employee_first_name or str(employee)
        for employee in interview.employee_id.all()
    ]
    interviewer_text = ", ".join(filter(None, interviewer_names)) or "our hiring team"
    recruitment_title = escape(_get_recruitment_title(candidate))
    interview_date = escape(_format_interview_date(interview.interview_date))
    interview_time = escape(_format_interview_time(interview.interview_time))
    candidate_name = escape(candidate.name)
    interviewer_text = escape(interviewer_text)
    company_name = escape(_get_company_name(candidate))
    schedule_label = "updated" if is_update else "scheduled"
    subject = (
        f"{company_name} | Interview {schedule_label.capitalize()} - {recruitment_title}"
        if recruitment_title
        else f"{company_name} | Interview {schedule_label.capitalize()}"
    )
    description_block = ""
    description_text = ""
    if interview.description:
        description_block = f"""
            <p style="margin:0 0 12px;color:#475467;line-height:1.7;">
                <strong>Notes:</strong> {escape(interview.description)}
            </p>
        """
        description_text = f"\nNotes: {interview.description}"

    body = f"""
    <div style="background:#f6f8fb;padding:32px 16px;font-family:Arial,sans-serif;color:#101828;">
        <div style="max-width:700px;margin:0 auto;background:#ffffff;border:1px solid #d7deea;border-radius:18px;overflow:hidden;">
            <div style="background:linear-gradient(135deg,#0f172a,#1d4ed8);padding:24px 32px;">
                <p style="margin:0;color:#dbeafe;font-size:13px;letter-spacing:.08em;text-transform:uppercase;">
                    {company_name}
                </p>
                <h1 style="margin:10px 0 0;color:#ffffff;font-size:28px;line-height:1.25;">
                    Your interview has been {schedule_label}.
                </h1>
            </div>
            <div style="padding:32px;">
                <p style="margin:0 0 16px;color:#344054;line-height:1.7;">
                    Dear {candidate_name},
                </p>
                <p style="margin:0 0 16px;color:#344054;line-height:1.7;">
                    Thank you for your interest in <strong>{recruitment_title}</strong> at <strong>{company_name}</strong>.
                    We are pleased to move forward with your application and invite you to the interview stage.
                </p>
                <div style="margin:24px 0;padding:22px;border-radius:14px;background:#f8fbff;border:1px solid #dbe4f0;">
                    <p style="margin:0 0 10px;color:#0f172a;"><strong>Date:</strong> {interview_date}</p>
                    <p style="margin:0 0 10px;color:#0f172a;"><strong>Time:</strong> {interview_time}</p>
                    <p style="margin:0 0 10px;color:#0f172a;"><strong>Interviewers:</strong> {interviewer_text}</p>
                </div>
                {description_block}
                <p style="margin:0 0 16px;color:#344054;line-height:1.7;">
                    Please be available a few minutes before the scheduled time. If you need any assistance or would like to request a reschedule, simply reply to this email.
                </p>
                <p style="margin:0;color:#344054;line-height:1.7;">
                    Best regards,<br>
                    Talent Acquisition Team<br>
                    {company_name}
                </p>
            </div>
        </div>
    </div>
    """
    text_content = (
        f"Dear {candidate.name},\n\n"
        f"Your interview has been {schedule_label}.\n"
        f"Company: {_get_company_name(candidate)}\n"
        f"Role: {_get_recruitment_title(candidate)}\n"
        f"Date: {_format_interview_date(interview.interview_date)}\n"
        f"Time: {_format_interview_time(interview.interview_time)}\n"
        f"Interviewers: {', '.join(filter(None, interviewer_names)) or 'our hiring team'}"
        f"{description_text}\n\n"
        "Please be available a few minutes before the scheduled time. "
        "If you need any assistance or would like to request a reschedule, reply to this email.\n\n"
        f"Best regards,\nTalent Acquisition Team\n{_get_company_name(candidate)}"
    )
    _send_recruitment_email(candidate, subject, body, text_content)


class RecruitmentPipelineAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RecruitmentPipelineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Recruitment pipeline created successfully",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def get(self, request, pk=None):
        queryset = Recruitment.objects.select_related(
            "job_position_id", "company_id"
        ).prefetch_related("recruitment_managers", "survey_templates", "skills")

        if pk:
            recruitment = get_object_or_404(queryset, pk=pk)
            serializer = RecruitmentPipelineSerializer(recruitment)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = RecruitmentPipelineSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Recruitment pipeline ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        recruitment = get_object_or_404(Recruitment, pk=pk)
        serializer = RecruitmentPipelineSerializer(
            recruitment, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Recruitment pipeline updated successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Recruitment pipeline ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        recruitment = get_object_or_404(Recruitment, pk=pk)
        recruitment.delete()
        return Response(
            {"message": "Recruitment pipeline deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )

class RecruitmentCarrersAPIView(APIView):


    def get(self, request, pk=None):
        queryset = Recruitment.objects.select_related(
            "job_position_id", "company_id"
        ).prefetch_related("recruitment_managers", "survey_templates", "skills")

        if pk:
            recruitment = get_object_or_404(queryset, pk=pk)
            serializer = RecruitmentPipelineSerializer(recruitment)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = RecruitmentPipelineSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    

 

class RecruitmentCandidateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OnboardingCandidateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        candidate = serializer.save()
        return Response(
            {
                "message": "Candidate created successfully",
                "data": OnboardingCandidateSerializer(candidate).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def get(self, request, pk=None):
        if pk:
            candidate = get_object_or_404(Candidate, pk=pk)
            serializer = OnboardingCandidateSerializer(
                candidate, context={"request": request}
            )
            return Response(serializer.data, status=status.HTTP_200_OK)

        candidates = Candidate.objects.all().order_by("-id")
        serializer = OnboardingCandidateSerializer(
            candidates, many=True, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Candidate ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        candidate = get_object_or_404(Candidate, pk=pk)
        serializer = OnboardingCandidateSerializer(
            candidate, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        updated_candidate = serializer.save()
        return Response(
            {
                "message": "Candidate updated successfully",
                "data": OnboardingCandidateSerializer(
                    updated_candidate, context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Candidate ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        candidate = get_object_or_404(Candidate, pk=pk)
        candidate.delete()
        return Response(
            {"message": "Candidate deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )


class RecruitmentSurveyTemplateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RecruitmentSurveyTemplateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Survey template created successfully",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def get(self, request, pk=None):
        if pk:
            instance = get_object_or_404(SurveyTemplate, pk=pk)
            serializer = RecruitmentSurveyTemplateSerializer(
                instance, context={"request": request}
            )
            return Response(serializer.data, status=status.HTTP_200_OK)

        queryset = SurveyTemplate.objects.select_related("company_id").order_by("-id")
        serializer = RecruitmentSurveyTemplateSerializer(
            queryset, many=True, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Survey template ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance = get_object_or_404(SurveyTemplate, pk=pk)
        serializer = RecruitmentSurveyTemplateSerializer(
            instance, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Survey template updated successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Survey template ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance = get_object_or_404(SurveyTemplate, pk=pk)
        instance.delete()
        return Response(
            {"message": "Survey template deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )


class RecruitmentSurveyQuestionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RecruitmentSurveyQuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Survey question created successfully",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def get(self, request, pk=None):
        queryset = RecruitmentSurvey.objects.prefetch_related(
            "template_id", "recruitment_ids"
        ).order_by("sequence", "id")
        if pk:
            instance = get_object_or_404(queryset, pk=pk)
            serializer = RecruitmentSurveyQuestionSerializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = RecruitmentSurveyQuestionSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Survey question ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance = get_object_or_404(RecruitmentSurvey, pk=pk)
        serializer = RecruitmentSurveyQuestionSerializer(
            instance, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Survey question updated successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Survey question ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance = get_object_or_404(RecruitmentSurvey, pk=pk)
        instance.delete()
        return Response(
            {"message": "Survey question deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )


class RecruitmentStageAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RecruitmentStageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Recruitment stage created successfully",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def get(self, request, pk=None):
        queryset = Stage.objects.select_related("recruitment_id").prefetch_related(
            "stage_managers", "recruitment_id__recruitment_managers"
        ).order_by("sequence", "id")
        if pk:
            instance = get_object_or_404(queryset, pk=pk)
            serializer = RecruitmentStageSerializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = RecruitmentStageSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Recruitment stage ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance = get_object_or_404(Stage, pk=pk)
        serializer = RecruitmentStageSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Recruitment stage updated successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Recruitment stage ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance = get_object_or_404(Stage, pk=pk)
        instance.delete()
        return Response(
            {"message": "Recruitment stage deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )


class LegacyRecruitmentInterviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RecruitmentInterviewSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        interview = serializer.save()

        interviewer_ids = request.data.get("interviewers", [])

        # 🔥 FETCH using base manager (IMPORTANT)
        employees = Employee._base_manager.filter(id__in=interviewer_ids)

        interview.employee_id.set(employees)

        # Refresh from DB to ensure M2M is up-to-date for serialization
        interview.refresh_from_db()

        try:
            _send_interview_schedule_email(interview, is_update=False)
        except Exception:
            logger.exception(
                "Failed to send interview email for interview id=%s",
                interview.pk,
            )

        return Response({
            "message": "Interview created successfully",
            "data": RecruitmentInterviewSerializer(interview).data,
        })

    def get(self, request, pk=None):
        print("interview geting")
        queryset = InterviewSchedule.objects.select_related("candidate_id").prefetch_related(
            "employee_id"
        ).order_by("-interview_date", "-id")
        if pk:
            instance = get_object_or_404(queryset, pk=pk)
            serializer = RecruitmentInterviewSerializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = RecruitmentInterviewSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Interview ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance = get_object_or_404(InterviewSchedule, pk=pk)
        serializer = RecruitmentInterviewSerializer(
            instance, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        interview = serializer.save()
        try:
            _send_interview_schedule_email(interview, is_update=True)
        except Exception:
            logger.exception(
                "Failed to send updated interview email for interview id=%s",
                interview.pk,
            )
        return Response(
            {
                "message": "Interview updated successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Interview ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance = get_object_or_404(InterviewSchedule, pk=pk)
        instance.delete()
        return Response(
            {"message": "Interview deleted successfully"},
            status=status.HTTP_200_OK,
        )

class RecruitmentInterviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RecruitmentInterviewSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        interview = serializer.save()
        interview.refresh_from_db()

        try:
            _send_interview_schedule_email(interview, is_update=False)
        except Exception:
            logger.exception(
                "Failed to send interview email for interview id=%s",
                interview.pk,
            )

        return Response(
            {
                "message": "Interview created successfully",
                "data": RecruitmentInterviewSerializer(interview).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def get(self, request, pk=None):
        queryset = InterviewSchedule.objects.select_related("candidate_id").prefetch_related(
            "employee_id"
        ).order_by("-interview_date", "-id")
        if pk:
            instance = get_object_or_404(queryset, pk=pk)
            serializer = RecruitmentInterviewSerializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = RecruitmentInterviewSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Interview ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance = get_object_or_404(InterviewSchedule, pk=pk)
        serializer = RecruitmentInterviewSerializer(
            instance, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        interview = serializer.save()
        interview.refresh_from_db()

        try:
            _send_interview_schedule_email(interview, is_update=True)
        except Exception:
            logger.exception(
                "Failed to send updated interview email for interview id=%s",
                interview.pk,
            )

        return Response(
            {
                "message": "Interview updated successfully",
                "data": RecruitmentInterviewSerializer(interview).data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Interview ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance = get_object_or_404(InterviewSchedule, pk=pk)
        instance.delete()
        return Response(
            {"message": "Interview deleted successfully"},
            status=status.HTTP_200_OK,
        )


class RecruitmentSkillZoneAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RecruitmentSkillZoneSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Skill zone created successfully",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def get(self, request, pk=None):
        queryset = SkillZone.objects.select_related("company_id").order_by("-id")
        if pk:
            instance = get_object_or_404(queryset, pk=pk)
            serializer = RecruitmentSkillZoneSerializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = RecruitmentSkillZoneSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Skill zone ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance = get_object_or_404(SkillZone, pk=pk)
        serializer = RecruitmentSkillZoneSerializer(
            instance, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Skill zone updated successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Skill zone ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance = get_object_or_404(SkillZone, pk=pk)
        instance.delete()
        return Response(
            {"message": "Skill zone deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )


class RecruitmentSkillZoneCandidateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RecruitmentSkillZoneCandidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Candidate added to skill zone successfully",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def get(self, request, pk=None):
        queryset = SkillZoneCandidate.objects.select_related(
            "skill_zone_id", "candidate_id"
        ).order_by("-id")
        if pk:
            instance = get_object_or_404(queryset, pk=pk)
            serializer = RecruitmentSkillZoneCandidateSerializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = RecruitmentSkillZoneCandidateSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Skill zone candidate ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance = get_object_or_404(SkillZoneCandidate, pk=pk)
        serializer = RecruitmentSkillZoneCandidateSerializer(
            instance, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Skill zone candidate updated successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"error": "Skill zone candidate ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance = get_object_or_404(SkillZoneCandidate, pk=pk)
        instance.delete()
        return Response(
            {"message": "Skill zone candidate deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )
