from __future__ import annotations

from django.urls import path

from .admin_views import (
    AdminAuditLogsView,
    AdminSuppressionDetailView,
    AdminSuppressionListView,
)
from .views import ApplyRetentionView, SuppressionCollectionView

urlpatterns = [
    path("supressoes/", SuppressionCollectionView.as_view(), name="suppression-list"),
    path("retencao/aplicar/", ApplyRetentionView.as_view(), name="retention-apply"),
    path("admin/suppression/", AdminSuppressionListView.as_view(), name="admin-suppression-list"),
    path(
        "admin/suppression/<uuid:suppression_id>/",
        AdminSuppressionDetailView.as_view(),
        name="admin-suppression-detail",
    ),
    path("admin/audit-logs/", AdminAuditLogsView.as_view(), name="admin-audit-logs"),
]
