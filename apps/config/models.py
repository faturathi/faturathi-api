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
    enable_auto_backups = models.BooleanField(default=True)
    backup_retention_years = models.PositiveSmallIntegerField(default=7)
    maintenance_window = models.CharField(max_length=40, default="Sun 02:00-04:00 GST")
    webhook_url = models.URLField(blank=True)
    admin_alert_contact = models.CharField(max_length=120, blank=True)
    notification_emails = models.JSONField(default=list, blank=True)
    master_api_key = models.CharField(max_length=64, blank=True)  # fake, display-only


class SystemLog(TenantModel):
    """Doubles as the immutable audit log. Never update/delete rows (convention only)."""

    user = models.ForeignKey("user.User", null=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=60)  # LOGIN, INVOICE_CREATE, INVOICE_SUBMIT, RESEED...
    entity = models.CharField(max_length=60, blank=True)  # "Document", "Transmission", ...
    entity_id = models.CharField(max_length=40, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)


class ApiCredential(TenantModel):
    """Company-scoped machine credential. The raw key is returned once; only its hash is stored."""

    name = models.CharField(max_length=120)
    key_prefix = models.CharField(max_length=24, db_index=True)
    key_hash = models.CharField(max_length=64, unique=True)
    service_user = models.ForeignKey("user.User", on_delete=models.CASCADE, related_name="api_credentials")
    scopes = models.JSONField(default=list, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)


class ErpDeliveryConfig(TenantModel):
    """Outbound AP-invoice delivery target at company level or for one operational branch."""

    AUTH_CHOICES = [
        ("NONE", "No authentication"),
        ("BEARER", "Bearer token"),
        ("API_KEY", "API key header"),
        ("BASIC", "Basic authentication"),
        ("OAUTH2", "OAuth 2 token"),
    ]
    METHOD_CHOICES = [(value, value) for value in ("POST", "PUT", "PATCH")]

    branch = models.ForeignKey(
        "company.CompanyBranch", null=True, blank=True, on_delete=models.PROTECT,
        related_name="erp_delivery_configs",
        help_text="Blank means the company-level centralized ERP target.",
    )
    name = models.CharField(max_length=120)
    base_url = models.URLField(max_length=500)
    endpoint_path = models.CharField(max_length=240, default="/api/accounts-payable/invoices")
    http_method = models.CharField(max_length=8, choices=METHOD_CHOICES, default="POST")
    auth_type = models.CharField(max_length=12, choices=AUTH_CHOICES, default="BEARER")
    auth_header_name = models.CharField(max_length=80, default="Authorization")
    auth_token = models.TextField(blank=True)
    username = models.CharField(max_length=120, blank=True)
    custom_headers = models.JSONField(default=dict, blank=True)
    payload_template = models.JSONField(default=dict, blank=True)
    timeout_seconds = models.PositiveSmallIntegerField(default=30)
    is_active = models.BooleanField(default=True)

    class Meta(TenantModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["company"],
                condition=models.Q(branch__isnull=True, is_deleted=False),
                name="uniq_company_central_erp_delivery",
            ),
            models.UniqueConstraint(
                fields=["company", "branch"],
                condition=models.Q(branch__isnull=False, is_deleted=False),
                name="uniq_company_branch_erp_delivery",
            ),
        ]

    def __str__(self):
        scope = self.branch.code if self.branch_id else "Company central"
        return f"{self.company} · {scope} · {self.name}"


class SupportTicket(TenantModel):
    CATEGORY_CHOICES = [("TECHNICAL", "Technical"), ("BILLING", "Billing"), ("PEPPOL", "Peppol / OTA"), ("DATA", "Data / archive")]
    STATUS_CHOICES = [("OPEN", "Open"), ("IN_PROGRESS", "In progress"), ("RESOLVED", "Resolved")]
    subject = models.CharField(max_length=160)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="TECHNICAL")
    contact_email = models.EmailField()
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OPEN")
