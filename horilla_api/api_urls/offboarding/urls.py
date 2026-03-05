from django.urls import path

from horilla_api.api_views.offboarding.views import (
    ExitProcessAPIView,
    OffboardingAPIView,
    OffboardingEmployeeAPIView,
    OffboardingStageAPIView,
)

urlpatterns = [
    path(
        "exit-process/",
        ExitProcessAPIView.as_view(),
        name="offboarding-exit-process-list",
    ),
    path(
        "exit-process/<int:pk>/",
        ExitProcessAPIView.as_view(),
        name="offboarding-exit-process-detail",
    ),
    path(
        "employees/",
        OffboardingEmployeeAPIView.as_view(),
        name="offboarding-employee-list",
    ),
    path(
        "employees/<int:pk>/",
        OffboardingEmployeeAPIView.as_view(),
        name="offboarding-employee-detail",
    ),
    path(
        "offboarding/",
        OffboardingAPIView.as_view(),
        name="offboarding-manager-status-list",
    ),
    path(
        "offboarding/<int:pk>/",
        OffboardingAPIView.as_view(),
        name="offboarding-manager-status-detail",
    ),
    path("stages/", OffboardingStageAPIView.as_view(), name="offboarding-stage-list"),
    path(
        "stages/<int:pk>/",
        OffboardingStageAPIView.as_view(),
        name="offboarding-stage-detail",
    ),
]
