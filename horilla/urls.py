"""horilla URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

from horilla_api.api_views.employee import views as employee_views
from horilla_api.api_views.auth.views import ResetPasswordPageView
from leave import views as leave_views

from . import settings


def health_check(request):
    return JsonResponse({"status": "ok"}, status=200)


# Swagger Schema Configuration
schema_view = get_schema_view(
    openapi.Info(
        title="Horilla EMS API",
        default_version="v1",
        description="Horilla Employee Management System REST API Documentation",
        terms_of_service="https://www.example.com/terms/",
        contact=openapi.Contact(email="contact@example.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # Django Admin
    path("admin/", admin.site.urls),
    # Swagger/OpenAPI Documentation
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    path("api-schema/", schema_view.without_ui(cache_timeout=0), name="schema-json"),
    # API endpoints
    path("api/", include("horilla_api.urls")),
    # path("api/project/", include("project.urls_api")),  # Using views.py instead
    path(
        "auth/", include("horilla_api.api_urls.auth.urls")
    ),  # Shortcut for authentication
    path(
        "auth/reset-password/<str:uid>/<str:token>/",
        ResetPasswordPageView.as_view(),
        name="auth-reset-password-page",
    ),
    path(
        "employees/",
        employee_views.EmployeeListAPIView.as_view(),
        name="employees-list",
    ),  # Direct shortcut
    path("health/", health_check),
    path("api/recruitment/", include("horilla_api.api_urls.recruitment.urls")),
    path("api/leave/", include("leave.urls")),
    path("api/performance/", include("performance.urls")),  # Employee API endpoints
    path("api/pms/", include("pms.urls")),  # Employee API endpoints
    path("api/project/", include("project.urls")),  # Employee API endpoints
    path(
        "api/employee/assign-rotating-work-type/",
        leave_views.assign_rotating_work_type,
        name="assign-rotating-work-type",
    ),
    path(
        "api/employee/assign-rotating-work-type/get/",
        leave_views.get_rotating_work_type,
        name="get-rotating-work-type",
    ),
    path(
        "api/employee/assign-rotating-work-type/<int:assignment_id>/",
        leave_views.update_rotating_work_type,
        name="update-rotating-work-type",
    ),
    path(
        "api/employee/assign-rotating-work-type/<int:assignment_id>/delete/",
        leave_views.delete_rotating_work_type,
        name="delete-rotating-work-type",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
