from django.urls import path

from .views import (
    CandidateAPIView,
    CandidateSkillAPIView,
    InterviewAPIView,
    SkillZoneAPIView,
)

urlpatterns = [
    path("candidates/", CandidateAPIView.as_view(), name="candidate-list"),
    path("candidates/<int:pk>/", CandidateAPIView.as_view()),
    path("interviews/", InterviewAPIView.as_view()),
    path("interviews/<int:pk>/", InterviewAPIView.as_view()),
    path("skills/", SkillZoneAPIView.as_view()),
    path("skills/<int:pk>/", SkillZoneAPIView.as_view()),
    # Candidate Skill
    path("candidate-skills/", CandidateSkillAPIView.as_view()),
    path("candidate-skills/<int:pk>/", CandidateSkillAPIView.as_view()),
]
