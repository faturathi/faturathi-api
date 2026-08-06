from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Notification, User
from apps.utils.admin_mixins import TenantAdminMixin


class UserAdmin(DjangoUserAdmin):
    model = User
    ordering = ["email"]
    list_display = ["email", "role", "company", "is_staff", "is_active"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("first_name", "last_name", "company", "role", "designation", "branch", "phone", "mfa_enabled")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2", "role")}),
    )
    search_fields = ["email"]


admin.site.register(User, UserAdmin)

@admin.register(Notification)
class NotificationAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["company", "user", "title", "level", "is_read", "created_at"]
