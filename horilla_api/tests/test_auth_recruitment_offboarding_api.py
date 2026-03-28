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

    def test_offboarding_stage_create_returns_connected_exit_process(self):
        self.client.force_authenticate(user=self.user)
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
                "managers": [self.employee.id],
            },
            format="json",
        )

        assert response.status_code == 201
        data = response.json()
        assert data["offboarding"]["id"] == offboarding.id
        assert data["offboarding"]["title"] == "Exit Process"
        assert data["title"] == "Exit Interview"

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
