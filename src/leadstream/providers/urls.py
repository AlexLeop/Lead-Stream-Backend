from django.urls import path

from .admin_views import AdminProvidersBudgetView, AdminProvidersConfigView
from .views import (
    DiscoveryCollectionView,
    DiscoveryDetailView,
    DiscoveryMaterializeView,
    DiscoveryResultsView,
    ProviderMetricsView,
    ProviderPolicyCollectionView,
    ProviderPolicyDetailView,
    StartBatchEnrichmentView,
)

urlpatterns = [
    path(
        "admin/providers/",
        AdminProvidersConfigView.as_view(),
        name="admin-providers-config",
    ),
    path(
        "admin/providers/budget/",
        AdminProvidersBudgetView.as_view(),
        name="admin-providers-budget",
    ),
    path("descobertas/", DiscoveryCollectionView.as_view(), name="discovery-list"),
    path(
        "descobertas/<uuid:search_id>/",
        DiscoveryDetailView.as_view(),
        name="discovery-detail",
    ),
    path(
        "descobertas/<uuid:search_id>/resultados/",
        DiscoveryResultsView.as_view(),
        name="discovery-results",
    ),
    path(
        "descobertas/<uuid:search_id>/materializar/",
        DiscoveryMaterializeView.as_view(),
        name="discovery-materialize",
    ),
    path("provedores/", ProviderPolicyCollectionView.as_view(), name="provider-policies"),
    path(
        "provedores/<uuid:policy_id>/",
        ProviderPolicyDetailView.as_view(),
        name="provider-policy-detail",
    ),
    path("metricas/provedores/", ProviderMetricsView.as_view(), name="provider-metrics"),
    path(
        "lotes/<uuid:batch_id>/enriquecer/",
        StartBatchEnrichmentView.as_view(),
        name="batch-enrichment-start",
    ),
]
