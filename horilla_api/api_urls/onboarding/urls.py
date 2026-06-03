from django.urls import path

from horilla_api.api_views.onboarding.views import OnboardingCandidateAPIView

urlpatterns = [
    path(
        "candidates/",
        OnboardingCandidateAPIView.as_view(),
        name="onboarding-candidates",
    ),
    path(
        "candidates/<int:pk>/",
        OnboardingCandidateAPIView.as_view(),
        name="onboarding-candidate-detail",
    ),
]
