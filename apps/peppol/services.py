"""Simulated AS4/OTA engine: synchronous state machine + fake timestamps, no external calls."""

from datetime import timedelta

from django.utils import timezone

from apps.documents.services import recompute_totals
from apps.documents.pint_om import build_pint_payload, refresh_pint_snapshot
from apps.utils import uuid5
from apps.utils.validators import validate_document

from .models import Transmission


def _build_payload(document) -> dict:
    return build_pint_payload(document)


def submit_document(document, user, force_status: str | None = None) -> Transmission:
    """Runs validation; on success walks QUEUED->AS4_SENT->ACK_RECEIVED->TDD_REPORTED->MLS_RECEIVED."""
    recompute_totals(document)
    errors = validate_document(document)
    attempt = document.transmissions.count() + 1

    if errors:
        transmission = Transmission.objects.create(
            company=document.company, document=document, attempt=attempt, status="REJECTED",
            payload=_build_payload(document), validation_errors=errors,
            ota_response_code=errors[0]["code"], ota_message=errors[0]["message"],
            created_by=user,
        )
        document.status = "REJECTED"
        document.save(update_fields=["status"])
        refresh_pint_snapshot(document)
        return transmission

    document.uuid_v5 = uuid5.generate(document)
    document.save(update_fields=["uuid_v5"])
    refresh_pint_snapshot(document)

    now = timezone.now()
    final_status = force_status or "MLS_RECEIVED"
    transmission = Transmission.objects.create(
        company=document.company, document=document, attempt=attempt,
        status=final_status, payload=_build_payload(document),
        sent_at=now + timedelta(seconds=1),
        acked_at=now + timedelta(seconds=2),
        reported_at=now + timedelta(seconds=3),
        ota_response_code="OK", mls_status="AB",
        created_by=user,
    )
    document.status = "REPORTED"
    document.save(update_fields=["status"])
    refresh_pint_snapshot(document)
    return transmission


def resubmit_document(document, user) -> Transmission:
    return submit_document(document, user)
