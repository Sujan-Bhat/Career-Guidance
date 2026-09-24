"""Root URL configuration: all apps under /api/v1/."""
from django.urls import include, path

urlpatterns = [
    path("api/v1/accounts/", include("apps.accounts.urls")),
    path("api/v1/collector/", include("apps.collector.urls")),
    path("api/v1/fes/", include("apps.fes.urls")),
    path("api/v1/courses/", include("apps.courses.urls")),
    path("api/v1/careers/", include("apps.careers.urls")),
    path("api/v1/recommendations/", include("apps.recommendations.urls")),
    path("api/v1/rl/", include("apps.rl_feedback.urls")),
    path("api/v1/llm/", include("apps.llm_proxy.urls")),
]
