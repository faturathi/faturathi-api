from apps.utils.permissions import is_platform_admin


def admin_company_ids(user):
    if is_platform_admin(user):
        return None
    company = getattr(user, "company", None)
    if company is None:
        return []
    if company.company_group_id:
        from apps.company.models import Company
        return list(Company.objects.filter(company_group_id=company.company_group_id).values_list("id", flat=True))
    return [company.id]


class TenantAdminMixin:
    """Apply the same business-group boundary to Django Admin tenant-owned models."""

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        ids = admin_company_ids(request.user)
        return queryset if ids is None else queryset.filter(company_id__in=ids)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        ids = admin_company_ids(request.user)
        if db_field.name == "company" and ids is not None:
            from apps.company.models import Company
            kwargs["queryset"] = Company.objects.filter(id__in=ids)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
