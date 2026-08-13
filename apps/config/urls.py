from django.urls import path

from .views import ApiCredentialView, ResetSeedsView, SupportTicketListCreateView, SystemConfigView, SystemLogListView, WhoAmIView

urlpatterns = [
    path("config", SystemConfigView.as_view(), name="config-detail"),
    path("config/logs", SystemLogListView.as_view(), name="config-logs"),
    path("config/whoami", WhoAmIView.as_view(), name="config-whoami"),
    path("connectors/credentials", ApiCredentialView.as_view(), name="connector-credentials"),
    path("config/reset-seeds", ResetSeedsView.as_view(), name="config-reset-seeds"),
    path("support/tickets", SupportTicketListCreateView.as_view(), name="support-tickets"),
]
