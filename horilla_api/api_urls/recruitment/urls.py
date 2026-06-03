from django.urls import include, path
from rest_framework.routers import DefaultRouter

from recruitment.api_apply_now import ApplyNowViewSet
from horilla_api.api_views.recruitment.views import (
    RecruitmentCarrersAPIView,
    RecruitmentCandidateAPIView,
    RecruitmentInterviewAPIView,
    RecruitmentPipelineAPIView,
    RecruitmentSkillZoneCandidateAPIView,
    RecruitmentSkillZoneAPIView,
    RecruitmentStageAPIView,
    RecruitmentSurveyQuestionAPIView,
    RecruitmentSurveyTemplateAPIView,
)

router = DefaultRouter()
router.register(r'apply-now', ApplyNowViewSet, basename='apply-now')

urlpatterns = [
    path("", include(router.urls)),
    path("candidates/", RecruitmentCandidateAPIView.as_view(), name="recruitment-candidate-list"),
    path(
        "candidates/<int:pk>/",
        RecruitmentCandidateAPIView.as_view(),
        name="recruitment-candidate-detail",
    ),
    path("interviews/", RecruitmentInterviewAPIView.as_view(), name="recruitment-interview-list"),
    path(
        "interviews/<int:pk>/",
        RecruitmentInterviewAPIView.as_view(),
        name="recruitment-interview-detail",
    ),
    path("pipeline/", RecruitmentPipelineAPIView.as_view(), name="recruitment-pipeline-list"),
    path(
        "pipeline/<int:pk>/",
        RecruitmentPipelineAPIView.as_view(),
        name="recruitment-pipeline-detail",
    ),
    path(
        "recruitment-view/",
        RecruitmentPipelineAPIView.as_view(),
        name="recruitment-view-list",
    ),
    path(
        "recruitment-carrers/",
        RecruitmentCarrersAPIView.as_view(),
        name="recruitment-carrer-list",
    ),
    path(
        "recruitment-view/<int:pk>/",
        RecruitmentPipelineAPIView.as_view(),
        name="recruitment-view-detail",
    ),
    path(
        "stage-view/",
        RecruitmentStageAPIView.as_view(),
        name="recruitment-stage-view-list",
    ),
    path(
        "stage-view/<int:pk>/",
        RecruitmentStageAPIView.as_view(),
        name="recruitment-stage-view-detail",
    ),
    path(
        "survey-templates/",
        RecruitmentSurveyTemplateAPIView.as_view(),
        name="recruitment-survey-template-list",
    ),
    path(
        "survey-templates/<int:pk>/",
        RecruitmentSurveyTemplateAPIView.as_view(),
        name="recruitment-survey-template-detail",
    ),
    path(
        "survey-questions/",
        RecruitmentSurveyQuestionAPIView.as_view(),
        name="recruitment-survey-question-list",
    ),
    path(
        "survey-questions/<int:pk>/",
        RecruitmentSurveyQuestionAPIView.as_view(),
        name="recruitment-survey-question-detail",
    ),
    path(
        "skill-zones/",
        RecruitmentSkillZoneAPIView.as_view(),
        name="recruitment-skill-zone-list",
    ),
    path(
        "skill-zones/<int:pk>/",
        RecruitmentSkillZoneAPIView.as_view(),
        name="recruitment-skill-zone-detail",
    ),
    path(
        "skill-zone-candidates/",
        RecruitmentSkillZoneCandidateAPIView.as_view(),
        name="recruitment-skill-zone-candidate-list",
    ),
    path(
        "skill-zone-candidates/<int:pk>/",
        RecruitmentSkillZoneCandidateAPIView.as_view(),
        name="recruitment-skill-zone-candidate-detail",
    ),
]
