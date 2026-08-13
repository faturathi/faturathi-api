"""Deterministic operational log fixtures used by demo/UAT management commands."""

from datetime import timedelta

from django.utils import timezone

from apps.company.models import Company
from apps.user.models import User

from .models import SystemLog


DEMO_LOG_MATRIX = [
    ("USER_ACTIVITY", "INFO", "USER_LOGIN", "Authentication", "Email OTP login completed successfully"),
    ("USER_ACTIVITY", "WARN", "USER_PERMISSION_WARNING", "Authorization", "User attempted an action outside the assigned entity scope"),
    ("USER_ACTIVITY", "ERROR", "USER_ACTION_FAILED", "User", "Customer update failed because a required VAT field was invalid"),
    ("USER_ACTIVITY", "AUDIT", "USER_PROFILE_UPDATED", "User", "Administrator changed a user role and entity access scope"),
    ("USER_ACTIVITY", "TRANSMISSION", "USER_DOCUMENT_SUBMIT", "Document", "User confirmed invoice submission to Peppol"),

    ("OTA_AS4", "INFO", "OTA_STATUS_RECEIVED", "OTA", "OTA processing status received for the submitted document"),
    ("OTA_AS4", "WARN", "AS4_DELIVERY_DELAY", "Transmission", "AS4 acknowledgement is approaching the configured SLA threshold"),
    ("OTA_AS4", "ERROR", "OTA_REJECTION", "Transmission", "OTA rejected the document because the buyer VATIN failed validation"),
    ("OTA_AS4", "AUDIT", "PEPPOL_EVIDENCE_STORED", "Transmission", "Peppol transmission evidence and response metadata archived"),
    ("OTA_AS4", "TRANSMISSION", "AS4_ACK_RECEIVED", "Transmission", "Peppol C3 acknowledgement received and TDD lifecycle updated"),

    ("SERVER_API", "INFO", "API_REQUEST_COMPLETED", "REST API", "Invoice API request completed successfully"),
    ("SERVER_API", "WARN", "API_RATE_WARNING", "REST API", "Connector traffic reached the demonstration warning threshold"),
    ("SERVER_API", "ERROR", "API_UPSTREAM_TIMEOUT", "ApplicationServer", "Upstream Peppol service timed out and was queued for retry"),
    ("SERVER_API", "AUDIT", "API_CREDENTIAL_USED", "ApiCredential", "Machine credential authenticated a tenant-scoped inbound request"),
    ("SERVER_API", "TRANSMISSION", "API_INVOICE_RECEIVED", "REST API", "ERP invoice payload received and handed to the document pipeline"),

    ("ERROR_WARNING", "INFO", "VALIDATION_SUMMARY", "Validator", "Document validation completed with no blocking errors"),
    ("ERROR_WARNING", "WARN", "VALIDATION_WARNING", "Validator", "Optional buyer postcode is missing from the payload"),
    ("ERROR_WARNING", "ERROR", "SYSTEM_ERROR", "BackgroundJob", "Retryable background processing exception recorded"),
    ("ERROR_WARNING", "AUDIT", "ERROR_REVIEWED", "SupportTicket", "Administrator reviewed and acknowledged an operational exception"),
    ("ERROR_WARNING", "TRANSMISSION", "TRANSMISSION_RETRY", "Transmission", "Rejected transmission was corrected and queued for re-submission"),
]


def populate_demo_logs(*, companies=None, clear_demo=False):
    companies = list(companies or Company.objects.filter(is_active=True).order_by("short_code"))
    if clear_demo:
        SystemLog.all_objects.filter(entity_id__startswith="DEMO-LOG-").delete()

    now = timezone.now()
    created = updated = 0
    for company_index, company in enumerate(companies):
        user = User.objects.filter(company=company, is_active=True).order_by("email").first()
        for index, (category, level, action, entity, message) in enumerate(DEMO_LOG_MATRIX, start=1):
            entity_id = f"DEMO-LOG-{company.short_code}-{index:02d}"
            defaults = {
                "company": company, "user": user, "action": action, "entity": entity,
                "detail": {
                    "category": category, "category_label": category.replace("_", " / ").title(),
                    "level": level, "severity": level, "message": message,
                    "demo": True, "source": "seed_demo_logs",
                },
                "ip_address": f"10.0.{company_index + 1}.{(index % 200) + 10}", "created_by": user,
                "is_deleted": False, "deleted_at": None,
            }
            row, was_created = SystemLog.all_objects.update_or_create(entity_id=entity_id, defaults=defaults)
            # Spread fixtures over recent history so date/time filters and charts are meaningful.
            SystemLog.all_objects.filter(pk=row.pk).update(created_at=now - timedelta(minutes=index * 17 + company_index * 5))
            created += int(was_created)
            updated += int(not was_created)
    return {"companies": len(companies), "created": created, "updated": updated, "total": len(companies) * len(DEMO_LOG_MATRIX)}
