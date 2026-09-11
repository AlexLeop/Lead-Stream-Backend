from __future__ import annotations

from django.urls import path

from .views import (
    AdminCRMOverviewView,
    BatchSyncToCRMView,
    CRMConnectionDetailView,
    CRMConnectionListCreateView,
    CRMConnectionTestView,
    CRMFieldMappingDetailView,
    CRMFieldMappingListCreateView,
    CRMOutboxMessageListView,
    CRMOutboxRetryDeadLetterView,
    CRMOutboxStatusView,
)

app_name = "integrations"

urlpatterns = [
    # B2B Workspace - Conexões
    path(
        "integracoes/conexoes/",
        CRMConnectionListCreateView.as_view(),
        name="crm_connection_list_create",
    ),
    path(
        "integracoes/conexoes/<uuid:pk>/",
        CRMConnectionDetailView.as_view(),
        name="crm_connection_detail",
    ),
    path(
        "integracoes/conexoes/<uuid:pk>/testar/",
        CRMConnectionTestView.as_view(),
        name="crm_connection_test",
    ),
    # B2B Workspace - Mapeamento de Campos
    path(
        "integracoes/conexoes/<uuid:connection_id>/mapeamentos/",
        CRMFieldMappingListCreateView.as_view(),
        name="crm_field_mapping_list_create",
    ),
    path(
        "integracoes/conexoes/<uuid:connection_id>/mapeamentos/<uuid:pk>/",
        CRMFieldMappingDetailView.as_view(),
        name="crm_field_mapping_detail",
    ),
    # B2B Workspace - Acompanhamento e Métricas da Outbox
    path(
        "integracoes/outbox/status/",
        CRMOutboxStatusView.as_view(),
        name="crm_outbox_status",
    ),
    path(
        "integracoes/outbox/retry-dead-letter/",
        CRMOutboxRetryDeadLetterView.as_view(),
        name="crm_outbox_retry_dead_letter",
    ),
    path(
        "integracoes/conexoes/<uuid:connection_id>/outbox/",
        CRMOutboxMessageListView.as_view(),
        name="crm_outbox_message_list",
    ),
    # B2B Workspace - Disparo de Sincronização de Lote com CRM
    path(
        "lotes/<uuid:batch_id>/sincronizar-crm/",
        BatchSyncToCRMView.as_view(),
        name="batch_sync_to_crm",
    ),
    # Cockpit do CEO - Visão Consolidada de Integrações
    path(
        "admin/integracoes/metricas/",
        AdminCRMOverviewView.as_view(),
        name="admin_crm_overview",
    ),
]
