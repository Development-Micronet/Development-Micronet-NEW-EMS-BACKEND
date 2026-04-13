from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from employee.models import Employee
from notifications.models import Notification
from performance.models import Feedback, Question, QuestionTemplate


class PerformanceNotificationAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.admin_user = User.objects.create_user(
            username="performance_admin",
            password="password",
        )
        self.admin_employee = Employee.objects.create(
            employee_user_id=self.admin_user,
            employee_first_name="Asha",
            employee_last_name="Admin",
            email="asha.admin@example.com",
            phone="9999999001",
            role="admin",
        )

        self.employee_user = User.objects.create_user(
            username="performance_employee",
            password="password",
        )
        self.employee = Employee.objects.create(
            employee_user_id=self.employee_user,
            employee_first_name="Ravi",
            employee_last_name="Employee",
            email="ravi.employee@example.com",
            phone="9999999002",
        )

        self.manager_user = User.objects.create_user(
            username="performance_manager",
            password="password",
        )
        self.manager = Employee.objects.create(
            employee_user_id=self.manager_user,
            employee_first_name="Meera",
            employee_last_name="Manager",
            email="meera.manager@example.com",
            phone="9999999003",
        )

        self.question_template = QuestionTemplate.objects.create(name="Quarterly Review")
        self.question = Question.objects.create(
            template=self.question_template,
            question="How was your quarter?",
            answer_type="text",
        )

    def test_create_objective_notifies_employee_and_manager(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(
            "/api/performance/objectives/",
            {
                "employee": self.employee.id,
                "title": "Q2 Growth Plan",
                "objective": "productivity_metrics",
                "description": "Improve delivery throughput",
                "start_date": date.today().isoformat(),
                "end_date": (date.today() + timedelta(days=30)).isoformat(),
                "status": "not_started",
                "managers": [self.manager.id],
            },
            format="json",
        )

        assert response.status_code == 201, response.content
        assert Notification.objects.filter(
            recipient=self.employee_user,
            verb__icontains="objective",
        ).exists()
        assert Notification.objects.filter(
            recipient=self.manager_user,
            verb__icontains="manage the objective",
        ).exists()

    def test_feedback_create_and_submit_send_notifications(self):
        self.client.force_authenticate(user=self.admin_user)

        create_response = self.client.post(
            "/api/performance/feedbacks/",
            {
                "title": "Q2 360 Feedback",
                "employee": self.employee.id,
                "start_date": date.today().isoformat(),
                "end_date": (date.today() + timedelta(days=7)).isoformat(),
                "question_template": self.question_template.id,
                "status": "not_started",
            },
            format="json",
        )

        assert create_response.status_code == 201, create_response.content
        feedback = Feedback.objects.get(id=create_response.json()["data"]["id"])

        assert Notification.objects.filter(
            recipient=self.employee_user,
            verb__icontains="feedback",
        ).exists()

        self.client.force_authenticate(user=self.employee_user)
        submit_response = self.client.post(
            "/api/performance/feedback/submit/",
            {
                "feedback_id": feedback.id,
                "answers": [
                    {
                        "question_id": self.question.id,
                        "answer_text": "It went well.",
                    }
                ],
            },
            format="json",
        )

        assert submit_response.status_code == 201, submit_response.content
        assert Notification.objects.filter(
            recipient=self.admin_user,
            verb__icontains="submitted",
        ).exists()
