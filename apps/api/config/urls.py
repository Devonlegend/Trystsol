from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

from apps.common.views import HealthView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/", include("apps.projects.urls")),
    path("api/", include("apps.milestones.urls")),
    path("api/", include("apps.reviews.urls")),
    path("api/chain/", include("apps.chain.urls")),
    path("api/integrations/", include("apps.integrations.urls")),
    path("api/", include("apps.decision_pages.urls")),
    path("api/", include("apps.passport.urls")),
    path("api/health/", HealthView.as_view(), name="health"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
]
