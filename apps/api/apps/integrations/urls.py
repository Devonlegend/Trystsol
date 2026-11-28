from django.urls import path

from . import views

app_name = "integrations"

urlpatterns = [
    path("github/challenge/", views.GitHubChallengeView.as_view(), name="github-challenge"),
    path("github/verify/", views.GitHubVerifyView.as_view(), name="github-verify"),
    path("github/<uuid:project_id>/", views.GitHubStatusView.as_view(), name="github-status"),
]
