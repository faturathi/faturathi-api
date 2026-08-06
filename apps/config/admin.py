from django.contrib import admin

from .models import ApiCredential, SystemConfig, SystemLog
from apps.utils.admin_mixins import TenantAdminMixin


@admin.register(SystemConfig)
class SystemConfigAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["company", "country", "base_currency", "mfa_enforced", "allow_user_logins"]


@admin.register(SystemLog)
class SystemLogAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["company", "action", "entity", "user", "created_at"]


@admin.register(ApiCredential)
class ApiCredentialAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["name", "company", "key_prefix", "service_user", "is_active", "last_used_at"]
    readonly_fields = ["key_hash", "key_prefix", "last_used_at"]
