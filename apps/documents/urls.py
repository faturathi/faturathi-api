from rest_framework.routers import DefaultRouter

from django.urls import path

from .views import (
    BatchFileUploadView, BatchUploadView, DocumentTypeCatalogView, InvoiceViewSet,
    LegacyReceiveView, LegacyRequestsView, PintOmPayloadCreateView,
    PintOmPayloadValidateView, ValidateOmanView,
)

router = DefaultRouter(trailing_slash=False)
router.register("invoices", InvoiceViewSet, basename="invoice")

urlpatterns = [
    # Canonical production contract. Explicit slash paths intentionally precede the
    # slashless compatibility router used by the historical React application.
    path("invoices/validate/", PintOmPayloadValidateView.as_view(), name="pint-om-validate"),
    path("invoices/", PintOmPayloadCreateView.as_view(), name="pint-om-create"),
    path("document-types", DocumentTypeCatalogView.as_view(), name="document-types"),
    path("upload-batch", BatchUploadView.as_view(), name="upload-batch"),
    path("upload-batch/file", BatchFileUploadView.as_view(), name="upload-batch-file"),
    path("validate", ValidateOmanView.as_view(), name="validate"),
    path("validate-oman", ValidateOmanView.as_view(), name="validate-oman"),
    path("requests", LegacyRequestsView.as_view(), name="legacy-requests"),
    path("receive", LegacyReceiveView.as_view(), name="legacy-receive"),
] + router.urls
