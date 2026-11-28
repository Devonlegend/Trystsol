from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path("admin/reviewers/", views.ReviewerRegistryView.as_view(), name="registry"),
    path("admin/reviewers/<uuid:reviewer_id>/deactivate/", views.ReviewerDeactivateView.as_view(), name="deactivate"),
    path("milestones/<uuid:milestone_id>/review/", views.MilestoneReviewView.as_view(), name="review"),
    path("reviewer/assignments/", views.ReviewerAssignmentsView.as_view(), name="assignments"),
    path("reviews/<uuid:review_id>/disputes/", views.FileDisputeView.as_view(), name="file-dispute"),
    path("disputes/<uuid:dispute_id>/resolve/", views.ResolveDisputeView.as_view(), name="resolve-dispute"),
    path("admin/disputes/", views.AdminDisputeListView.as_view(), name="admin-disputes"),
]
