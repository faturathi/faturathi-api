from django.urls import path

from .views import ArchiveExportView, BranchSummaryView, DashboardView, TaxGridExportView, TaxGridView, VatGroupsView

urlpatterns = [
    path("reports/dashboard", DashboardView.as_view(), name="reports-dashboard"),
    path("reports/tax-grid", TaxGridView.as_view(), name="reports-tax-grid"),
    path("reports/branch-summary", BranchSummaryView.as_view(), name="reports-branch-summary"),
    path("reports/tax-grid/export", TaxGridExportView.as_view(), name="reports-tax-grid-export"),
    path("reports/archive/export", ArchiveExportView.as_view(), name="reports-archive-export"),
    path("vat-groups", VatGroupsView.as_view(), name="vat-groups"),
]
