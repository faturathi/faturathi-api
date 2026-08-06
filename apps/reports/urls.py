from django.urls import path

from .views import DashboardView, TaxGridExportView, TaxGridView, VatGroupsView

urlpatterns = [
    path("reports/dashboard", DashboardView.as_view(), name="reports-dashboard"),
    path("reports/tax-grid", TaxGridView.as_view(), name="reports-tax-grid"),
    path("reports/tax-grid/export", TaxGridExportView.as_view(), name="reports-tax-grid-export"),
    path("vat-groups", VatGroupsView.as_view(), name="vat-groups"),
]
