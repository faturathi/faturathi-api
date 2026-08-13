from rest_framework import serializers

from .models import SupportTicket, SystemConfig, SystemLog


class SystemConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemConfig
        fields = [
            "id", "country", "timezone", "base_currency", "fx_rate_usd", "language_mode",
            "mfa_enforced", "security_alerts", "admin_alerts", "allow_user_logins",
            "enable_auto_backups",
            "backup_retention_years", "maintenance_window", "webhook_url",
            "admin_alert_contact", "master_api_key",
            "notification_emails",
        ]
        read_only_fields = ["id", "master_api_key"]

    def validate_notification_emails(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Provide email recipients as a list.")
        validator = serializers.EmailField()
        cleaned = []
        for item in value:
            email = validator.run_validation(str(item).strip().lower())
            if email not in cleaned:
                cleaned.append(email)
        return cleaned


class SystemLogSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True, default="")

    class Meta:
        model = SystemLog
        fields = ["id", "user", "user_email", "action", "entity", "entity_id",
                  "detail", "ip_address", "created_at"]
        read_only_fields = fields


class SupportTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = ["id", "subject", "category", "contact_email", "message", "status", "created_at"]
        read_only_fields = ["id", "status", "created_at"]
