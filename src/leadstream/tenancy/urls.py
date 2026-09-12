from __future__ import annotations

from django.urls import path

from .admin_views import (
    AdminTenantDetailView,
    AdminTenantImpersonateView,
    AdminTenantListCreateView,
)
from .branding_views import BrandingView
from .views import WorkspaceView

app_name = "tenancy"

urlpatterns = [
    path("workspace/", WorkspaceView.as_view(), name="workspace"),
    path("system/branding/", BrandingView.as_view(), name="system-branding"),
    path("admin/tenants/", AdminTenantListCreateView.as_view(), name="admin-tenant-list"),
    path(
        "admin/tenants/<uuid:tenant_id>/",
        AdminTenantDetailView.as_view(),
        name="admin-tenant-detail",
    ),
    path(
        "admin/tenants/<uuid:tenant_id>/impersonate/",
        AdminTenantImpersonateView.as_view(),
        name="admin-tenant-impersonate",
    ),
]
