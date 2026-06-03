import base64
from io import BytesIO
import os
from email.utils import formataddr
from urllib.parse import urlparse
from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from email.mime.image import MIMEImage
from rest_framework import serializers
from xhtml2pdf import pisa

from base.backends import ConfiguredEmailBackend
from base.models import BrevoEmailConfiguration, HorillaMailTemplate
from base.models import Department, JobPosition
from employee.models import Employee
from recruitment.models import Candidate, Recruitment, Stage

try:
    from brevo_email_sender import BrevoEmailSender

    BREVO_AVAILABLE = True
except ImportError:
    BREVO_AVAILABLE = False

OFFER_LETTER_TEMPLATE_TITLE = "Offer Letter"
ACE_RECRUITMENT_FROM_NAME = "Ace Technologies Recruitment Team"
OFFER_LETTER_TEMPLATE_BODY = """
<div style="font-family: 'Times New Roman', serif; color: #111827; line-height: 1.65;">
  <p><strong>Private & Confidential</strong></p>
  <p>Date: {{ instance.joining_date|default:"To be communicated" }}</p>
  <p>
    <strong>{{ instance.name }}</strong><br>
    Mobile: {{ instance.mobile|default:"-" }}<br>
    Email: {{ instance.email }}
  </p>
  <p style="text-align:center;"><strong><u>Subject: Offer of Employment</u></strong></p>
  <p>Dear {{ instance.name }},</p>
  <p>
    We are pleased to offer you the position of
    <strong>{{ instance.job_position_id.job_position|default:"the offered role" }}</strong>
    with <strong>{{ company_name|default:"Ace Technologies" }}</strong>.
  </p>
  <p>
    This offer reflects our confidence in your experience, capabilities, and the value you can
    bring to our team. We believe you will make a meaningful contribution to the continued growth
    of our organization.
  </p>
  <p>
    {% if instance.joining_date %}
    Your proposed joining date will be <strong>{{ instance.joining_date }}</strong>.
    {% else %}
    Your proposed joining date will be communicated separately by our HR team.
    {% endif %}
    Additional details regarding compensation, benefits, and employment terms will be shared with
    you as part of the onboarding process.
  </p>
  <p>Please submit the following documents at the time of joining for verification:</p>
  <ul>
    <li>Copies of educational certificates and testimonials.</li>
    <li>Proof of permanent and current address.</li>
    <li>Government-issued photo identification.</li>
    <li>PAN card copy.</li>
  </ul>
  <p>
    This offer is subject to the accuracy of the information and documents submitted during the
    selection and onboarding process.
  </p>
  <p>
    We look forward to welcoming you to <strong>{{ company_name|default:"Ace Technologies" }}</strong>
    and wish you every success in your new role.
  </p>
  <p>Warm regards,</p>
  <p>For {{ company_name|default:"Ace Technologies" }}</p>
  <p>Authorized Signatory</p>
</div>
""".strip()


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


class EmployeeFlexibleField(serializers.PrimaryKeyRelatedField):
    def _employee_queryset(self):
        return Employee._base_manager.all()

    def _ensure_employee_for_admin_user(self, user):
        if not (user.is_superuser or user.is_staff):
            self.fail("does_not_exist", pk_value=user.pk)

        employee, _created = Employee._base_manager.get_or_create(
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
        if employee.role != "admin":
            updates["role"] = "admin"

        if updates:
            Employee._base_manager.filter(pk=employee.pk).update(**updates)
            for field, value in updates.items():
                setattr(employee, field, value)

        return employee

    def _resolve_user_or_employee(self, candidate):
        if candidate in (None, ""):
            return None

        candidate_str = str(candidate).strip()

        if candidate_str.isdigit():
            candidate_id = int(candidate_str)
            user = User.objects.filter(pk=candidate_id).first()
            if user:
                employee = self._employee_queryset().filter(employee_user_id=user).first()
                if employee:
                    return employee
                if user.is_superuser or user.is_staff:
                    return self._ensure_employee_for_admin_user(user)

            employee = self._employee_queryset().filter(pk=candidate_id).first()
            if employee:
                return employee

        employee = self._employee_queryset().filter(email__iexact=candidate_str).first()
        if employee:
            return employee

        user = User.objects.filter(email__iexact=candidate_str).first()
        if user:
            employee = self._employee_queryset().filter(employee_user_id=user).first()
            if employee:
                return employee
            if user.is_superuser or user.is_staff:
                return self._ensure_employee_for_admin_user(user)

        employee = self._employee_queryset().filter(badge_id__iexact=candidate_str).first()
        if employee:
            return employee

        return None

    def to_internal_value(self, data):
        if data in (None, ""):
            if self.allow_null:
                return None
            self.fail("required")

        try:
            return super().to_internal_value(data)
        except serializers.ValidationError:
            pass

        candidate_values = []
        if isinstance(data, dict):
            candidate_values.extend(
                [data.get("id"), data.get("employee_id"), data.get("user_id")]
            )
            email = data.get("email")
            if email:
                employee = self._resolve_user_or_employee(email)
                if employee:
                    return employee
        else:
            candidate_values.append(data)

        for candidate in candidate_values:
            employee = self._resolve_user_or_employee(candidate)
            if employee:
                return employee

        self.fail("does_not_exist", pk_value=data)


class OnboardingCandidateSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    stage_id = serializers.PrimaryKeyRelatedField(
        queryset=Stage.objects.all(), required=False, allow_null=True
    )
    recruitment = RecruitmentFlexibleField(
        source="recruitment_id", queryset=Recruitment.objects.all()
    )
    job_position = JobPositionFlexibleField(
        source="job_position_id", queryset=JobPosition.objects.all()
    )
    referral = EmployeeFlexibleField(
        queryset=Employee._base_manager.all(),
        required=False,
        allow_null=True,
    )
    referral_data = serializers.SerializerMethodField(read_only=True)
    resume = serializers.FileField(required=False, allow_null=True)
    gender = serializers.CharField(required=False)
    source = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    offer_letter_status = serializers.ChoiceField(
        choices=Candidate.offer_letter_statuses, required=False
    )

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
            "city",
            "zip",
            "resume",
            "referral",
            "referral_data",
            "offer_letter_status",
            "stage_id",
            "status",
        ]

    def get_status(self, obj):
        # Return the stage_type if stage_id is set, else 'applied'
        if hasattr(obj, 'stage_id') and obj.stage_id:
            return getattr(obj.stage_id, 'stage_type', 'applied')
        return "applied"

    def to_internal_value(self, data):
        if hasattr(data, "copy"):
            mutable = data.copy()
        else:
            mutable = dict(data)
        self._pending_status = mutable.get("status", mutable.get("Status", serializers.empty))
        aliases = {
            "Name": "name",
            "Portfolio": "portfolio",
            "Email": "email",
            "Mobile": "mobile",
            "Recruitment": "recruitment",
            "recruitment_id": "recruitment",
            "Job Position": "job_position",
            "job_position_id": "job_position",
            "Date of Birth": "dob",
            "Gender": "gender",
            "Address": "address",
            "Source": "source",
            "Country": "country",
            "State": "state",
            "City": "city",
            "Zip Code": "zip",
            "Resume": "resume",
            "Referral": "referral",
            "referral_id": "referral",
            "Status": "status",
            "Offer Letter": "offer_letter_status",
            "Offer Letter Status": "offer_letter_status",
        }
        for incoming_key, target_key in aliases.items():
            if incoming_key in mutable and target_key not in mutable:
                mutable[target_key] = mutable[incoming_key]

        resume_value = mutable.get("resume", serializers.empty)
        if isinstance(resume_value, str):
            normalized_resume = resume_value.strip()
            if normalized_resume == "":
                mutable["resume"] = None
            elif self._is_existing_resume_reference(normalized_resume):
                mutable.pop("resume", None)
            else:
                raise serializers.ValidationError(
                    {
                        "resume": [
                            "Resume must be uploaded as a PDF file. Omit this field to keep the existing resume."
                        ]
                    }
                )
        return super().to_internal_value(mutable)

    def _is_existing_resume_reference(self, value):
        instance = getattr(self, "instance", None)
        current_resume = getattr(instance, "resume", None)
        if not instance or not current_resume:
            return False

        candidates = {str(current_resume), current_resume.name}
        try:
            candidates.add(current_resume.url)
        except ValueError:
            pass

        parsed_value = urlparse(value)
        if parsed_value.path:
            candidates.add(parsed_value.path)
            candidates.add(parsed_value.path.lstrip("/"))

        normalized_candidates = {item.strip().lstrip("/") for item in candidates if item}
        return value.strip().lstrip("/") in normalized_candidates

    def _normalize_status(self, value):
        if value in (None, ""):
            return None

        normalized = str(value).strip().lower().replace(" ", "_")
        alias_map = {"canceled": "cancelled"}
        normalized = alias_map.get(normalized, normalized)

        valid_statuses = {choice[0] for choice in Stage.stage_types}
        display_map = {
            str(label).strip().lower().replace(" ", "_"): key
            for key, label in Stage.stage_types
        }

        if normalized in valid_statuses:
            return normalized
        if normalized in display_map:
            return display_map[normalized]

        raise serializers.ValidationError(
            {
                "status": [
                    "Status must be one of initial, applied, test, interview, cancelled, or hired."
                ]
            }
        )

    def _resolve_stage_from_status(self, recruitment, normalized_status, stage=None):
        if stage and stage.stage_type == normalized_status:
            return stage

        if not recruitment:
            raise serializers.ValidationError(
                {"status": ["Recruitment is required to resolve status."]}
            )

        resolved_stage = (
            Stage.objects.filter(
                recruitment_id=recruitment,
                stage_type=normalized_status,
            )
            .order_by("sequence", "id")
            .first()
        )
        if resolved_stage:
            return resolved_stage

        if normalized_status == "cancelled":
            return Stage.objects.create(
                recruitment_id=recruitment,
                stage="Cancelled Candidates",
                stage_type="cancelled",
                sequence=50,
            )

        raise serializers.ValidationError(
            {
                "status": [
                    f'No stage found for status "{normalized_status}" in this recruitment.'
                ]
            }
        )

    def validate_offer_letter_status(self, value):
        if value in (None, ""):
            return value
        normalized = str(value).strip().lower().replace(" ", "_")
        valid_statuses = dict(Candidate.offer_letter_statuses)
        display_map = {
            str(label).strip().lower().replace(" ", "_"): key
            for key, label in Candidate.offer_letter_statuses
        }
        if normalized in valid_statuses:
            return normalized
        if normalized in display_map:
            return display_map[normalized]
        raise serializers.ValidationError(
            "Offer letter status must be one of not_sent, sent, accepted, rejected, or joined."
        )

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

    def validate_resume(self, value):
        if value in (None, ""):
            return value
        filename = getattr(value, "name", "")
        if not filename.lower().endswith(".pdf"):
            raise serializers.ValidationError("Resume must be a PDF file.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        recruitment = attrs.get("recruitment_id") or getattr(
            self.instance, "recruitment_id", None
        )
        job_position = attrs.get("job_position_id")
        if recruitment and job_position:
            # Candidate.save enforces job_position to be part of recruitment.open_positions.
            if not recruitment.open_positions.filter(id=job_position.id).exists():
                recruitment.open_positions.add(job_position)

        stage = attrs.get("stage_id")
        pending_status = getattr(self, "_pending_status", serializers.empty)
        if pending_status is not serializers.empty:
            normalized_status = self._normalize_status(pending_status)
            if normalized_status is not None:
                stage = self._resolve_stage_from_status(
                    recruitment=recruitment,
                    normalized_status=normalized_status,
                    stage=stage,
                )
                attrs["stage_id"] = stage

        if stage:
            attrs["hired"] = stage.stage_type == "hired"
            attrs["canceled"] = stage.stage_type == "cancelled"
            attrs["start_onboard"] = False
        return attrs

    def create(self, validated_data):
        status_email_requested = self._status_email_requested(validated_data)
        with transaction.atomic():
            candidate = super().create(validated_data)
            self._handle_offer_letter_status(
                candidate,
                previous_status=None,
                status_provided="offer_letter_status" in validated_data,
            )
            self._handle_pending_status_email(
                candidate=candidate,
                previous_stage_type=None,
                status_provided=status_email_requested,
            )
            return candidate

    def update(self, instance, validated_data):
        previous_status = instance.offer_letter_status
        previous_stage_type = getattr(getattr(instance, "stage_id", None), "stage_type", None)
        status_email_requested = self._status_email_requested(validated_data)
        with transaction.atomic():
            candidate = super().update(instance, validated_data)
            self._handle_offer_letter_status(
                candidate,
                previous_status=previous_status,
                status_provided="offer_letter_status" in validated_data,
            )
            self._handle_pending_status_email(
                candidate=candidate,
                previous_stage_type=previous_stage_type,
                status_provided=status_email_requested,
            )
            return candidate

    def _status_email_requested(self, validated_data):
        pending_status = getattr(self, "_pending_status", serializers.empty)
        return pending_status is not serializers.empty or "stage_id" in validated_data

    def _handle_pending_status_email(
        self, candidate, previous_stage_type=None, status_provided=False
    ):
        if not status_provided:
            return

        current_stage_type = getattr(getattr(candidate, "stage_id", None), "stage_type", None)
        if current_stage_type == previous_stage_type:
            return

        if current_stage_type == "cancelled":
            self._send_candidate_rejection_mail(candidate)
        elif current_stage_type == "interview":
            self._send_candidate_interview_stage_mail(candidate)

    def _get_company_name(self, candidate):
        brand_name = getattr(settings, "EMAIL_BRAND_NAME", "").strip()
        if brand_name:
            return brand_name
        company = getattr(getattr(candidate, "recruitment_id", None), "company_id", None)
        return getattr(company, "company", None) or "Ace Technologies"

    def _get_recruitment_from_email(self):
        email_backend = ConfiguredEmailBackend()
        sender_email = getattr(
            email_backend, "dynamic_mail_sent_from", None
        ) or getattr(email_backend, "dynamic_username", None) or "noreply@acetechnologies.com"
        if sender_email:
            return formataddr((ACE_RECRUITMENT_FROM_NAME, sender_email))
        return ACE_RECRUITMENT_FROM_NAME

    def _get_mail_sender(self):
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

    def _send_candidate_email(self, candidate, subject, html_content, text_content):
        recipient_email = getattr(candidate, "email", None)
        if not recipient_email:
            return

        sender = self._get_mail_sender()
        recipient_name = getattr(candidate, "name", None) or "Candidate"

        if BREVO_AVAILABLE and sender["api_key"]:
            brevo_sender = BrevoEmailSender(
                api_key=sender["api_key"],
                from_email=sender["from_email"],
                from_name=sender["from_name"],
            )
            success, _message, _message_id = brevo_sender.send_email(
                to_email=recipient_email,
                to_name=recipient_name,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
            )
            if success:
                return

        email = EmailMessage(
            subject=subject,
            body=html_content,
            from_email=formataddr((sender["from_name"], sender["from_email"])),
            to=[recipient_email],
            connection=ConfiguredEmailBackend(fail_silently=False),
        )
        email.content_subtype = "html"
        email.send(fail_silently=False)

    def _send_candidate_rejection_mail(self, candidate):
        if not getattr(candidate, "email", None):
            return

        company_name = self._get_company_name(candidate)
        job_position = getattr(getattr(candidate, "job_position_id", None), "job_position", "the role")
        subject = f"{company_name} | Application Status Update"
        body = f"""
        <div style="background:#f6f8fb;padding:32px 16px;font-family:Arial,sans-serif;color:#101828;">
            <div style="max-width:700px;margin:0 auto;background:#ffffff;border:1px solid #d7deea;border-radius:18px;overflow:hidden;">
                <div style="background:linear-gradient(135deg,#1f2937,#334155);padding:24px 32px;">
                    <p style="margin:0;color:#e2e8f0;font-size:13px;letter-spacing:.08em;text-transform:uppercase;">{company_name}</p>
                    <h1 style="margin:10px 0 0;color:#ffffff;font-size:28px;line-height:1.25;">Thank you for your interest in {company_name}</h1>
                </div>
                <div style="padding:32px;">
                    <p style="margin:0 0 16px;color:#344054;line-height:1.7;">Dear {candidate.name},</p>
                    <p style="margin:0 0 16px;color:#344054;line-height:1.7;">
                        Thank you for your interest in the <strong>{job_position}</strong> opportunity at <strong>{company_name}</strong>.
                    </p>
                    <p style="margin:0 0 16px;color:#344054;line-height:1.7;">
                        After careful consideration, we regret to inform you that unfortunately we will not be moving forward with your application for this role.
                    </p>
                    <p style="margin:0 0 16px;color:#344054;line-height:1.7;">
                        This decision was not easy, and we sincerely appreciate the time, effort, and interest you invested in the selection process.
                    </p>
                    <p style="margin:0 0 16px;color:#344054;line-height:1.7;">
                        We will be glad to stay in touch and encourage you to apply again for future opportunities at <strong>{company_name}</strong> that match your profile and experience.
                    </p>
                    <p style="margin:0;color:#344054;line-height:1.7;">
                        Wishing you success in your career journey.<br><br>
                        Kind regards,<br>
                        Talent Acquisition Team<br>
                        {company_name}
                    </p>
                </div>
            </div>
        </div>
        """
        text_content = (
            f"Dear {candidate.name},\n\n"
            f"Thank you for your interest in the {job_position} opportunity at {company_name}.\n"
            "After careful consideration, unfortunately we will not be moving forward with your application for this role.\n"
            "We sincerely appreciate the time, effort, and interest you invested in the selection process.\n"
            f"We encourage you to apply again for future opportunities at {company_name} that match your profile and experience.\n\n"
            "Wishing you success in your career journey.\n\n"
            f"Kind regards,\nTalent Acquisition Team\n{company_name}"
        )
        self._send_candidate_email(candidate, subject, body, text_content)

    def _send_candidate_interview_stage_mail(self, candidate):
        if not getattr(candidate, "email", None):
            return

        company_name = self._get_company_name(candidate)
        job_position = getattr(getattr(candidate, "job_position_id", None), "job_position", "the role")
        subject = f"{company_name} | Interview Process Update"
        body = f"""
        <div style="background:#f6f8fb;padding:32px 16px;font-family:Arial,sans-serif;color:#101828;">
            <div style="max-width:700px;margin:0 auto;background:#ffffff;border:1px solid #d7deea;border-radius:18px;overflow:hidden;">
                <div style="background:linear-gradient(135deg,#0f172a,#1d4ed8);padding:24px 32px;">
                    <p style="margin:0;color:#dbeafe;font-size:13px;letter-spacing:.08em;text-transform:uppercase;">{company_name}</p>
                    <h1 style="margin:10px 0 0;color:#ffffff;font-size:28px;line-height:1.25;">You have been shortlisted for the interview stage</h1>
                </div>
                <div style="padding:32px;">
                    <p style="margin:0 0 16px;color:#344054;line-height:1.7;">Dear {candidate.name},</p>
                    <p style="margin:0 0 16px;color:#344054;line-height:1.7;">
                        We are pleased to inform you that your application for the <strong>{job_position}</strong> position at <strong>{company_name}</strong> has progressed to the interview stage.
                    </p>
                    <p style="margin:0 0 16px;color:#344054;line-height:1.7;">
                        Our recruitment team will share the interview schedule and next steps with you shortly.
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
            f"We are pleased to inform you that your application for the {job_position} position at {company_name} has progressed to the interview stage.\n"
            "Our recruitment team will share the interview schedule and next steps with you shortly.\n\n"
            f"Best regards,\nTalent Acquisition Team\n{company_name}"
        )
        self._send_candidate_email(candidate, subject, body, text_content)

    def _handle_offer_letter_status(
        self, candidate, previous_status=None, status_provided=False
    ):
        current_status = candidate.offer_letter_status
        should_send = current_status == "sent" and (
            previous_status != "sent" or status_provided
        )
        if not should_send:
            return

        self._ensure_offer_letter_template(candidate)
        self._send_offer_letter_mail(candidate)

    def _ensure_offer_letter_template(self, candidate):
        company = getattr(getattr(candidate, "recruitment_id", None), "company_id", None)
        template, _created = HorillaMailTemplate.objects.get_or_create(
            title=OFFER_LETTER_TEMPLATE_TITLE,
            defaults={"body": OFFER_LETTER_TEMPLATE_BODY, "company_id": company},
        )
        updates = {}
        if template.body != OFFER_LETTER_TEMPLATE_BODY:
            updates["body"] = OFFER_LETTER_TEMPLATE_BODY
        if getattr(template, "company_id", None) != company:
            updates["company_id"] = company

        if updates:
            for field, value in updates.items():
                setattr(template, field, value)
            template.save(update_fields=list(updates.keys()))

    def _send_offer_letter_mail(self, candidate):
        request = self.context.get("request")
        protocol = getattr(request, "scheme", "http") if request else "http"
        host = request.get_host() if request else "127.0.0.1:8000"
        company_name = self._get_company_name(candidate)
        logo_data_uri = self._get_company_logo_data_uri(candidate)
        logo_path = self._get_company_logo_path(candidate)
        job_position = getattr(
            getattr(candidate, "job_position_id", None), "job_position", "-"
        )
        recruitment = getattr(getattr(candidate, "recruitment_id", None), "title", "-")
        joining_date = getattr(candidate, "joining_date", None) or "To be discussed"

        try:
            html_message = render_to_string(
                "onboarding/mail_templates/offer_letter.html",
                {
                    "instance": candidate,
                    "host": host,
                    "protocol": protocol,
                    "company_name": company_name,
                    "logo_data_uri": logo_data_uri,
                    "logo_cid": "company_logo_inline",
                },
                request=request,
            )
        except Exception:
            html_message = f"""
            <div style="font-family: Arial, Helvetica, sans-serif; color: #1f2937; line-height: 1.6;">
              <h2>{company_name} Offer Letter</h2>
              <p>Dear {candidate.name},</p>
              <p>We are pleased to offer you the position of <strong>{job_position}</strong> with <strong>{company_name}</strong>.</p>
              <p><strong>Recruitment:</strong> {recruitment}</p>
              <p><strong>Joining Date:</strong> {joining_date}</p>
              <p>Please review the attached offer letter for the complete terms and next steps.</p>
              <p>Warm regards,<br>{company_name} Talent Acquisition Team</p>
            </div>
            """.strip()

        subject = f"{company_name} | Offer Letter - {candidate.name}"
        pdf_filename = f"offer_letter_{candidate.id}.pdf"
        text_content = (
            f"Dear {candidate.name},\n\n"
            f"We are pleased to offer you the position of {job_position} with {company_name}.\n"
            f"Recruitment: {recruitment}\n"
            f"Joining Date: {joining_date}\n\n"
            "Please review the attached offer letter for the complete terms, conditions, and next steps.\n"
            "If you have any questions, our Talent Acquisition team will be happy to assist you.\n\n"
            f"Warm regards,\n{company_name} Talent Acquisition Team"
        )
        pdf_content = self._build_offer_letter_pdf(
            candidate=candidate,
            host=host,
            protocol=protocol,
            company_name=company_name,
            logo_data_uri=logo_data_uri,
        )
        if not pdf_content.startswith(b"%PDF"):
            preview = pdf_content[:300].decode("utf-8", errors="ignore")
            print(
                f"[OfferLetter] PDF generation failed for candidate_id={candidate.id}. "
                f"Response preview: {preview}"
            )
            raise serializers.ValidationError(
                {
                    "offer_letter_status": (
                        "Offer letter PDF could not be generated correctly."
                    )
                }
            )
        print(
            f"[OfferLetter] Triggered for candidate_id={candidate.id}, "
            f"email={candidate.email}, status={candidate.offer_letter_status}"
        )
        print(
            f"[OfferLetter] PDF generated successfully for candidate_id={candidate.id} "
            f"filename={pdf_filename}"
        )

        if BREVO_AVAILABLE:
            api_key = getattr(settings, "BREVO_API_KEY", "").strip()
            from_email = getattr(settings, "BREVO_FROM_EMAIL", "noreply@horilla.com")
            from_name = ACE_RECRUITMENT_FROM_NAME
            if not api_key:
                brevo_config = BrevoEmailConfiguration.objects.filter(
                    is_active=True
                ).first()
                if brevo_config:
                    api_key = brevo_config.api_key
                    from_email = brevo_config.from_email
                    from_name = ACE_RECRUITMENT_FROM_NAME

            if api_key:
                try:
                    print(
                        f"[OfferLetter] Trying Brevo send to {candidate.email} "
                        f"with from_email={from_email}"
                    )
                    sender = BrevoEmailSender(
                        api_key=api_key,
                        from_email=from_email,
                        from_name=from_name,
                    )
                    success, _, _ = sender.send_email(
                        to_email=candidate.email,
                        to_name=candidate.name,
                        subject=subject,
                        html_content=html_message,
                        text_content=text_content,
                        attachments=[
                            {
                                "name": pdf_filename,
                                "content": base64.b64encode(pdf_content).decode("utf-8"),
                            }
                        ],
                    )
                    if success:
                        print(
                            f"[OfferLetter] Mail sent successfully via Brevo "
                            f"to {candidate.email}"
                        )
                        return
                    print(
                        f"[OfferLetter] Brevo send returned unsuccessful result "
                        f"for {candidate.email}"
                    )
                except Exception:
                    import traceback

                    print(
                        f"[OfferLetter] Brevo send failed for {candidate.email}"
                    )
                    traceback.print_exc()
            else:
                print("[OfferLetter] Brevo not configured. Falling back to SMTP.")
        else:
            print("[OfferLetter] Brevo package not available. Falling back to SMTP.")

        try:
            email_backend = ConfiguredEmailBackend()
            from_email = self._get_recruitment_from_email()
            print(
                f"[OfferLetter] Trying SMTP send to {candidate.email} "
                f"with from_email={from_email}"
            )
            message = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=from_email,
                to=[candidate.email],
                connection=ConfiguredEmailBackend(fail_silently=False),
            )
            message.attach_alternative(html_message, "text/html")
            if logo_path and os.path.exists(logo_path):
                with open(logo_path, "rb") as logo_file:
                    logo_img = MIMEImage(logo_file.read())
                    logo_img.add_header("Content-ID", "<company_logo_inline>")
                    logo_img.add_header("Content-Disposition", "inline", filename=os.path.basename(logo_path))
                    message.attach(logo_img)
            message.attach(pdf_filename, pdf_content, "application/pdf")
            message.send(fail_silently=False)
            print(
                f"[OfferLetter] Mail sent successfully via SMTP to {candidate.email}"
            )
            return
        except Exception as exc:
            import traceback

            print(f"[OfferLetter] SMTP send failed for {candidate.email}: {exc}")
            traceback.print_exc()
            raise serializers.ValidationError(
                {
                    "offer_letter_status": (
                        "Offer letter email could not be sent: "
                        f"{exc}"
                    )
                }
            )

    def _build_offer_letter_pdf(
        self, candidate, host, protocol, company_name=None, logo_data_uri=None
    ):
        buffer = BytesIO()
        try:
            html = render_to_string(
                "onboarding/mail_templates/offer_letter_pdf.html",
                {
                    "instance": candidate,
                    "host": host,
                    "protocol": protocol,
                    "company_name": company_name or self._get_company_name(candidate),
                    "logo_data_uri": logo_data_uri,
                    "stamp_data_uri": self._get_stamp_data_uri(),
                    "signature_text": self._get_signature_text(candidate),
                },
                request=self.context.get("request"),
            )
            pdf = pisa.CreatePDF(src=html, dest=buffer)
            if pdf.err:
                raise serializers.ValidationError(
                    {
                        "offer_letter_status": "Offer letter PDF generation failed during template rendering."
                    }
                )
            return buffer.getvalue()
        except Exception as exc:
            print(
                f"[OfferLetter] xhtml2pdf generation exception for candidate_id={candidate.id}: {exc}"
            )
            raise serializers.ValidationError(
                {
                    "offer_letter_status": f"Offer letter PDF generation failed: {exc}"
                }
            )
        finally:
            buffer.close()

    def _get_company_logo_path(self, candidate):
        company = getattr(getattr(candidate, "recruitment_id", None), "company_id", None)
        logo_field = getattr(company, "icon", None)
        if not logo_field:
            return None

        logo_name = getattr(logo_field, "name", None)
        if not logo_name:
            return None

        try:
            logo_path = logo_field.path
        except (AttributeError, NotImplementedError, ValueError):
            return None

        if logo_path and os.path.exists(logo_path):
            return logo_path
        return None

    def _get_company_logo_data_uri(self, candidate):
        logo_path = self._get_company_logo_path(candidate)
        if not logo_path:
            fallback_logo = os.path.join(
                settings.BASE_DIR,
                "payroll",
                "templates",
                "payroll",
                "payslip",
                "company_logo.png",
            )
            if os.path.exists(fallback_logo):
                logo_path = fallback_logo
        if not logo_path:
            return None
        ext = os.path.splitext(logo_path)[1].lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".svg": "image/svg+xml",
        }
        mime_type = mime_map.get(ext, "application/octet-stream")
        try:
            with open(logo_path, "rb") as logo_file:
                encoded = base64.b64encode(logo_file.read()).decode("utf-8")
            return f"data:{mime_type};base64,{encoded}"
        except Exception:
            return None

    def _get_stamp_data_uri(self):
        stamp_path = os.path.join(
            settings.BASE_DIR,
            "payroll",
            "templates",
            "payroll",
            "payslip",
            "stamp.png",
        )
        if not os.path.exists(stamp_path):
            return None
        with open(stamp_path, "rb") as stamp_file:
            return "data:image/png;base64," + base64.b64encode(
                stamp_file.read()
            ).decode("ascii")

    def _get_signature_text(self, candidate):
        return self._get_company_name(candidate) or "Authorized Signatory"

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

    def get_referral_data(self, obj):
        referral = getattr(obj, "referral", None)
        if not referral:
            return None
        return {
            "id": referral.id,
            "badge_id": getattr(referral, "badge_id", None),
            "name": referral.get_full_name(),
            "email": getattr(referral, "email", None),
        }
