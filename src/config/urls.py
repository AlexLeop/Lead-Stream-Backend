from __future__ import annotations

from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from leadstream.batches.views import ExportDetailView, ExportDownloadView
from leadstream.common.views import ScalarDocsView

urlpatterns = [
    path("health/", include("leadstream.common.urls")),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/v1/docs/",
        ScalarDocsView.as_view(),
        name="scalar-docs",
    ),
    path(
        "api/v1/swagger/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/v1/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    path("api/v1/", include("leadstream.security.urls")),
    path("api/v1/", include("leadstream.tenancy.urls")),
    path("api/v1/", include("leadstream.governance.urls")),
    path("api/v1/", include("leadstream.batches.admin_urls")),
    path("api/v1/dados/", include("leadstream.entities.urls")),
    path("api/v1/dados/", include("leadstream.evidence.urls")),
    path("api/v1/dados/", include("leadstream.governance.urls")),
    path("api/v1/lotes/", include("leadstream.batches.urls")),
    path("api/v1/leads/", include("leadstream.canonical.urls")),
    path(
        "api/v1/exportacoes/<uuid:export_id>/",
        ExportDetailView.as_view(),
        name="root-export-detail",
    ),
    path(
        "api/v1/exportacoes/<uuid:export_id>/download/",
        ExportDownloadView.as_view(),
        name="root-export-download",
    ),
    path("api/v1/", include("leadstream.billing.urls")),
    path("api/v1/", include("leadstream.providers.urls")),
    path("api/v1/", include("leadstream.integrations.urls")),
    path("api/v1/", include("leadstream.validation.urls")),
    path("api/v1/", include("leadstream.analytics.urls")),
]
