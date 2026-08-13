from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.utils.mixins import TenantQuerysetMixin
from apps.utils.permissions import IsPlatformAdmin, IsTenantAdministrator, ResolveActiveCompany, resolve_write_company

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
        elif IsPlatformAdmin().has_permission(self.request, self):
            group_id = self.request.headers.get("X-Business-Group-ID")
            if group_id:
                qs = qs.filter(company_group__isnull=True) if group_id == "standalone" else qs.filter(company_group_id=group_id)
        return qs

    def perform_create(self, serializer):
        own_company = getattr(self.request.user, "company", None)
        standalone = bool(self.request.data.get("standalone"))
        platform_admin = IsPlatformAdmin().has_permission(self.request, self)
        if standalone and not platform_admin:
            raise ValidationError({"standalone": ["Only a platform administrator can create a standalone company."]})
        if platform_admin:
            group = None if standalone else serializer.validated_data.get("company_group")
        else:
            group = getattr(own_company, "company_group", None)
        if not standalone and group is None:
            raise ValidationError({"company_group": ["Select a valid business group before creating a company."]})
        serializer.save(company_group=group, created_by=self.request.user)

    def perform_update(self, serializer):
        platform_admin = IsPlatformAdmin().has_permission(self.request, self)
        if platform_admin:
            standalone = bool(self.request.data.get("standalone"))
            entity_type = self.request.data.get("entity_type", serializer.instance.entity_type)
            group = None if standalone else serializer.validated_data.get(
                "company_group", serializer.instance.company_group
            )
            if entity_type in {"SUBSIDIARY", "BRANCH"} and group is None:
                raise ValidationError({"company_group": ["Subsidiaries and branches must belong to a business group."]})
            serializer.save(company_group=group)
        else:
            serializer.save(company_group=serializer.instance.company_group)

    def perform_destroy(self, instance):
        instance.soft_delete()


class CustomerViewSet(TenantQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = CustomerSerializer
    filterset_fields = ["is_walkin", "company"]
    search_fields = ["name", "vatin"]
    permission_classes = [ResolveActiveCompany, IsTenantAdministrator]

    def get_queryset(self):
        return Customer.objects.filter(company_id__in=getattr(self.request, "active_company_ids", []))

    def perform_create(self, serializer):
        serializer.save(
            company=resolve_write_company(self.request, self.request.data),
            created_by=self.request.user,
        )

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
        self._require_platform_admin()
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        self._require_platform_admin()
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        self._require_platform_admin()
        instance = self.get_object()
        company_count = instance.companies.filter(is_active=True).count()
        if company_count:
            return Response(
                {
                    "detail": "This business group cannot be deleted while companies belong to it.",
                    "company_count": company_count,
                },
                status=status.HTTP_409_CONFLICT,
            )
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _require_platform_admin(self):
        if not IsPlatformAdmin().has_permission(self.request, self):
            raise PermissionDenied("Only a platform administrator can manage business groups.")
