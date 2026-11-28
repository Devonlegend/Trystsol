from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("projects/", views.ProjectListCreateView.as_view(), name="list-create"),
    path("projects/<slug:slug>/", views.ProjectDetailView.as_view(), name="detail"),
    path("projects/<uuid:project_id>/submit/", views.ProjectSubmitView.as_view(), name="submit"),
    path("projects/<uuid:project_id>/decision/", views.ProjectDecisionView.as_view(), name="decision"),
    path("admin/projects/", views.AdminProjectListView.as_view(), name="admin-list"),
    path("founders/me/", views.FounderProfileView.as_view(), name="founder-profile"),
    path("founders/projects/", views.FounderProjectListView.as_view(), name="founder-projects"),
    path("projects/<uuid:project_id>/manage/", views.ManageProjectView.as_view(), name="manage"),
    path("projects/<uuid:project_id>/token/", views.ProjectTokenView.as_view(), name="token"),
]
