from __future__ import annotations

from django.urls import path

from leadstream.security.views import (
    APIKeyDetailView,
    APIKeyListCreateView,
    SecurityAuditLogListView,
    TokenObtainPairAuditView,
    TokenRefreshAuditView,
    TokenRevokeView,
)

urlpatterns = [
    path("auth/token/", TokenObtainPairAuditView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshAuditView.as_view(), name="token_refresh"),
    path("auth/token/revoke/", TokenRevokeView.as_view(), name="token_revoke"),
    path("security/keys/", APIKeyListCreateView.as_view(), name="api_keys_list_create"),
    path("security/keys/<uuid:pk>/", APIKeyDetailView.as_view(), name="api_keys_detail"),
    path("security/audit-logs/", SecurityAuditLogListView.as_view(), name="security_audit_logs"),
]
