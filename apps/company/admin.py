from django.contrib import admin

from .models import Company, CompanyGroup, Customer
from apps.utils.admin_mixins import TenantAdminMixin, admin_company_ids
from apps.utils.permissions import is_platform_admin


@admin.register(CompanyGroup)
class CompanyGroupAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if is_platform_admin(request.user):
            return queryset
        company = getattr(request.user, "company", None)
        return queryset.filter(pk=company.company_group_id) if company and company.company_group_id else queryset.none()


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["short_code", "name_en", "company_group", "vat_number", "is_active"]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        ids = admin_company_ids(request.user)
        return queryset if ids is None else queryset.filter(id__in=ids)


@admin.register(Customer)
class CustomerAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["name", "company", "vatin", "is_walkin"]
