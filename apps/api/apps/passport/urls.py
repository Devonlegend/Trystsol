from django.urls import path

from . import views

app_name = "passport"

urlpatterns = [
    path("passport/<uuid:user_id>/", views.BuilderPassportView.as_view(), name="builder"),
]
