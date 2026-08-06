from rest_framework import serializers

from .models import SystemConfig, SystemLog


class SystemConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemConfig
        fields = [
            "id", "country", "timezone", "base_currency", "fx_rate_usd", "language_mode",
            "mfa_enforced", "security_alerts", "admin_alerts", "allow_user_logins",
            "enable_auto_backups",
            "backup_retention_years", "maintenance_window", "webhook_url",
            "admin_alert_contact", "master_api_key",
        ]
        read_only_fields = ["id", "master_api_key"]


class SystemLogSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True, default="")

    class Meta:
        model = SystemLog
        fields = ["id", "user", "user_email", "action", "entity", "entity_id",
                  "detail", "ip_address", "created_at"]
        read_only_fields = fields
