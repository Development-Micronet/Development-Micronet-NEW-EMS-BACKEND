"""
apps.py
"""

from django.apps import AppConfig


class EmployeeConfig(AppConfig):
    """
    AppConfig for the 'employee' app.

    This class represents the configuration for the 'employee' app. It provides
    the necessary settings and metadata for the app.

    Attributes:
        default_auto_field (str): The default auto field to use for model field IDs.
        name (str): The name of the app.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "employee"

    def ready(self):
        """
        This method is called when the app is ready.
        Import signals here to ensure they are connected.
        """
        import employee.models  # noqa

