from __future__ import annotations

from django.urls import path

from .admin_views import AdminSMTPConfigView, AdminSMTPProbeView
from .views import EmailValidationView

urlpatterns = [
    path("validacao/emails/", EmailValidationView.as_view(), name="email-validation"),
    path("validation/email/", EmailValidationView.as_view(), name="email-validation-alias"),
    path("admin/smtp-config/", AdminSMTPConfigView.as_view(), name="admin-smtp-config"),
    path("admin/smtp-probe/", AdminSMTPProbeView.as_view(), name="admin-smtp-probe"),
]
