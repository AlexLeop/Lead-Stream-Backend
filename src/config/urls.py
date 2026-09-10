from __future__ import annotations

from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path("health/", include("leadstream.common.urls")),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/v1/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/v1/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    path("api/v1/", include("leadstream.tenancy.urls")),
    path("api/v1/dados/", include("leadstream.entities.urls")),
    path("api/v1/dados/", include("leadstream.evidence.urls")),
    path("api/v1/dados/", include("leadstream.governance.urls")),
    path("api/v1/lotes/", include("leadstream.batches.urls")),
    path("api/v1/", include("leadstream.billing.urls")),
    path("api/v1/", include("leadstream.providers.urls")),
]
