from django.db import models

from core.models import TenantModel


class Transmission(TenantModel):
    """Simulated Peppol AS4 / OTA / TDD / MLS lifecycle for one submit/resubmit attempt."""

    STATUS_CHOICES = [
        ("QUEUED", "Queued"), ("VALIDATING", "Validating"), ("VALIDATED", "Schematron OK"),
        ("AS4_SENT", "AS4 Sent (C2→C3)"), ("ACK_RECEIVED", "Ack Received"),
        ("TDD_REPORTED", "TDD Reported (C5)"), ("MLS_RECEIVED", "MLS Received"),
        ("REJECTED", "Rejected"),
    ]

    document = models.ForeignKey(
        "documents.Document", on_delete=models.CASCADE, related_name="transmissions")
    attempt = models.PositiveSmallIntegerField(default=1)  # resubmits increment this
    status = models.CharField(max_length=14, choices=STATUS_CHOICES, default="QUEUED")
    payload = models.JSONField(default=dict)  # UBL-like JSON snapshot of the document
    validation_errors = models.JSONField(default=list, blank=True)  # [{rule, field, code, message}]
    ota_response_code = models.CharField(max_length=10, blank=True)  # "OK" or "C5", "C8"...
    ota_message = models.CharField(max_length=255, blank=True)
    mls_status = models.CharField(max_length=10, blank=True)  # "AB", "RE", "AP" style codes
    sent_at = models.DateTimeField(null=True, blank=True)
    acked_at = models.DateTimeField(null=True, blank=True)
    reported_at = models.DateTimeField(null=True, blank=True)

    class Meta(TenantModel.Meta):
        ordering = ["-attempt", "-created_at"]

    def __str__(self):
        return f"{self.document.invoice_number} #{self.attempt} {self.status}"

    def save(self, *args, **kwargs):
        if self.document_id:
            self.company_id = self.document.company_id
        super().save(*args, **kwargs)
