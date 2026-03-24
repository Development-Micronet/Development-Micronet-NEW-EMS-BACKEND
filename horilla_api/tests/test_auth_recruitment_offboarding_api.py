from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import resolve
from rest_framework.test import APIClient

from base.models import Company
from employee.models import Employee
from horilla.horilla_middlewares import _thread_locals
from offboarding.models import Offboarding, ResignationLetter
from recruitment.models import SurveyTemplate


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

    def test_recruitment_interviews_url_resolves_to_new_api_view(self):
        match = resolve("/api/recruitment/interviews/")
        assert match.func.view_class.__name__ == "RecruitmentInterviewAPIView"

    def test_offboarding_stages_list_returns_stage_ids(self):
        self.client.force_authenticate(user=self.user)
        Offboarding.objects.create(
            title="Exit Process",
            description="Standard exit workflow",
            company_id=self.company,
        )

        response = self.client.get("/api/offboarding/stages/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert "id" in data[0]
        assert "title" in data[0]
        assert "type" in data[0]

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
        assert data["employee"]["id"] == self.employee.id
        assert data["title"] == "Personal Resignation"
        assert data["description"] == "I want to resign for personal reasons."
        assert data["planned_to_leave_on"] == "2026-04-15"
        assert data["status"] == "Requested"
        assert ResignationLetter.objects.filter(employee_id=self.employee).exists()

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
