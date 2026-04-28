import logging
from email.utils import formataddr

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import EmailMessage
from django.utils.html import escape
from rest_framework import serializers, status, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from base.backends import ConfiguredEmailBackend
from base.models import BrevoEmailConfiguration
from recruitment.models import Candidate
from recruitment.serializers import CandidateSerializer

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


def _get_recruitment_title(candidate):
    recruitment = getattr(candidate, "recruitment_id", None)
    if recruitment and getattr(recruitment, "title", None):
        return recruitment.title

    job_position = getattr(candidate, "job_position_id", None) or getattr(
        recruitment, "job_position_id", None
    )
    if job_position and getattr(job_position, "job_position", None):
        return job_position.job_position

    return "the selected position"


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


class ApplyNowViewSet(viewsets.ModelViewSet):
    queryset = Candidate.objects.all()
    serializer_class = CandidateSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        try:
            candidate = serializer.save()
            if candidate.recruitment_id and not candidate.stage_id:
                stages = candidate.recruitment_id.stage_set.all()
                applied_stage = stages.filter(stage_type="applied").first()
                candidate.stage_id = (
                    applied_stage if applied_stage else stages.order_by("sequence").first()
                )
                candidate.save()
            return candidate
        except DjangoValidationError as e:
            raise serializers.ValidationError(
                e.message_dict if hasattr(e, "message_dict") else list(e)
            )

    def _send_application_confirmation(self, candidate):
        candidate_name = escape(getattr(candidate, "name", None) or "Candidate")
        raw_company_name = _get_company_name(candidate)
        raw_role_name = _get_recruitment_title(candidate)
        company_name = escape(raw_company_name)
        role_name = escape(raw_role_name)
        support_email = escape(getattr(settings, "EMAIL_SUPPORT_EMAIL", "").strip())

        subject = f"Application Received - {raw_role_name} at {raw_company_name}"
        support_line = (
            f'<p style="margin:0 0 16px;">For any questions, you may contact us at '
            f'<a href="mailto:{support_email}">{support_email}</a>.</p>'
            if support_email
            else ""
        )
        html_content = f"""
        <div style="font-family: Arial, sans-serif; color: #1f2937; line-height: 1.6;">
          <p>Dear {candidate_name},</p>
          <p>
            Thank you for applying for the <strong>{role_name}</strong> position at
            <strong>{company_name}</strong>.
          </p>
          <p>
            We are pleased to confirm that your application has been received successfully.
            Our recruitment team will review your profile and reach out to you if your
            qualifications match our current requirements.
          </p>
          <p>
            We appreciate your interest in building your career with {company_name} and
            thank you for considering us as your next professional opportunity.
          </p>
          {support_line}
          <p style="margin-bottom:0;">Best regards,</p>
          <p style="margin-top:4px;">
            <strong>{company_name} Recruitment Team</strong>
          </p>
        </div>
        """.strip()
        text_content = (
            f"Dear {candidate.name or 'Candidate'},\n\n"
            f"Thank you for applying for the {raw_role_name} position at "
            f"{raw_company_name}.\n\n"
            "We are pleased to confirm that your application has been received successfully. "
            "Our recruitment team will review your profile and contact you if your "
            "qualifications match our current requirements.\n\n"
            f"We appreciate your interest in {raw_company_name}.\n"
        )
        if getattr(settings, "EMAIL_SUPPORT_EMAIL", "").strip():
            text_content += (
                f"\nFor any questions, please contact us at "
                f"{getattr(settings, 'EMAIL_SUPPORT_EMAIL').strip()}.\n"
            )
        text_content += (
            f"\nBest regards,\n{raw_company_name} Recruitment Team"
        )

        _send_recruitment_email(candidate, subject, html_content, text_content)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        candidate = self.perform_create(serializer)
        try:
            self._send_application_confirmation(candidate)
        except Exception as e:
            logger.exception("Email failed: %s", str(e))
            raise  # TEMP: re-raise to see the actual error
        headers = self.get_success_headers(serializer.data)
        data = serializer.data
        response_data = dict(data)
        response_data["status"] = "applied"
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)

    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
