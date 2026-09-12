from django.urls import path

from .views import EmailValidationView

urlpatterns = [
    path("validacao/emails/", EmailValidationView.as_view(), name="email-validation"),
    path("validation/email/", EmailValidationView.as_view(), name="email-validation-alias"),
]
