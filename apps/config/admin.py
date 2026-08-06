from django.contrib import admin

from .models import SystemConfig, SystemLog
from apps.utils.admin_mixins import TenantAdminMixin


@admin.register(SystemConfig)
class SystemConfigAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["company", "country", "base_currency", "mfa_enforced", "allow_user_logins"]


@admin.register(SystemLog)
class SystemLogAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["company", "action", "entity", "user", "created_at"]
