from django.db import models

from core.models import TenantModel


class SystemConfig(TenantModel):
    """One row per tenant (get_or_create)."""

    country = models.CharField(max_length=2, default="OM")
    timezone = models.CharField(max_length=40, default="Asia/Muscat")
    base_currency = models.CharField(max_length=3, default="OMR")
    fx_rate_usd = models.DecimalField(max_digits=8, decimal_places=4, default="0.3850")
    language_mode = models.CharField(max_length=20, default="EN_AR_BILINGUAL")
    mfa_enforced = models.BooleanField(default=True)
    security_alerts = models.BooleanField(default=True)
    admin_alerts = models.BooleanField(default=True)
    allow_user_logins = models.BooleanField(default=True)
    backup_retention_years = models.PositiveSmallIntegerField(default=7)
    maintenance_window = models.CharField(max_length=40, default="Sun 02:00-04:00 GST")
    webhook_url = models.URLField(blank=True)
    admin_alert_contact = models.CharField(max_length=120, blank=True)
    master_api_key = models.CharField(max_length=64, blank=True)  # fake, display-only


class SystemLog(TenantModel):
    """Doubles as the immutable audit log. Never update/delete rows (convention only)."""

    user = models.ForeignKey("user.User", null=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=60)  # LOGIN, INVOICE_CREATE, INVOICE_SUBMIT, RESEED...
    entity = models.CharField(max_length=60, blank=True)  # "Document", "Transmission", ...
    entity_id = models.CharField(max_length=40, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
