from __future__ import annotations

from django.urls import path

from .views import CanonicalLeadDetailView

urlpatterns = [
    path(
        "<uuid:item_id>/canonical/", CanonicalLeadDetailView.as_view(), name="canonical-lead-detail"
    ),
    path("<uuid:item_id>/", CanonicalLeadDetailView.as_view(), name="canonical-lead-direct"),
]
