from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

UserModel = get_user_model()


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Permite autenticação flexível com Username ou E-mail (case-insensitive)
    mantendo compatibilidade com o ModelBackend padrão do Django.
    """

    def authenticate(
        self,
        request: Any = None,
        username: str | None = None,
        password: str | None = None,
        **kwargs: Any,
    ) -> Any | None:
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if not username or not password:
            return None

        clean_identifier = str(username).strip()
        user = UserModel.objects.filter(
            Q(username__iexact=clean_identifier) | Q(email__iexact=clean_identifier)
        ).first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
