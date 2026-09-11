from django.urls import path

from .views import (
    BatchChunksView,
    BatchCollectionView,
    BatchDetailView,
    BatchExportCreateView,
    BatchExportListView,
    BatchItemsView,
    CancelBatchView,
    ExportDetailView,
    ExportDownloadView,
    PauseBatchView,
    ResumeBatchView,
)

urlpatterns = [
    path("", BatchCollectionView.as_view(), name="batch-list"),
    path("<uuid:batch_id>/", BatchDetailView.as_view(), name="batch-detail"),
    path("<uuid:batch_id>/itens/", BatchItemsView.as_view(), name="batch-items"),
    path("<uuid:batch_id>/chunks/", BatchChunksView.as_view(), name="batch-chunks"),
    path("<uuid:batch_id>/pausar/", PauseBatchView.as_view(), name="batch-pause"),
    path("<uuid:batch_id>/retomar/", ResumeBatchView.as_view(), name="batch-resume"),
    path("<uuid:batch_id>/cancelar/", CancelBatchView.as_view(), name="batch-cancel"),
    path("<uuid:batch_id>/exportar/", BatchExportCreateView.as_view(), name="batch-export-create"),
    path("<uuid:batch_id>/exportacoes/", BatchExportListView.as_view(), name="batch-export-list"),
    path("exportacoes/<uuid:export_id>/", ExportDetailView.as_view(), name="export-detail"),
    path(
        "exportacoes/<uuid:export_id>/download/",
        ExportDownloadView.as_view(),
        name="export-download",
    ),
]
