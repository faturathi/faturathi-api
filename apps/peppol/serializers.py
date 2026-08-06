from rest_framework import serializers

from .models import Transmission


class TransmissionSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="document.invoice_number", read_only=True)

    class Meta:
        model = Transmission
        fields = [
            "id", "document", "invoice_number", "attempt", "status", "payload",
            "validation_errors", "ota_response_code", "ota_message", "mls_status",
            "sent_at", "acked_at", "reported_at", "created_at",
        ]
        read_only_fields = fields
