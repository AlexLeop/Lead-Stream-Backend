from __future__ import annotations

from django.urls import path

from .admin_views import (
    AdminPriceBookUpdateView,
    AdminPricingListView,
    AdminWalletCreditInjectionView,
    AdminWalletListView,
    AdminWalletTransactionsView,
)
from .views import (
    BatchFinancialSummaryView,
    CreditDepositView,
    CreditTransactionListView,
    CreditWalletDetailView,
    PriceBookCollectionView,
)

urlpatterns = [
    path("precos/", PriceBookCollectionView.as_view(), name="price-book-list"),
    path(
        "lotes/<uuid:batch_id>/financeiro/",
        BatchFinancialSummaryView.as_view(),
        name="batch-financial-summary",
    ),
    path("faturamento/carteira/", CreditWalletDetailView.as_view(), name="wallet-detail"),
    path(
        "faturamento/carteira/extrato/",
        CreditTransactionListView.as_view(),
        name="wallet-ledger",
    ),
    path("faturamento/carteira/recarga/", CreditDepositView.as_view(), name="wallet-deposit"),
    path("billing/wallet/", CreditWalletDetailView.as_view(), name="billing-wallet"),
    path("billing/transactions/", CreditTransactionListView.as_view(), name="billing-transactions"),
    path("billing/deposit/", CreditDepositView.as_view(), name="billing-deposit"),
    path("admin/pricing/", AdminPricingListView.as_view(), name="admin-pricing-list"),
    path(
        "admin/pricing/<uuid:book_id>/",
        AdminPriceBookUpdateView.as_view(),
        name="admin-pricing-update",
    ),
    path("admin/wallets/", AdminWalletListView.as_view(), name="admin-wallet-list"),
    path(
        "admin/wallets/<uuid:tenant_id>/credit/",
        AdminWalletCreditInjectionView.as_view(),
        name="admin-wallet-credit",
    ),
    path(
        "admin/wallets/<uuid:tenant_id>/transactions/",
        AdminWalletTransactionsView.as_view(),
        name="admin-wallet-transactions",
    ),
]
