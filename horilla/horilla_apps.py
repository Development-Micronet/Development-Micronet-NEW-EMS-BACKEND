"""
horilla_apps

This module is used to register horilla addons
"""

from horilla import settings
from horilla.settings import INSTALLED_APPS

def append_app(app_name):
    if app_name not in INSTALLED_APPS:
        INSTALLED_APPS.append(app_name)


append_app("accessibility")
append_app("horilla_audit")
append_app("horilla_widgets")
append_app("horilla_crumbs")
append_app("horilla_documents")
append_app("horilla_views")
append_app("horilla_automations")
append_app("auditlog")
append_app("biometric")
append_app("helpdesk")
append_app("offboarding")
append_app("horilla_backup")
append_app("project")
if settings.env("AWS_ACCESS_KEY_ID", default=None) and "storages" not in INSTALLED_APPS:
    INSTALLED_APPS.append("storages")


AUDITLOG_INCLUDE_ALL_MODELS = True

AUDITLOG_EXCLUDE_TRACKING_MODELS = (
    # "<app_name>",
    # "<app_name>.<model>"
)

setattr(settings, "AUDITLOG_INCLUDE_ALL_MODELS", AUDITLOG_INCLUDE_ALL_MODELS)
setattr(settings, "AUDITLOG_EXCLUDE_TRACKING_MODELS", AUDITLOG_EXCLUDE_TRACKING_MODELS)

settings.MIDDLEWARE.append(
    "auditlog.middleware.AuditlogMiddleware",
)

SETTINGS_EMAIL_BACKEND = getattr(settings, "EMAIL_BACKEND", False)
setattr(settings, "EMAIL_BACKEND", "base.backends.ConfiguredEmailBackend")
if SETTINGS_EMAIL_BACKEND:
    setattr(settings, "EMAIL_BACKEND", SETTINGS_EMAIL_BACKEND)


SIDEBARS = [
    "recruitment",
    "onboarding",
    "employee",
    "attendance",
    "leave",
    "payroll",
    "pms",
    "offboarding",
    "asset",
    "helpdesk",
    "project",
]

WHITE_LABELLING = False
NESTED_SUBORDINATE_VISIBILITY = False
TWO_FACTORS_AUTHENTICATION = False
