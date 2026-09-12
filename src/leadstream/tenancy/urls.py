from __future__ import annotations

from django.urls import path

from .branding_views import BrandingView
from .views import WorkspaceView

app_name = "tenancy"

urlpatterns = [
    path("workspace/", WorkspaceView.as_view(), name="workspace"),
    path("system/branding/", BrandingView.as_view(), name="system-branding"),
]
