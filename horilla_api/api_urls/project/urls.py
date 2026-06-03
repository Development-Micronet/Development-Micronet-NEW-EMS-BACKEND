from django.urls import path

from project import views

urlpatterns = [
    # Example: expose existing endpoints from project/views.py
    path(
        "projects-new/create/",
        views.ProjectNewCreateAPIView.as_view(),
        name="project-new-create",
    ),
    path("project-dashboard-view", views.dashboard_view, name="project-dashboard-view"),
    path(
        "projects-due-in-this-month",
        views.dashboard.ProjectsDueInMonth.as_view(),
        name="projects-due-in-this-month",
    ),
    path(
        "project-status-chart", views.project_status_chart, name="project-status-chart"
    ),
    path("task-status-chart", views.task_status_chart, name="task-status-chart"),
    path(
        "project-detailed-view/<int:pk>/",
        views.dashboard.ProjectDetailView.as_view(),
        name="project-detailed-view",
    ),
    path(
        "project-nav-view/",
        views.projects.ProjectsNavView.as_view(),
        name="project-nav-view",
    ),
]
