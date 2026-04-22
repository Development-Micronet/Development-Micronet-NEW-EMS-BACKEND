import base64
from io import BytesIO
import os
from email.utils import formataddr
from urllib.parse import urlparse
from django.conf import settings
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
  <p>To,</p>
  <p>
    <strong>{{ instance.name }}</strong><br>
    Mobile: {{ instance.mobile|default:"-" }}<br>
    E-mail: {{ instance.email }}
  </p>
  <p style="text-align:center;"><strong><u>Sub: Offer Letter</u></strong></p>
  <p>Dear {{ instance.name }},</p>
  <p>
    With reference to your application and subsequent interview with us, we are pleased
    to offer you the position of <strong>{{ instance.job_position_id.job_position }}</strong>
    in our organization. We feel confident that you will contribute your skills and
    experience to the growth of our organization.
  </p>
  <p>
    We are pleased to appoint you for full-time employment.
    {% if instance.joining_date %}
    As per the discussion, your joining date will be on <strong>{{ instance.joining_date }}</strong>.
    {% else %}
    Your joining date will be communicated separately.
    {% endif %}
  </p>
  <p>Your remuneration and other terms will be shared as per the finalized discussion.</p>
  <p>Please submit the following documents at the time of reporting for duty:</p>
  <ul>
    <li>Photocopies of all educational testimonials.</li>
    <li>Address proof of permanent and present address.</li>
    <li>Photo ID proof.</li>
    <li>PAN card copy.</li>
  </ul>
  <p>
    Your offer of appointment may be withdrawn if any of the information furnished above
    is found to be incorrect.
  </p>
  <p>Wishing you all the best,</p>
  <p>For {{ instance.recruitment_id.company_id.company|default:"HR Team" }}</p>
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
                employee = Employee.objects.filter(email__iexact=email).first()
                if employee:
                    return employee
        else:
            candidate_values.append(data)

        for candidate in candidate_values:
            if candidate in (None, ""):
                continue

            candidate_str = str(candidate).strip()
            if candidate_str.isdigit():
                employee = Employee.objects.filter(
                    employee_user_id__id=int(candidate_str)
                ).first()
                if employee:
                    return employee

            if isinstance(candidate, str):
                employee = Employee.objects.filter(email__iexact=candidate_str).first()
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
        queryset=Employee.objects.all(),
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
        with transaction.atomic():
            candidate = super().create(validated_data)
            self._handle_offer_letter_status(
                candidate,
                previous_status=None,
                status_provided="offer_letter_status" in validated_data,
            )
            return candidate

    def update(self, instance, validated_data):
        previous_status = instance.offer_letter_status
        previous_stage_type = getattr(getattr(instance, "stage_id", None), "stage_type", None)
        status_provided = getattr(self, "_pending_status", serializers.empty)
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
                status_provided=status_provided is not serializers.empty,
            )
            return candidate

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

    def _send_candidate_rejection_mail(self, candidate):
        if not getattr(candidate, "email", None):
            return

        company_name = self._get_company_name(candidate)
        job_position = getattr(getattr(candidate, "job_position_id", None), "job_position", "the role")
        subject = f"{company_name} | Application Update"
        body = f"""
        <div style="background:#f6f8fb;padding:32px 16px;font-family:Arial,sans-serif;color:#101828;">
            <div style="max-width:700px;margin:0 auto;background:#ffffff;border:1px solid #d7deea;border-radius:18px;overflow:hidden;">
                <div style="background:linear-gradient(135deg,#1f2937,#334155);padding:24px 32px;">
                    <p style="margin:0;color:#e2e8f0;font-size:13px;letter-spacing:.08em;text-transform:uppercase;">{company_name}</p>
                    <h1 style="margin:10px 0 0;color:#ffffff;font-size:28px;line-height:1.25;">Application Update</h1>
                </div>
                <div style="padding:32px;">
                    <p style="margin:0 0 16px;color:#344054;line-height:1.7;">Dear {candidate.name},</p>
                    <p style="margin:0 0 16px;color:#344054;line-height:1.7;">
                        Thank you for your interest in the <strong>{job_position}</strong> opportunity at <strong>{company_name}</strong>.
                    </p>
                    <p style="margin:0 0 16px;color:#344054;line-height:1.7;">
                        After careful consideration, we regret to inform you that we will not be moving forward with your application at this time.
                    </p>
                    <p style="margin:0 0 16px;color:#344054;line-height:1.7;">
                        We appreciate the time and effort you invested in the process and encourage you to apply again for future opportunities that match your profile.
                    </p>
                    <p style="margin:0;color:#344054;line-height:1.7;">
                        Kind regards,<br>
                        Talent Acquisition Team<br>
                        {company_name}
                    </p>
                </div>
            </div>
        </div>
        """
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=self._get_recruitment_from_email(),
            to=[candidate.email],
            connection=ConfiguredEmailBackend(),
        )
        email.content_subtype = "html"
        email.send(fail_silently=False)

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
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=self._get_recruitment_from_email(),
            to=[candidate.email],
            connection=ConfiguredEmailBackend(),
        )
        email.content_subtype = "html"
        email.send(fail_silently=False)

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
        HorillaMailTemplate.objects.get_or_create(
            title=OFFER_LETTER_TEMPLATE_TITLE,
            defaults={
                "body": OFFER_LETTER_TEMPLATE_BODY,
                "company_id": getattr(
                    getattr(candidate, "recruitment_id", None), "company_id", None
                ),
            },
        )

    def _send_offer_letter_mail(self, candidate):
        request = self.context.get("request")
        protocol = getattr(request, "scheme", "http") if request else "http"
        host = request.get_host() if request else "127.0.0.1:8000"
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
                    "logo_data_uri": logo_data_uri,
                    "logo_cid": "company_logo_inline",
                },
                request=request,
            )
        except Exception:
            html_message = f"""
            <div style="font-family: Arial, Helvetica, sans-serif; color: #1f2937; line-height: 1.6;">
              <h2>Offer Letter</h2>
              <p>Dear {candidate.name},</p>
              <p>We are pleased to offer you the position of <strong>{job_position}</strong>.</p>
              <p><strong>Recruitment:</strong> {recruitment}</p>
              <p><strong>Joining Date:</strong> {joining_date}</p>
              <p><strong>Status:</strong> Sent</p>
              <p>Best regards,<br>HR Team</p>
            </div>
            """.strip()

        subject = f"Offer Letter - {candidate.name}"
        pdf_filename = f"offer_letter_{candidate.id}.pdf"
        text_content = (
            f"Dear {candidate.name},\n\n"
            f"We are pleased to offer you the position of {job_position}.\n"
            f"Recruitment: {recruitment}\n"
            f"Joining Date: {joining_date}\n\n"
            "Please review the offer letter and contact HR for any clarification.\n\n"
            "Best regards,\nHR Team"
        )
        pdf_content = self._build_offer_letter_pdf(
            candidate=candidate,
            host=host,
            protocol=protocol,
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

    def _build_offer_letter_pdf(self, candidate, host, protocol, logo_data_uri=None):
        buffer = BytesIO()
        try:
            html = render_to_string(
                "onboarding/mail_templates/offer_letter_pdf.html",
                {
                    "instance": candidate,
                    "host": host,
                    "protocol": protocol,
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
        logo_path = getattr(logo_field, "path", None)
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
        company = getattr(getattr(candidate, "recruitment_id", None), "company_id", None)
        company_name = getattr(company, "company", "") or "Authorized Signatory"
        return company_name

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
