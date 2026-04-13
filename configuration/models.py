from django.db import models

class Holiday(models.Model):
    name = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()
    company = models.CharField(max_length=255)
    recurring = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class CompanyLeave(models.Model):
    WEEK_CHOICES = [
        ("ALL", "All"),
        ("FIRST", "First Week"),
        ("SECOND", "Second Week"),
        ("THIRD", "Third Week"),
        ("FOURTH", "Fourth Week"),
        ("FIFTH", "Fifth Week"),
    ]
    WEEKDAY_CHOICES = [
        ("MONDAY", "Monday"),
        ("TUESDAY", "Tuesday"),
        ("WEDNESDAY", "Wednesday"),
        ("THURSDAY", "Thursday"),
        ("FRIDAY", "Friday"),
        ("SATURDAY", "Saturday"),
        ("SUNDAY", "Sunday"),
    ]
    based_on_week = models.CharField(max_length=10, choices=WEEK_CHOICES)
    based_on_week_day = models.CharField(max_length=10, choices=WEEKDAY_CHOICES)
    company = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.company} - {self.based_on_week} - {self.based_on_week_day}"
