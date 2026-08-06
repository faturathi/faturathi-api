from django.urls import path

from .views import TransmissionListView

urlpatterns = [
    path("peppol/transmissions", TransmissionListView.as_view(), name="peppol-transmissions"),
]
