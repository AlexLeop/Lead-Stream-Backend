from django.urls import path

from .views import (
    ProviderMetricsView,
    ProviderPolicyCollectionView,
    ProviderPolicyDetailView,
    StartBatchEnrichmentView,
)

urlpatterns = [
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
