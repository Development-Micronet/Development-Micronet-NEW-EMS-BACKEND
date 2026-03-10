from django.urls import path

from horilla_api.api_views.recruitment.views import (
    RecruitmentCandidateAPIView,
    RecruitmentInterviewAPIView,
    RecruitmentPipelineAPIView,
    RecruitmentStageAPIView,
    RecruitmentSurveyQuestionAPIView,
    RecruitmentSurveyTemplateAPIView,
)

urlpatterns = [
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
]
