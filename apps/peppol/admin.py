from django.contrib import admin

from .models import Transmission
from apps.utils.admin_mixins import TenantAdminMixin


@admin.register(Transmission)
class TransmissionAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["document", "company", "attempt", "status", "mls_status", "created_at"]
