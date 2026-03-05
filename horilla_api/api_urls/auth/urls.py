from django.urls import path

from ...api_views.auth.views import (
    ForgotPasswordAPIView,
    LoginAPIView,
    ResetPasswordAPIView,
)

urlpatterns = [
    path("login/", LoginAPIView.as_view()),
    path("forgot-password/", ForgotPasswordAPIView.as_view()),
    path("reset-password/", ResetPasswordAPIView.as_view()),
]
