from __future__ import annotations

from django.urls import re_path

from .views import (
    ActivitiesCollectionView,
    CrmConnectionsView,
    DashboardView,
    DataHealthView,
    DatasetDetailView,
    DatasetsCollectionView,
    DiscoveryCnaesView,
    DiscoveryExtractView,
    DiscoverySearchView,
    EnrichmentCatalogView,
    EnrichmentCompanyView,
    EnrichmentLookupView,
    EnrichmentRunsView,
    EnrichmentStatusView,
    ImportsCollectionView,
    LeadLookupView,
    LeadRevealPhoneView,
    LeadsCollectionView,
    ListAddLeadsView,
    ListArchiveView,
    ListsCollectionView,
    PixStatusView,
)

urlpatterns = [
    re_path(r"^dashboard/?$", DashboardView.as_view(), name="manager-dashboard"),
    re_path(r"^data-health/?$", DataHealthView.as_view(), name="manager-data-health"),
    re_path(r"^data-health/repair/?$", DataHealthView.as_view(), name="manager-data-health-repair"),
    re_path(r"^datasets/?$", DatasetsCollectionView.as_view(), name="manager-datasets"),
    re_path(
        r"^datasets/(?P<dataset_id>[^/]+)/?$",
        DatasetDetailView.as_view(),
        name="manager-dataset-detail",
    ),
    re_path(r"^leads/?$", LeadsCollectionView.as_view(), name="manager-leads"),
    re_path(r"^leads/lookup/?$", LeadLookupView.as_view(), name="manager-lead-lookup"),
    re_path(
        r"^leads/(?P<lead_id>[^/]+)/reveal-phone/?$",
        LeadRevealPhoneView.as_view(),
        name="manager-lead-reveal-phone",
    ),
    re_path(r"^imports/?$", ImportsCollectionView.as_view(), name="manager-imports"),
    re_path(r"^lists/?$", ListsCollectionView.as_view(), name="manager-lists"),
    re_path(
        r"^lists/(?P<list_id>[^/]+)/archive/?$",
        ListArchiveView.as_view(),
        name="manager-list-archive",
    ),
    re_path(
        r"^lists/(?P<list_id>[^/]+)/leads/?$",
        ListAddLeadsView.as_view(),
        name="manager-list-add-leads",
    ),
    re_path(r"^activities/?$", ActivitiesCollectionView.as_view(), name="manager-activities"),
    re_path(r"^crm-connections/?$", CrmConnectionsView.as_view(), name="manager-crm-connections"),
    re_path(r"^pix/status/?$", PixStatusView.as_view(), name="manager-pix-status"),
    re_path(
        r"^enrichment/status/?$", EnrichmentStatusView.as_view(), name="manager-enrichment-status"
    ),
    re_path(
        r"^enrichment/catalog/?$",
        EnrichmentCatalogView.as_view(),
        name="manager-enrichment-catalog",
    ),
    re_path(r"^enrichment/runs/?$", EnrichmentRunsView.as_view(), name="manager-enrichment-runs"),
    re_path(
        r"^enrichment/company/?$",
        EnrichmentCompanyView.as_view(),
        name="manager-enrichment-company",
    ),
    re_path(
        r"^enrichment/lookup/?$", EnrichmentLookupView.as_view(), name="manager-enrichment-lookup"
    ),
    re_path(r"^discovery/cnaes/?$", DiscoveryCnaesView.as_view(), name="manager-discovery-cnaes"),
    re_path(
        r"^discovery/search/?$", DiscoverySearchView.as_view(), name="manager-discovery-search"
    ),
    re_path(
        r"^discovery/extract/?$", DiscoveryExtractView.as_view(), name="manager-discovery-extract"
    ),
]
