from django.urls import path

from .views import ResetSeedsView, SystemConfigView, SystemLogListView

urlpatterns = [
    path("config", SystemConfigView.as_view(), name="config-detail"),
    path("config/logs", SystemLogListView.as_view(), name="config-logs"),
    path("config/reset-seeds", ResetSeedsView.as_view(), name="config-reset-seeds"),
]
