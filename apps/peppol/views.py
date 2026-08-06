from rest_framework import generics

from .models import Transmission
from .serializers import TransmissionSerializer


class TransmissionListView(generics.ListAPIView):
    """GET /api/peppol/transmissions/?document=<invoice_number> — lifecycle timeline (TDD & MLS)."""

    serializer_class = TransmissionSerializer

    def get_queryset(self):
        qs = Transmission.objects.filter(
            company_id__in=getattr(self.request, "active_company_ids", [])
        ).select_related("document")
        document_param = self.request.query_params.get("document")
        if document_param:
            qs = qs.filter(document__invoice_number=document_param)
        return qs
