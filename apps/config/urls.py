from django.urls import path

from .views import ApiCredentialView, ResetSeedsView, SystemConfigView, SystemLogListView

urlpatterns = [
    path("config", SystemConfigView.as_view(), name="config-detail"),
    path("config/logs", SystemLogListView.as_view(), name="config-logs"),
    path("connectors/credentials", ApiCredentialView.as_view(), name="connector-credentials"),
    path("config/reset-seeds", ResetSeedsView.as_view(), name="config-reset-seeds"),
]
