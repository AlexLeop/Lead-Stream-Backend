from __future__ import annotations

from django.urls import path

from .admin_views import (
    AdminBatchActionView,
    AdminBatchesListView,
    AdminCeleryQueuesView,
)

urlpatterns = [
    path("admin/batches/", AdminBatchesListView.as_view(), name="admin-batches-list"),
    path(
        "admin/batches/<uuid:batch_id>/<str:action>/",
        AdminBatchActionView.as_view(),
        name="admin-batch-action",
    ),
    path("admin/celery/queues/", AdminCeleryQueuesView.as_view(), name="admin-celery-queues"),
]
