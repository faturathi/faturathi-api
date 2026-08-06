from rest_framework import viewsets

from apps.utils.mixins import TenantQuerysetMixin
from apps.utils.permissions import IsPlatformAdmin, IsTenantAdministrator, ResolveActiveCompany

from .models import Company, CompanyGroup, Customer
from .serializers import CompanyGroupSerializer, CustomerSerializer, EntitySerializer


class EntityViewSet(viewsets.ModelViewSet):
    """/api/entities — legal entities (Companies) in the caller's VAT group."""

    serializer_class = EntitySerializer
    permission_classes = [ResolveActiveCompany, IsTenantAdministrator]

    def get_queryset(self):
        own_company = getattr(self.request.user, "company", None)
        qs = Company.objects.filter(is_active=True)
        if own_company is not None and own_company.company_group_id:
            qs = qs.filter(company_group_id=own_company.company_group_id)
        elif own_company is not None:
            qs = qs.filter(pk=own_company.pk)
        return qs

    def perform_create(self, serializer):
        own_company = getattr(self.request.user, "company", None)
        serializer.save(
            company_group_id=getattr(own_company, "company_group_id", None),
            created_by=self.request.user,
        )

    def perform_destroy(self, instance):
        instance.soft_delete()


class CustomerViewSet(TenantQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = CustomerSerializer
    filterset_fields = ["is_walkin"]
    search_fields = ["name", "vatin"]
    permission_classes = [ResolveActiveCompany, IsTenantAdministrator]

    def get_queryset(self):
        return Customer.objects.filter(company_id__in=getattr(self.request, "active_company_ids", []))

    def perform_destroy(self, instance):
        instance.soft_delete()


class CompanyGroupViewSet(viewsets.ModelViewSet):
    """Our own company-group lookup. NOTE: /api/vat-groups is reserved for VAT rate
    categories (see apps.utils.constants.VAT_CATEGORIES / reports app), not this model."""

    serializer_class = CompanyGroupSerializer
    permission_classes = [ResolveActiveCompany, IsTenantAdministrator]

    def get_queryset(self):
        own_company = getattr(self.request.user, "company", None)
        if own_company and own_company.company_group_id:
            return CompanyGroup.objects.filter(pk=own_company.company_group_id)
        if IsPlatformAdmin().has_permission(self.request, self):
            return CompanyGroup.objects.all()
        return CompanyGroup.objects.none()

    def perform_create(self, serializer):
        if not IsPlatformAdmin().has_permission(self.request, self):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only a platform administrator can create a business group.")
        serializer.save(created_by=self.request.user)
