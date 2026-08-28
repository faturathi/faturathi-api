from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ApiCredentialView, DocumentApiExamplesView, ErpDeliveryConfigViewSet, ResetSeedsView, SupportTicketListCreateView, SystemConfigView, SystemLogListView, WhoAmIView

router = DefaultRouter(trailing_slash=False)
router.register("erp-delivery-configs", ErpDeliveryConfigViewSet, basename="erp-delivery-config")

urlpatterns = [
    path("config", SystemConfigView.as_view(), name="config-detail"),
    path("config/logs", SystemLogListView.as_view(), name="config-logs"),
    path("config/whoami", WhoAmIView.as_view(), name="config-whoami"),
    path("connectors/credentials", ApiCredentialView.as_view(), name="connector-credentials"),
    path("config/reset-seeds", ResetSeedsView.as_view(), name="config-reset-seeds"),
    path("support/tickets", SupportTicketListCreateView.as_view(), name="support-tickets"),
    path("document-api-examples", DocumentApiExamplesView.as_view(), name="document-api-examples"),
    path("", include(router.urls)),
]
