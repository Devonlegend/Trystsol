from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("nonce/", views.NonceView.as_view(), name="nonce"),
    path("verify/", views.VerifyView.as_view(), name="verify"),
    path("refresh/", views.RefreshView.as_view(), name="refresh"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("me/", views.MeView.as_view(), name="me"),
    path("me/role/<uuid:user_id>/", views.SetRoleView.as_view(), name="set-role"),
]
