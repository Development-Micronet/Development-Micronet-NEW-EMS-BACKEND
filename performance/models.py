from django.db import models

from employee.models import Employee


# ==========================
# OBJECTIVE
# ==========================
class Objective(models.Model):
    OBJECTIVE_CHOICES = [
        ("employee_engagement", "Employee Engagement"),
        ("productivity_metrics", "Productivity Metrics"),
        ("increase_sales", "Increase Sales"),
    ]

    STATUS_CHOICES = [
        ("not_started", "Not Started"),
        ("on_track", "On Track"),
        ("behind", "Behind"),
        ("closed", "Closed"),
    ]

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="objectives"
    )
    title = models.CharField(max_length=200)
    objective = models.CharField(max_length=50, choices=OBJECTIVE_CHOICES)
    description = models.TextField(null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="not_started"
    )

    managers = models.ManyToManyField(
        Employee, related_name="managed_objectives", blank=True
    )

    class Meta:
        db_table = "employee_objective"

    def __str__(self):
        return self.title


# ==========================
# KEY RESULT
# ==========================
class KeyResult(models.Model):
    PROGRESS_CHOICES = [
        ("percentage", "Percentage"),
        ("number", "Number"),
        ("usd", "USD"),
        ("inr", "INR"),
        ("eur", "EUR"),
    ]

    title = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField()
    progress_type = models.CharField(
        max_length=20, choices=PROGRESS_CHOICES, default="percentage"
    )
    target_value = models.FloatField(null=True, blank=True)
    duration = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "employee_keyresult"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


# ==========================
# QUESTION TEMPLATE
# ==========================
class QuestionTemplate(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class Question(models.Model):
    ANSWER_TYPES = [
        ("text", "Text"),
        ("mcq", "MCQ"),
        ("boolean", "Boolean"),
        ("rating", "Rating"),
    ]

    template = models.ForeignKey(
        QuestionTemplate, on_delete=models.CASCADE, related_name="questions"
    )
    question = models.TextField()
    answer_type = models.CharField(max_length=20, choices=ANSWER_TYPES)

    class Meta:
        db_table = "employee_question"

    def __str__(self):
        return self.question


# ==========================
# MEETING
# ==========================
class Meeting(models.Model):
    title = models.CharField(max_length=200)
    date = models.DateField()

    employees = models.ManyToManyField(
        Employee, related_name="meeting_employees", blank=True
    )

    manager = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_meetings",
    )

    answerable_employees = models.ManyToManyField(
        Employee, related_name="meeting_answerables", blank=True
    )

    question_template = models.ForeignKey(
        QuestionTemplate, on_delete=models.SET_NULL, null=True, blank=True
    )

    mom = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "employee_meeting"

    def __str__(self):
        return self.title


# ==========================
# feed back
# ==========================


class Feedback(models.Model):

    STATUS_CHOICES = [
        ("not_started", "Not Started"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("closed", "Closed"),
    ]

    title = models.CharField(max_length=200)

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="performance_feedbacks"
    )

    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    question_template = models.ForeignKey(
        QuestionTemplate, on_delete=models.SET_NULL, null=True, blank=True
    )

    key_result = models.ForeignKey(
        KeyResult, on_delete=models.SET_NULL, null=True, blank=True
    )

    colleagues = models.ManyToManyField(
        Employee, related_name="feedback360_colleagues", blank=True
    )
    subordinates = models.ManyToManyField(
        Employee, related_name="feedback360_subordinates", blank=True
    )

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="not_started"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "employee_feedback360"

    def __str__(self):
        return self.title


from employee.models import Employee


#### employee feedback answer
class FeedbackAnswer(models.Model):
    feedback = models.ForeignKey(
        "Feedback", on_delete=models.CASCADE, related_name="answers"
    )

    question = models.ForeignKey(Question, on_delete=models.CASCADE)

    answered_by = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="submitted_feedback_answers"
    )

    answer_text = models.TextField(null=True, blank=True)
    answer_boolean = models.BooleanField(null=True, blank=True)
    answer_rating = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.feedback.title} - {self.question.id}"


from employee.models import Employee


class NewBonusEmployee(models.Model):

    BONUS_CATEGORY_CHOICES = [
        ("performance", "Performance"),
        ("attendance", "Attendance"),
        ("referral", "Referral"),
        ("project", "Project Completion"),
    ]

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="new_bonus_records"
    )

    bonus_points = models.IntegerField()
    bonus_category = models.CharField(max_length=50, choices=BONUS_CATEGORY_CHOICES)

    reason = models.TextField(null=True, blank=True)

    awarded_date = models.DateField(auto_now_add=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.bonus_points}"
