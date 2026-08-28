import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("company", "0005_protect_company_group"),
        ("config", "0005_supportticket_systemconfig_notification_emails"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ErpDeliveryConfig",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("name", models.CharField(max_length=120)),
                ("base_url", models.URLField(max_length=500)),
                ("endpoint_path", models.CharField(default="/api/accounts-payable/invoices", max_length=240)),
                ("http_method", models.CharField(choices=[("POST", "POST"), ("PUT", "PUT"), ("PATCH", "PATCH")], default="POST", max_length=8)),
                ("auth_type", models.CharField(choices=[("NONE", "No authentication"), ("BEARER", "Bearer token"), ("API_KEY", "API key header"), ("BASIC", "Basic authentication"), ("OAUTH2", "OAuth 2 token")], default="BEARER", max_length=12)),
                ("auth_header_name", models.CharField(default="Authorization", max_length=80)),
                ("auth_token", models.TextField(blank=True)),
                ("username", models.CharField(blank=True, max_length=120)),
                ("custom_headers", models.JSONField(blank=True, default=dict)),
                ("payload_template", models.JSONField(blank=True, default=dict)),
                ("timeout_seconds", models.PositiveSmallIntegerField(default=30)),
                ("is_active", models.BooleanField(default=True)),
                ("branch", models.ForeignKey(blank=True, help_text="Blank means the company-level centralized ERP target.", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="erp_delivery_configs", to="company.companybranch")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="%(class)s_set", to="company.company")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="erpdeliveryconfig",
            constraint=models.UniqueConstraint(condition=models.Q(("branch__isnull", True), ("is_deleted", False)), fields=("company",), name="uniq_company_central_erp_delivery"),
        ),
        migrations.AddConstraint(
            model_name="erpdeliveryconfig",
            constraint=models.UniqueConstraint(condition=models.Q(("branch__isnull", False), ("is_deleted", False)), fields=("company", "branch"), name="uniq_company_branch_erp_delivery"),
        ),
    ]
