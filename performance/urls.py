from django.urls import path

from .views import (
    AdminFeedbackAPIView,
    FeedbackAPIView,
    KeyResultAPIView,
    MeetingAPIView,
    MyAssignedFeedbackAPIView,
    NewBonusEmployeeAPIView,
    ObjectiveAPIView,
    QuestionAPIView,
    QuestionTemplateAPIView,
    SubmitFeedbackAPIView,
)

urlpatterns = [
    # ======================
    # OBJECTIVE
    # ======================
    path("objectives/", ObjectiveAPIView.as_view()),
    path("objectives/<int:pk>/", ObjectiveAPIView.as_view()),
    # ======================
    # KEY RESULT
    # ======================
    path("key-results/", KeyResultAPIView.as_view()),
    path("key-results/<int:pk>/", KeyResultAPIView.as_view()),
    # ======================
    # MEETING
    # ======================
    path("meetings/", MeetingAPIView.as_view()),
    path("meetings/<int:pk>/", MeetingAPIView.as_view()),
    # ======================
    # QUESTION TEMPLATE
    # ======================
    path("question-templates/", QuestionTemplateAPIView.as_view()),
    path("question-templates/<int:pk>/", QuestionTemplateAPIView.as_view()),
    # ======================
    # QUESTIONS
    # ======================
    path("questions/", QuestionAPIView.as_view()),
    path("questions/<int:pk>/", QuestionAPIView.as_view()),
    # dam feedback
    path("feedbacks/", FeedbackAPIView.as_view()),
    path("feedbacks/<int:pk>/", FeedbackAPIView.as_view()),
    path("feedback/admin/", AdminFeedbackAPIView.as_view()),
    path("feedback/admin/<int:pk>/", AdminFeedbackAPIView.as_view()),
    # employee feed back
    path("feedback/my/", MyAssignedFeedbackAPIView.as_view()),
    path("feedback/submit/", SubmitFeedbackAPIView.as_view()),
    # bonus here ###
    path("bonus/", NewBonusEmployeeAPIView.as_view()),
    path("bonus/<int:pk>/", NewBonusEmployeeAPIView.as_view()),
]
