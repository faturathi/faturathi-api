from rest_framework import serializers

from .models import ErpDeliveryConfig, SupportTicket, SystemConfig, SystemLog


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
    level = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()

    @staticmethod
    def _detail(obj):
        return obj.detail if isinstance(obj.detail, dict) else {}

    def get_level(self, obj):
        detail = self._detail(obj)
        value = str(detail.get("level") or detail.get("severity") or "").strip().upper()
        if value == "WARNING":
            return "WARN"
        if value in {"AS4", "TRANSMISSION"}:
            return "TRANSMISSION"
        if value in {"INFO", "WARN", "ERROR", "AUDIT"}:
            return value
        if obj.entity == "Transmission":
            return "TRANSMISSION"
        if "ERROR" in obj.action.upper():
            return "ERROR"
        return "AUDIT"

    def get_category(self, obj):
        detail = self._detail(obj)
        value = str(detail.get("category") or "").strip().upper()
        if value:
            return value
        if obj.entity == "Transmission":
            return "OTA_AS4"
        if "ERROR" in obj.action.upper() or self.get_level(obj) in {"WARN", "ERROR"}:
            return "ERROR_WARNING"
        return "USER_ACTIVITY"

    def get_message(self, obj):
        detail = self._detail(obj)
        value = str(detail.get("message") or "").strip()
        if value:
            return value
        return f"{obj.action}{f' — {obj.entity_id}' if obj.entity_id else ''}"

    class Meta:
        model = SystemLog
        fields = ["id", "user", "user_email", "action", "entity", "entity_id",
                  "level", "category", "message", "detail", "ip_address", "created_at"]
        read_only_fields = fields


class SupportTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = ["id", "subject", "category", "contact_email", "message", "status", "created_at"]
        read_only_fields = ["id", "status", "created_at"]


class ErpDeliveryConfigSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name_en", read_only=True)
    branch_code = serializers.CharField(source="branch.code", read_only=True, default="")
    branch_name = serializers.CharField(source="branch.name", read_only=True, default="")
    token_configured = serializers.SerializerMethodField()
    curl_preview = serializers.SerializerMethodField()
    clear_token = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = ErpDeliveryConfig
        fields = [
            "id", "company", "company_name", "branch", "branch_code", "branch_name",
            "name", "base_url", "endpoint_path", "http_method", "auth_type",
            "auth_header_name", "auth_token", "username", "custom_headers",
            "payload_template", "timeout_seconds", "is_active", "token_configured",
            "curl_preview", "clear_token", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "company", "company_name", "branch_code", "branch_name",
            "token_configured", "curl_preview", "created_at", "updated_at",
        ]
        extra_kwargs = {
            "auth_token": {"write_only": True, "required": False, "allow_blank": True},
        }

    def get_token_configured(self, obj):
        return bool(obj.auth_token)

    def get_curl_preview(self, obj):
        target = f"{obj.base_url.rstrip('/')}/{obj.endpoint_path.lstrip('/')}"
        parts = [f"curl --request {obj.http_method} '{target}'", "--header 'Content-Type: application/json'"]
        for key, value in (obj.custom_headers or {}).items():
            parts.append(f"--header '{key}: {value}'")
        if obj.auth_type != "NONE":
            parts.append(f"--header '{obj.auth_header_name}: <configured-secret>'")
        parts.append("--data '<mapped AP invoice payload>'")
        return " \\\n  ".join(parts)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get("request")
        branch = attrs.get("branch", getattr(self.instance, "branch", None))
        company = getattr(self.instance, "company", None)
        if company is None and request is not None:
            company_ids = getattr(request, "active_company_ids", [])
            if branch and branch.company_id not in company_ids:
                raise serializers.ValidationError({
                    "branch": ["The selected branch is outside your active company scope."]
                })
            requested_company = request.data.get("company")
            if requested_company:
                from apps.company.models import Company
                company = Company.objects.filter(id__in=company_ids, pk=requested_company).first()
        if branch and company and branch.company_id != company.id:
            raise serializers.ValidationError({
                "branch": ["The selected branch does not belong to the selected company."]
            })
        for field in ("custom_headers", "payload_template"):
            value = attrs.get(field, getattr(self.instance, field, {}))
            if not isinstance(value, dict):
                raise serializers.ValidationError({field: ["Provide a JSON object."]})
        headers = attrs.get("custom_headers", getattr(self.instance, "custom_headers", {})) or {}
        sensitive_headers = {
            str(key).strip().casefold() for key in headers
        } & {"authorization", "proxy-authorization", "x-api-key", "api-key"}
        if sensitive_headers:
            raise serializers.ValidationError({
                "custom_headers": [
                    "Store authentication values in the protected Secret / Token field, not custom headers."
                ]
            })
        if company:
            queryset = ErpDeliveryConfig.objects.filter(company=company, branch=branch)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                label = branch.code if branch else "company-central"
                raise serializers.ValidationError({
                    "branch": [f"An active ERP delivery configuration already exists for {label} scope."]
                })
        return attrs

    def update(self, instance, validated_data):
        clear_token = validated_data.pop("clear_token", False)
        token = validated_data.get("auth_token")
        if clear_token:
            validated_data["auth_token"] = ""
        elif token == "":
            validated_data.pop("auth_token")
        return super().update(instance, validated_data)

    def create(self, validated_data):
        validated_data.pop("clear_token", None)
        return super().create(validated_data)
