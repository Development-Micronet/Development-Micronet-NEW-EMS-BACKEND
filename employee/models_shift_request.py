from django.db import models

from employee.models import Employee


class ShiftRequest(models.Model):
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="shift_requests"
    )
    shift_name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    date = models.DateField()
    reason = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, default="requested")

    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.shift_name} ({self.date})"
