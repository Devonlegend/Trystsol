from django.urls import path

from . import views

app_name = "decision_pages"

urlpatterns = [
    path("decision/projects/<slug:slug>/", views.ProjectDecisionView.as_view(), name="project"),
    path("decision/tokens/<str:mint>/", views.TokenDecisionView.as_view(), name="token"),
]
