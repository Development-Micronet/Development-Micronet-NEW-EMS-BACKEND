import base64
import time
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import resolve
from django.test.utils import override_settings
from rest_framework.test import APIClient

from base.models import Company, Department, JobPosition
from employee.models import Employee
from horilla.horilla_middlewares import _thread_locals
from offboarding.models import Offboarding, ResignationLetter
from recruitment.models import Candidate, Recruitment, Stage, SurveyTemplate


class AuthRecruitmentOffboardingAPITest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            company="Ace Technologys",
            address="Plot No 80, KT Nagar, Nagpur, Maharashtra 440013",
            country="India",
            state="Maharashtra",
            city="Nagpur",
            zip="440013",
        )
        self.company.created_by = None
        self.company.modified_by = None
        self.company.save(update_fields=["created_by", "modified_by"])
        self.user = User.objects.create_user(username="apitester", password="password")
        self.employee = Employee.objects.create(
            employee_user_id=self.user,
            employee_first_name="Nisha",
            employee_last_name="Dhamange",
            email="nisha@example.com",
            phone="9999999999",
        )
        self.client = APIClient()

    def tearDown(self):
        if hasattr(_thread_locals, "request"):
            _thread_locals.request = None

    def test_login_allows_anonymous_and_returns_401_for_invalid_credentials(self):
        response = self.client.post(
            "/api/auth/login/",
            {"username": "apitester", "password": "wrong-password"},
            format="json",
        )

        assert response.status_code == 401
        assert response.json()["error"] == "Invalid credentials"

    @override_settings(
        RETURN_RESET_LINK_IN_FORGOT_PASSWORD_RESPONSE=True,
        FRONTEND_RESET_PASSWORD_URL="",
    )
    @patch("horilla_api.api_views.auth.views.ForgotPasswordAPIView._send_with_brevo")
    def test_forgot_password_returns_usable_reset_token_for_five_minutes(
        self, mock_send_with_brevo
    ):
        mock_send_with_brevo.return_value = True

        forgot_response = self.client.post(
            "/api/auth/forgot-password/",
            {"email": self.employee.email},
            format="json",
        )

        assert forgot_response.status_code == 200
        forgot_data = forgot_response.json()
        assert "uid" in forgot_data
        assert "token" in forgot_data
        assert "reset_link" in forgot_data
        assert forgot_data["reset_link"].startswith("http://testserver/auth/reset-password/")

    @override_settings(
        RETURN_RESET_LINK_IN_FORGOT_PASSWORD_RESPONSE=True,
        FRONTEND_RESET_PASSWORD_URL="",
    )
    @patch("horilla_api.api_views.auth.views.ForgotPasswordAPIView._send_with_brevo")
    def test_forgot_password_ignores_frontend_origin_for_backend_reset_page(
        self, mock_send_with_brevo
    ):
        mock_send_with_brevo.return_value = True

        forgot_response = self.client.post(
            "/api/auth/forgot-password/",
            {"email": self.employee.email},
            format="json",
            HTTP_ORIGIN="http://192.168.1.50:5173",
        )

        assert forgot_response.status_code == 200
        forgot_data = forgot_response.json()
        assert forgot_data["reset_link"].startswith(
            "http://testserver/auth/reset-password/"
        )

    @override_settings(
        RETURN_RESET_LINK_IN_FORGOT_PASSWORD_RESPONSE=True,
        FRONTEND_RESET_PASSWORD_URL="",
        PUBLIC_BACKEND_URL="http://13.202.113.121",
    )
    @patch("horilla_api.api_views.auth.views.ForgotPasswordAPIView._send_with_brevo")
    def test_forgot_password_uses_public_backend_url_when_configured(
        self, mock_send_with_brevo
    ):
        mock_send_with_brevo.return_value = True

        forgot_response = self.client.post(
            "/api/auth/forgot-password/",
            {"email": self.employee.email},
            format="json",
        )

        assert forgot_response.status_code == 200
        forgot_data = forgot_response.json()
        assert forgot_data["reset_link"].startswith(
            "http://13.202.113.121/auth/reset-password/"
        )

        reset_response = self.client.post(
            "/api/auth/reset-password/",
            {
                "uid": forgot_data["uid"],
                "token": forgot_data["token"],
                "new_password": "NewPassword@123",
                "confirm_password": "NewPassword@123",
            },
            format="json",
        )

        assert reset_response.status_code == 200
        assert reset_response.json()["success"] is True
        self.user.refresh_from_db()
        assert self.user.check_password("NewPassword@123") is True

    @override_settings(
        RETURN_RESET_LINK_IN_FORGOT_PASSWORD_RESPONSE=True,
        PASSWORD_RESET_TIMEOUT=1,
    )
    @patch("horilla_api.api_views.auth.views.ForgotPasswordAPIView._send_with_brevo")
    def test_reset_password_rejects_expired_signed_token(self, mock_send_with_brevo):
        mock_send_with_brevo.return_value = True

        forgot_response = self.client.post(
            "/api/auth/forgot-password/",
            {"email": self.employee.email},
            format="json",
        )

        assert forgot_response.status_code == 200
        forgot_data = forgot_response.json()
        time.sleep(2)

        reset_response = self.client.post(
            "/api/auth/reset-password/",
            {
                "uid": forgot_data["uid"],
                "token": forgot_data["token"],
                "new_password": "ExpiredPassword@123",
                "confirm_password": "ExpiredPassword@123",
            },
            format="json",
        )

        assert reset_response.status_code == 400
        assert reset_response.json()["success"] is False
        assert "expired" in reset_response.json()["message"].lower()

    def test_recruitment_interviews_url_resolves_to_new_api_view(self):
        match = resolve("/api/recruitment/interviews/")
        assert match.func.view_class.__name__ == "RecruitmentInterviewAPIView"

    def test_recruitment_stage_create_accepts_admin_user_id_in_stage_managers(self):
        self.client.force_authenticate(user=self.user)
        admin_user = User.objects.create_user(
            username="recruitstageadmin",
            password="password",
            is_staff=True,
            email="recruitstageadmin@example.com",
        )
        department = Department.objects.create(department="Recruitment Department")
        job_position = JobPosition.objects.create(
            job_position="Recruiter",
            department_id=department,
        )
        recruitment = Recruitment.objects.create(
            title="Stage Hiring",
            description="Hiring pipeline",
            is_event_based=True,
            is_published=False,
            vacancy=1,
            company_id=self.company,
        )
        recruitment.open_positions.add(job_position)

        response = self.client.post(
            "/api/recruitment/stage-view/",
            {
                "recruitment": recruitment.id,
                "stage_managers": [admin_user.id],
                "stage": "Manager Review",
                "stage_type": "interview",
            },
            format="json",
        )

        assert response.status_code == 201
        created_employee = Employee.objects.get(employee_user_id=admin_user)
        assert response.json()["data"]["stage_managers"] == [
            {"id": created_employee.id, "name": created_employee.get_full_name()}
        ]

    def test_recruitment_stage_create_returns_field_error_for_duplicate_stage(self):
        self.client.force_authenticate(user=self.user)
        department = Department.objects.create(department="Duplicate Stage Department")
        job_position = JobPosition.objects.create(
            job_position="Duplicate Stage Role",
            department_id=department,
        )
        recruitment = Recruitment.objects.create(
            title="Duplicate Stage Hiring",
            description="Hiring pipeline",
            is_event_based=True,
            is_published=False,
            vacancy=1,
            company_id=self.company,
        )
        recruitment.open_positions.add(job_position)
        Stage.objects.create(
            recruitment_id=recruitment,
            stage="Manager Review",
            stage_type="interview",
            sequence=10,
        )

        response = self.client.post(
            "/api/recruitment/stage-view/",
            {
                "recruitment": recruitment.id,
                "stage_managers": [self.employee.id],
                "stage": "Manager Review",
                "stage_type": "interview",
            },
            format="json",
        )

        assert response.status_code == 400
        assert response.json() == {
            "stage": ["This stage already exists for the selected recruitment."]
        }

    def test_recruitment_stage_list_falls_back_to_recruitment_managers(self):
        self.client.force_authenticate(user=self.user)
        admin_user = User.objects.create_user(
            username="recruitstagefallbackadmin",
            password="password",
            is_staff=True,
            email="recruitstagefallbackadmin@example.com",
        )
        admin_employee = Employee.objects.create(
            employee_user_id=admin_user,
            employee_first_name="Fallback",
            employee_last_name="Manager",
            email="fallback.manager@example.com",
            phone="9999999901",
            role="admin",
        )
        department = Department.objects.create(department="Fallback Stage Department")
        job_position = JobPosition.objects.create(
            job_position="Fallback Recruiter",
            department_id=department,
        )
        recruitment = Recruitment.objects.create(
            title="Fallback Stage Hiring",
            description="Hiring pipeline",
            is_event_based=True,
            is_published=False,
            vacancy=1,
            company_id=self.company,
        )
        recruitment.open_positions.add(job_position)
        recruitment.recruitment_managers.set([admin_employee])

        response = self.client.get("/api/recruitment/stage-view/")

        assert response.status_code == 200
        applied_stage = next(
            item
            for item in response.json()
            if item["recruitment"]["id"] == recruitment.id and item["stage"] == "Applied"
        )
        assert applied_stage["stage_managers"] == [
            {"id": admin_employee.id, "name": admin_employee.get_full_name()}
        ]

    def test_recruitment_stage_detail_includes_inactive_stage_manager(self):
        self.client.force_authenticate(user=self.user)
        admin_user = User.objects.create_user(
            username="recruitstageinactiveadmin",
            password="password",
            is_staff=True,
            email="recruitstageinactiveadmin@example.com",
        )
        inactive_employee = Employee.objects.create(
            employee_user_id=admin_user,
            employee_first_name="Inactive",
            employee_last_name="Manager",
            email="inactive.manager@example.com",
            phone="9999999902",
            role="admin",
            is_active=False,
        )
        department = Department.objects.create(department="Inactive Stage Department")
        job_position = JobPosition.objects.create(
            job_position="Inactive Stage Recruiter",
            department_id=department,
        )
        recruitment = Recruitment.objects.create(
            title="Inactive Stage Hiring",
            description="Hiring pipeline",
            is_event_based=True,
            is_published=False,
            vacancy=1,
            company_id=self.company,
        )
        recruitment.open_positions.add(job_position)
        stage = Stage.objects.create(
            recruitment_id=recruitment,
            stage="Inactive Manager Review",
            stage_type="interview",
            sequence=2,
        )
        stage.stage_managers.set([inactive_employee])

        response = self.client.get(f"/api/recruitment/stage-view/{stage.id}/")

        assert response.status_code == 200
        assert response.json()["stage_managers"] == [
            {"id": inactive_employee.id, "name": inactive_employee.get_full_name()}
        ]

    @override_settings(EMAIL_BRAND_NAME="Ace Technologies")
    @patch("recruitment.api_apply_now._send_recruitment_email")
    def test_apply_now_sends_professional_confirmation_email(self, mock_send_email):
        department = Department.objects.create(department="Apply Now Department")
        job_position = JobPosition.objects.create(
            job_position="Python Developer",
            department_id=department,
        )
        recruitment = Recruitment.objects.create(
            title="Backend Engineer",
            description="Public hiring flow",
            is_event_based=True,
            is_published=True,
            vacancy=2,
            company_id=self.company,
        )
        recruitment.open_positions.add(job_position)
        applied_stage = recruitment.stage_set.filter(stage_type="applied").first()
        if not applied_stage:
            applied_stage = Stage.objects.create(
                recruitment_id=recruitment,
                stage="Applied",
                stage_type="applied",
                sequence=1,
            )

        response = self.client.post(
            "/api/recruitment/apply-now/",
            {
                "name": "Public Candidate",
                "recruitment_id": recruitment.id,
                "job_position_id": job_position.id,
                "email": "public.candidate@example.com",
                "mobile": "9999999915",
                "resume": base64.b64encode(b"%PDF-1.4 apply now").decode("utf-8"),
                "gender": "female",
                "address": "Nagpur",
                "country": "India",
                "state": "Maharashtra",
                "city": "Nagpur",
                "zip": "440013",
            },
            format="json",
        )

        assert response.status_code == 201
        assert response.json()["status"] == "applied"

        candidate = Candidate.objects.get(email="public.candidate@example.com")
        assert candidate.stage_id_id == applied_stage.id

        mock_send_email.assert_called_once()
        sent_candidate, subject, html_content, text_content = mock_send_email.call_args[0]
        assert sent_candidate.id == candidate.id
        assert subject == "Application Received - Backend Engineer at Ace Technologies"
        assert "Thank you for applying" in html_content
        assert "Ace Technologies Recruitment Team" in html_content
        assert "application has been received successfully" in text_content

    def test_recruitment_candidate_post_accepts_inactive_employee_user_id_in_referral(self):
        self.client.force_authenticate(user=self.user)
        department = Department.objects.create(department="Referral Department")
        job_position = JobPosition.objects.create(
            job_position="Referral Engineer",
            department_id=department,
        )
        recruitment = Recruitment.objects.create(
            title="Referral Hiring",
            description="Hiring flow",
            is_event_based=True,
            is_published=False,
            vacancy=1,
            company_id=self.company,
        )
        recruitment.open_positions.add(job_position)
        referral_user = User.objects.create_user(
            username="inactive_referral_user",
            password="password",
            email="inactive.referral@example.com",
        )
        referral_employee = Employee.objects.create(
            employee_user_id=referral_user,
            employee_first_name="Inactive",
            employee_last_name="Referral",
            email="inactive.referral.employee@example.com",
            phone="9999999913",
            is_active=False,
        )

        response = self.client.post(
            "/api/recruitment/candidates/",
            {
                "name": "Referral Candidate",
                "recruitment": recruitment.id,
                "job_position": job_position.id,
                "email": "referral.candidate@example.com",
                "mobile": "9999999914",
                "referral": referral_user.id,
                "resume": SimpleUploadedFile(
                    "referral_resume.pdf",
                    b"%PDF-1.4 referral",
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )

        assert response.status_code == 201
        candidate = Candidate.objects.get(email="referral.candidate@example.com")
        assert candidate.referral_id == referral_employee.id
        assert response.json()["data"]["referral_data"] == {
            "id": referral_employee.id,
            "badge_id": referral_employee.badge_id,
            "name": referral_employee.get_full_name(),
            "email": referral_employee.email,
        }

    def test_recruitment_candidate_post_accepts_admin_user_id_in_referral(self):
        self.client.force_authenticate(user=self.user)
        department = Department.objects.create(department="Admin Referral Department")
        job_position = JobPosition.objects.create(
            job_position="Admin Referral Engineer",
            department_id=department,
        )
        recruitment = Recruitment.objects.create(
            title="Admin Referral Hiring",
            description="Hiring flow",
            is_event_based=True,
            is_published=False,
            vacancy=1,
            company_id=self.company,
        )
        recruitment.open_positions.add(job_position)
        admin_user = User.objects.create_user(
            username="candidate_referral_admin",
            password="password",
            email="candidate.referral.admin@example.com",
            is_staff=True,
        )

        response = self.client.post(
            "/api/recruitment/candidates/",
            {
                "name": "Admin Referral Candidate",
                "recruitment": recruitment.id,
                "job_position": job_position.id,
                "email": "admin.referral.candidate@example.com",
                "mobile": "9999999915",
                "referral": admin_user.id,
                "resume": SimpleUploadedFile(
                    "admin_referral_resume.pdf",
                    b"%PDF-1.4 admin referral",
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )

        assert response.status_code == 201
        referral_employee = Employee.objects.get(employee_user_id=admin_user)
        candidate = Candidate.objects.get(email="admin.referral.candidate@example.com")
        assert referral_employee.role == "admin"
        assert candidate.referral_id == referral_employee.id
        assert response.json()["data"]["referral_data"] == {
            "id": referral_employee.id,
            "badge_id": referral_employee.badge_id,
            "name": referral_employee.get_full_name(),
            "email": referral_employee.email,
        }

    def test_recruitment_candidate_put_updates_stage_from_status(self):
        self.client.force_authenticate(user=self.user)
        department = Department.objects.create(department="Engineering")
        job_position = JobPosition.objects.create(
            job_position="Backend Engineer",
            department_id=department,
        )
        recruitment = Recruitment.objects.create(
            title="Backend Hiring",
            description="Hiring for backend team",
            is_event_based=True,
            is_published=False,
            vacancy=1,
            company_id=self.company,
        )
        recruitment.open_positions.add(job_position)
        applied_stage = recruitment.stage_set.get(stage_type="applied")
        interview_stage = Stage.objects.create(
            recruitment_id=recruitment,
            stage="Interview",
            stage_type="interview",
            sequence=2,
        )
        candidate = Candidate.objects.create(
            name="John Doe",
            recruitment_id=recruitment,
            job_position_id=job_position,
            stage_id=applied_stage,
            email="john.doe@example.com",
            mobile="9999999999",
            resume=SimpleUploadedFile(
                "resume.pdf",
                b"%PDF-1.4 test resume",
                content_type="application/pdf",
            ),
        )

        response = self.client.put(
            f"/api/recruitment/candidates/{candidate.id}/",
            {"status": "interview"},
            format="json",
        )

        assert response.status_code == 200
        candidate.refresh_from_db()
        assert candidate.stage_id_id == interview_stage.id
        assert candidate.hired is False
        assert candidate.canceled is False
        assert response.json()["data"]["status"] == "interview"

    @patch("horilla_api.api_views.recruitment.views._send_interview_schedule_email")
    def test_recruitment_interview_post_sends_professional_schedule_email(self, mock_send):
        self.client.force_authenticate(user=self.user)
        department = Department.objects.create(department="Interview Department")
        job_position = JobPosition.objects.create(
            job_position="QA Engineer",
            department_id=department,
        )
        recruitment = Recruitment.objects.create(
            title="Interview Hiring",
            description="Hiring for interviews",
            is_event_based=True,
            is_published=False,
            vacancy=1,
            company_id=self.company,
        )
        recruitment.open_positions.add(job_position)
        candidate = Candidate.objects.create(
            name="Interview Candidate",
            recruitment_id=recruitment,
            job_position_id=job_position,
            stage_id=recruitment.stage_set.get(stage_type="applied"),
            email="interview.candidate@example.com",
            mobile="9999999911",
            resume=SimpleUploadedFile(
                "interview_resume.pdf",
                b"%PDF-1.4 interview",
                content_type="application/pdf",
            ),
        )

        response = self.client.post(
            "/api/recruitment/interviews/",
            {
                "candidate": candidate.id,
                "interviewers": [self.employee.id],
                "interview_date": "2026-05-01",
                "interview_time": "10:30:00",
                "description": "Technical discussion",
            },
            format="json",
        )

        assert response.status_code == 200
        mock_send.assert_called_once()
        assert mock_send.call_args.kwargs["is_update"] is False

    @patch(
        "horilla_api.api_serializers.onboarding.serializers.OnboardingCandidateSerializer._send_candidate_interview_stage_mail"
    )
    def test_recruitment_candidate_put_status_interview_sends_stage_email(
        self, mock_send
    ):
        self.client.force_authenticate(user=self.user)
        department = Department.objects.create(department="Interview Status Department")
        job_position = JobPosition.objects.create(
            job_position="Support Engineer",
            department_id=department,
        )
        recruitment = Recruitment.objects.create(
            title="Interview Status Hiring",
            description="Hiring flow",
            is_event_based=True,
            is_published=False,
            vacancy=1,
            company_id=self.company,
        )
        recruitment.open_positions.add(job_position)
        applied_stage = recruitment.stage_set.get(stage_type="applied")
        Stage.objects.create(
            recruitment_id=recruitment,
            stage="Interview",
            stage_type="interview",
            sequence=2,
        )
        candidate = Candidate.objects.create(
            name="Status Interview Candidate",
            recruitment_id=recruitment,
            job_position_id=job_position,
            stage_id=applied_stage,
            email="status.interview@example.com",
            mobile="9999999912",
            resume=SimpleUploadedFile(
                "status_interview_resume.pdf",
                b"%PDF-1.4 status interview",
                content_type="application/pdf",
            ),
        )

        response = self.client.put(
            f"/api/recruitment/candidates/{candidate.id}/",
            {"status": "interview"},
            format="json",
        )

        assert response.status_code == 200
        mock_send.assert_called_once()

    @patch(
        "horilla_api.api_serializers.onboarding.serializers.OnboardingCandidateSerializer._send_candidate_rejection_mail"
    )
    def test_recruitment_candidate_put_status_cancelled_sends_rejection_email(
        self, mock_send
    ):
        self.client.force_authenticate(user=self.user)
        department = Department.objects.create(department="Rejected Status Department")
        job_position = JobPosition.objects.create(
            job_position="Frontend Engineer",
            department_id=department,
        )
        recruitment = Recruitment.objects.create(
            title="Rejected Status Hiring",
            description="Hiring flow",
            is_event_based=True,
            is_published=False,
            vacancy=1,
            company_id=self.company,
        )
        recruitment.open_positions.add(job_position)
        applied_stage = recruitment.stage_set.get(stage_type="applied")
        candidate = Candidate.objects.create(
            name="Rejected Candidate",
            recruitment_id=recruitment,
            job_position_id=job_position,
            stage_id=applied_stage,
            email="rejected.candidate@example.com",
            mobile="9999999913",
            resume=SimpleUploadedFile(
                "rejected_resume.pdf",
                b"%PDF-1.4 rejected",
                content_type="application/pdf",
            ),
        )

        response = self.client.put(
            f"/api/recruitment/candidates/{candidate.id}/",
            {"status": "cancelled"},
            format="json",
        )

        assert response.status_code == 200
        mock_send.assert_called_once()

    def test_onboarding_candidates_list_filters_using_hired_status(self):
        self.client.force_authenticate(user=self.user)
        department = Department.objects.create(department="Onboarding Department")
        job_position = JobPosition.objects.create(
            job_position="Onboarding Engineer",
            department_id=department,
        )
        recruitment = Recruitment.objects.create(
            title="Onboarding Hiring",
            description="Hiring for onboarding",
            is_event_based=True,
            is_published=False,
            vacancy=2,
            company_id=self.company,
        )
        recruitment.open_positions.add(job_position)
        applied_stage = recruitment.stage_set.get(stage_type="applied")
        hired_stage = Stage.objects.create(
            recruitment_id=recruitment,
            stage="Hired",
            stage_type="hired",
            sequence=3,
        )
        hired_candidate = Candidate.objects.create(
            name="Hired Candidate",
            recruitment_id=recruitment,
            job_position_id=job_position,
            stage_id=hired_stage,
            email="hired.candidate@example.com",
            mobile="9999999998",
            hired=False,
            resume=SimpleUploadedFile(
                "hired_resume.pdf",
                b"%PDF-1.4 hired",
                content_type="application/pdf",
            ),
        )
        Candidate.objects.create(
            name="Pending Candidate",
            recruitment_id=recruitment,
            job_position_id=job_position,
            stage_id=applied_stage,
            email="pending.candidate@example.com",
            mobile="9999999997",
            hired=False,
            resume=SimpleUploadedFile(
                "pending_resume.pdf",
                b"%PDF-1.4 pending",
                content_type="application/pdf",
            ),
        )

        response = self.client.get("/api/onboarding/candidates/")

        assert response.status_code == 200
        returned_ids = {row["id"] for row in response.json()}
        assert hired_candidate.id in returned_ids
        assert len(returned_ids) == 1

    def test_onboarding_candidates_list_includes_hired_candidate_without_stage(self):
        self.client.force_authenticate(user=self.user)
        department = Department.objects.create(department="Stage Null Department")
        job_position = JobPosition.objects.create(
            job_position="Stage Null Engineer",
            department_id=department,
        )
        recruitment = Recruitment.objects.create(
            title="Stage Null Hiring",
            description="Hiring for onboarding",
            is_event_based=True,
            is_published=False,
            vacancy=1,
            company_id=self.company,
        )
        recruitment.open_positions.add(job_position)
        hired_candidate = Candidate.objects.create(
            name="Stage Null Hired Candidate",
            recruitment_id=recruitment,
            job_position_id=job_position,
            stage_id=None,
            email="stage.null.hired@example.com",
            mobile="9999999996",
            hired=True,
            resume=SimpleUploadedFile(
                "stage_null_hired_resume.pdf",
                b"%PDF-1.4 stage null hired",
                content_type="application/pdf",
            ),
        )

        response = self.client.get("/api/onboarding/candidates/")

        assert response.status_code == 200
        data = response.json()
        matching = next(item for item in data if item["id"] == hired_candidate.id)
        assert matching["recruitment"] == recruitment.title
        assert matching["job_position"] == job_position.job_position
        assert matching["stage_id"] is None
        assert matching["status"] == "applied"

    def test_offboarding_stages_list_returns_stage_ids(self):
        self.client.force_authenticate(user=self.user)
        offboarding = Offboarding.objects.create(
            title="Exit Process",
            description="Standard exit workflow",
            company_id=self.company,
        )

        response = self.client.get("/api/offboarding/stages/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert "id" in data[0]
        assert "offboarding" in data[0]
        assert data[0]["offboarding"]["id"] == offboarding.id
        assert "title" in data[0]
        assert "type" in data[0]

    def test_exit_process_list_returns_exit_process_ids(self):
        self.client.force_authenticate(user=self.user)
        offboarding = Offboarding.objects.create(
            title="Exit Process",
            description="Standard exit workflow",
            company_id=self.company,
        )

        response = self.client.get("/api/offboarding/exit-process/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["id"] == offboarding.id
        assert data[0]["title"] == "Exit Process"

    def test_exit_process_get_falls_back_to_created_by_admin_manager(self):
        admin_user = User.objects.create_user(
            username="createdbyadmin",
            password="password",
            is_staff=True,
            email="createdbyadmin@example.com",
        )
        admin_employee = Employee.objects.create(
            employee_user_id=admin_user,
            employee_first_name="Created",
            employee_last_name="Admin",
            email="created-by-admin@example.com",
            phone="5555555555",
            role="admin",
        )
        self.client.force_authenticate(user=self.user)
        offboarding = Offboarding.objects.create(
            title="Exit Process",
            description="Standard exit workflow",
            company_id=self.company,
        )
        offboarding.created_by = admin_user
        offboarding.save(update_fields=["created_by"])

        response = self.client.get("/api/offboarding/exit-process/")

        assert response.status_code == 200
        matching = next(
            item for item in response.json() if item["id"] == offboarding.id
        )
        assert matching["managers"] == [
            {"id": admin_employee.id, "name": admin_employee.get_full_name()}
        ]

    def test_exit_process_create_accepts_admin_user_id_in_managers(self):
        admin_user = User.objects.create_user(
            username="offboardingadmin",
            password="password",
            is_staff=True,
        )
        admin_employee = Employee.objects.create(
            employee_user_id=admin_user,
            employee_first_name="Admin",
            employee_last_name="Manager",
            email="admin.manager@example.com",
            phone="8888888888",
            role="admin",
        )
        self.client.force_authenticate(user=admin_user)

        response = self.client.post(
            "/api/offboarding/exit-process/",
            {
                "title": "Exit Process",
                "description": "Standard exit workflow",
                "managers": [admin_user.id],
                "status": "ongoing",
                "company": self.company.id,
            },
            format="json",
        )

        assert response.status_code == 201
        data = response.json()
        assert data["managers"] == [
            {"id": admin_employee.id, "name": admin_employee.get_full_name()}
        ]

    def test_exit_process_create_resolves_admin_user_id_without_employee_profile(self):
        admin_user = User.objects.create_user(
            username="bareadmin",
            password="password",
            is_staff=True,
            email="bareadmin@example.com",
        )
        self.client.force_authenticate(user=admin_user)

        response = self.client.post(
            "/api/offboarding/exit-process/",
            {
                "title": "Exit Process",
                "description": "Standard exit workflow",
                "managers": [admin_user.id],
                "status": "ongoing",
                "company": self.company.id,
            },
            format="json",
        )

        assert response.status_code == 201
        created_employee = Employee.objects.get(employee_user_id=admin_user)
        assert created_employee.role == "admin"
        assert response.json()["managers"] == [
            {"id": created_employee.id, "name": created_employee.get_full_name()}
        ]

    def test_exit_process_create_rejects_non_admin_manager(self):
        admin_user = User.objects.create_user(
            username="validatoradmin",
            password="password",
            is_staff=True,
        )
        Employee.objects.create(
            employee_user_id=admin_user,
            employee_first_name="Validator",
            employee_last_name="Admin",
            email="validator.admin@example.com",
            phone="6666666666",
            role="admin",
        )
        self.client.force_authenticate(user=admin_user)

        response = self.client.post(
            "/api/offboarding/exit-process/",
            {
                "title": "Exit Process",
                "description": "Standard exit workflow",
                "managers": [self.employee.id],
                "status": "ongoing",
                "company": self.company.id,
            },
            format="json",
        )

        assert response.status_code == 400
        assert (
            response.json()["managers"][0]
            == f"Managers must reference admin users only. Invalid employee ids: [{self.employee.id}]"
        )

    def test_exit_process_create_ignores_legacy_manager_users_and_defaults_to_admin(self):
        admin_user = User.objects.create_user(
            username="defaultoffboardingadmin",
            password="password",
            is_staff=True,
        )
        admin_employee = Employee.objects.create(
            employee_user_id=admin_user,
            employee_first_name="Default",
            employee_last_name="Admin",
            email="default.admin@example.com",
            phone="7777777777",
            role="admin",
        )
        self.client.force_authenticate(user=admin_user)

        response = self.client.post(
            "/api/offboarding/exit-process/",
            {
                "title": "Exit Process",
                "description": "Standard exit workflow",
                "manager_users": [admin_user.id],
                "status": "ongoing",
                "company": self.company.id,
            },
            format="json",
        )

        assert response.status_code == 201
        assert response.json()["managers"] == [
            {"id": admin_employee.id, "name": admin_employee.get_full_name()}
        ]

    def test_exit_process_create_requires_admin_user(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/offboarding/exit-process/",
            {
                "title": "Exit Process",
                "description": "Standard exit workflow",
                "status": "ongoing",
                "company": self.company.id,
            },
            format="json",
        )

        assert response.status_code == 403
        assert response.json()["error"] == "Permission denied"

    def test_offboarding_stage_create_returns_connected_exit_process(self):
        admin_user = User.objects.create_user(
            username="offboardingstageadmin",
            password="password",
            is_staff=True,
            email="offboardingstageadmin@example.com",
        )
        admin_employee = Employee.objects.create(
            employee_user_id=admin_user,
            employee_first_name="Stage",
            employee_last_name="Admin",
            email="stage.admin@example.com",
            phone="7777777700",
            role="admin",
        )
        self.client.force_authenticate(user=admin_user)
        offboarding = Offboarding.objects.create(
            title="Exit Process",
            description="Standard exit workflow",
            company_id=self.company,
        )

        response = self.client.post(
            "/api/offboarding/stages/",
            {
                "offboarding": offboarding.id,
                "title": "Exit Interview",
                "type": "interview",
                "managers": [admin_user.id],
            },
            format="json",
        )

        assert response.status_code == 201
        data = response.json()
        assert data["offboarding"]["id"] == offboarding.id
        assert data["offboarding"]["title"] == "Exit Process"
        assert data["title"] == "Exit Interview"
        assert data["managers"] == [
            {"id": admin_employee.id, "name": admin_employee.get_full_name()}
        ]

    def test_offboarding_employee_create_accepts_user_id_in_employee_field(self):
        self.client.force_authenticate(user=self.user)
        offboarding = Offboarding.objects.create(
            title="Exit Process",
            description="Standard exit workflow",
            company_id=self.company,
        )
        User.objects.create_user(username="padding1", password="password")
        User.objects.create_user(username="padding2", password="password")
        target_user = User.objects.create_user(
            username="offboardtarget",
            password="password",
            email="offboardtarget@example.com",
        )
        target_employee = Employee.objects.create(
            employee_user_id=target_user,
            employee_first_name="Target",
            employee_last_name="Employee",
            email="target.employee@example.com",
            phone="8888888800",
        )

        response = self.client.post(
            "/api/offboarding/employees/",
            {
                "employee": target_user.id,
                "offboarding": offboarding.id,
                "notice_period_starts": "2026-04-22",
                "notice_period_ends": "2026-05-22",
            },
            format="json",
        )

        assert response.status_code == 201
        assert response.json()["employee"] == {
            "id": target_employee.id,
            "name": target_employee.get_full_name(),
        }

    def test_offboarding_stages_list_can_filter_by_exit_process(self):
        self.client.force_authenticate(user=self.user)
        first_offboarding = Offboarding.objects.create(
            title="Exit Process One",
            description="Standard exit workflow",
            company_id=self.company,
        )
        second_offboarding = Offboarding.objects.create(
            title="Exit Process Two",
            description="Another exit workflow",
            company_id=self.company,
        )

        response = self.client.get(
            f"/api/offboarding/stages/?offboarding={second_offboarding.id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert all(
            stage["offboarding"]["id"] == second_offboarding.id for stage in data
        )
        assert all(
            stage["offboarding"]["id"] != first_offboarding.id for stage in data
        )

    def test_resignation_request_create_returns_expected_shape(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/offboarding/resignation-requests/",
            {
                "employee": self.employee.id,
                "title": "Personal Resignation",
                "description": "I want to resign for personal reasons.",
                "planned_to_leave_on": "2026-04-15",
                "status": "requested",
            },
            format="json",
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["employee"]["id"] == self.employee.id
        assert data["title"] == "Personal Resignation"
        assert data["description"] == "I want to resign for personal reasons."
        assert data["planned_to_leave_on"] == "2026-04-15"
        assert data["status"] == "Requested"
        assert ResignationLetter.objects.filter(employee_id=self.employee).exists()

    def test_resignation_request_create_accepts_user_id_in_employee_field(self):
        self.client.force_authenticate(user=self.user)
        User.objects.create_user(username="resignpad1", password="password")
        User.objects.create_user(username="resignpad2", password="password")
        target_user = User.objects.create_user(
            username="resigntarget",
            password="password",
            email="resigntarget@example.com",
        )
        target_employee = Employee.objects.create(
            employee_user_id=target_user,
            employee_first_name="Resign",
            employee_last_name="Target",
            email="resign.target@example.com",
            phone="7777777711",
        )

        response = self.client.post(
            "/api/offboarding/resignation-requests/",
            {
                "employee": target_user.id,
                "title": "Personal Resignation",
                "description": "I want to resign for personal reasons.",
                "planned_to_leave_on": "2026-04-15",
                "status": "requested",
            },
            format="json",
        )

        assert response.status_code == 201
        assert response.json()["employee"] == {
            "id": target_employee.id,
            "name": target_employee.get_full_name(),
        }

    def test_exit_process_lists_employees_created_from_multiple_resignation_requests(self):
        self.client.force_authenticate(user=self.user)
        target_user = User.objects.create_user(
            username="secondresignee",
            password="password",
            email="secondresignee@example.com",
        )
        target_employee = Employee.objects.create(
            employee_user_id=target_user,
            employee_first_name="Second",
            employee_last_name="Resignee",
            email="second.resignee@example.com",
            phone="7777777722",
        )

        first_response = self.client.post(
            "/api/offboarding/resignation-requests/",
            {
                "employee": self.user.id,
                "title": "First Resignation",
                "description": "First employee resignation.",
                "planned_to_leave_on": "2026-04-15",
                "status": "requested",
            },
            format="json",
        )
        second_response = self.client.post(
            "/api/offboarding/resignation-requests/",
            {
                "employee": target_user.id,
                "title": "Second Resignation",
                "description": "Second employee resignation.",
                "planned_to_leave_on": "2026-04-16",
                "status": "requested",
            },
            format="json",
        )

        assert first_response.status_code == 201
        assert second_response.status_code == 201

        response = self.client.get("/api/offboarding/exit-process/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Exit Process"

        employee_ids = {
            row["employee"]["id"]
            for row in data[0]["employees"]
            if row.get("employee") is not None
        }
        assert employee_ids == {self.employee.id, target_employee.id}

    def test_survey_template_create_falls_back_when_company_pk_is_invalid(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/recruitment/survey-templates/",
            {
                "title": "API Survey Template",
                "description": "Created through API",
                "company": 999,
            },
            format="json",
        )

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["title"] == "API Survey Template"
        assert data["company"]["id"] == self.company.id
        assert SurveyTemplate.objects.filter(
            title="API Survey Template", company_id=self.company
        ).exists()
