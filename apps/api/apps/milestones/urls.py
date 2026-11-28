from django.urls import path

from . import views

app_name = "milestones"

urlpatterns = [
    path("projects/<uuid:project_id>/milestones/", views.MilestoneCreateView.as_view(), name="create"),
    path("projects/<uuid:project_id>/roadmaps/", views.RoadmapCreateView.as_view(), name="roadmap-create"),
    path("roadmaps/<uuid:roadmap_id>/", views.RoadmapUpdateView.as_view(), name="roadmap-update"),
    path("milestones/<uuid:milestone_id>/assign/", views.AssignReviewersView.as_view(), name="assign"),
    path("milestones/<uuid:milestone_id>/submit/", views.SubmitMilestoneView.as_view(), name="submit"),
    path("milestones/<uuid:milestone_id>/expire/", views.MilestoneExpireView.as_view(), name="expire"),
    path("criteria/", views.CriteriaListCreateView.as_view(), name="criteria"),
    path("admin/criteria/", views.CriteriaListCreateView.as_view(), name="admin-criteria"),
]
