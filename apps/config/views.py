from django.core.management import call_command
import hashlib
import secrets
from django_filters import rest_framework as df_filters
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from . import services
from .models import ApiCredential, SystemConfig, SystemLog
from .serializers import SystemConfigSerializer, SystemLogSerializer
from apps.utils.permissions import IsPlatformAdmin, IsTenantAdministrator, ResolveActiveCompany, resolve_write_company
from apps.utils.openapi import GenericApiSerializer
from apps.user.models import User


class SystemConfigView(generics.RetrieveUpdateAPIView):
    serializer_class = SystemConfigSerializer
    permission_classes = [ResolveActiveCompany, IsTenantAdministrator]

    def get_object(self):
        company = resolve_write_company(self.request, self.request.data)
        obj, _ = SystemConfig.objects.get_or_create(company=company, defaults={"created_by": self.request.user})
        return obj

    def perform_update(self, serializer):
        serializer.save()
        services.log(self.request, "CONFIG_UPDATE", entity="SystemConfig", entity_id=serializer.instance.id)


class SystemLogFilter(df_filters.FilterSet):
    date_from = df_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    date_to = df_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = SystemLog
        fields = ["action", "entity", "date_from", "date_to"]


class SystemLogListView(generics.ListAPIView):
    serializer_class = SystemLogSerializer
    filterset_class = SystemLogFilter

    def get_queryset(self):
        return SystemLog.objects.filter(company_id__in=getattr(self.request, "active_company_ids", []))


class ApiCredentialView(APIView):
    """Provision company-scoped machine credentials. Raw secrets are returned once on POST."""

    permission_classes = [ResolveActiveCompany, IsTenantAdministrator]
    serializer_class = GenericApiSerializer

    def get(self, request):
        rows = ApiCredential.objects.filter(company_id__in=request.active_company_ids).select_related("company")
        return Response([{
            "id": str(row.id), "name": row.name, "org": row.company.name_en,
            "apiKey": f"{row.key_prefix}••••••••", "bearerToken": "",
            "createdAt": row.created_at.date().isoformat(), "lastUsedAt": row.last_used_at,
        } for row in rows])

    def post(self, request):
        company = resolve_write_company(request, request.data)
        name = str(request.data.get("name", "")).strip()
        if not name:
            return Response({"name": ["Connector name is required."]}, status=400)

        raw_key = f"fat_live_{secrets.token_urlsafe(24)}"
        service_user = User.objects.create_user(
            email=f"api-{secrets.token_hex(8)}@service.faturathi.local",
            password=secrets.token_urlsafe(32), company=company, role="MAKER",
            first_name=name, designation="API Connector",
        )
        credential = ApiCredential.objects.create(
            company=company, name=name, key_prefix=raw_key[:20],
            key_hash=hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
            service_user=service_user, scopes=["invoices:read", "invoices:write"],
            created_by=request.user,
        )
        refresh = RefreshToken.for_user(service_user)
        return Response({
            "id": str(credential.id), "name": credential.name, "org": company.name_en,
            "apiKey": raw_key, "bearerToken": str(refresh.access_token),
            "refreshToken": str(refresh), "createdAt": credential.created_at.date().isoformat(),
            "warning": "Copy these secrets now. The API key cannot be retrieved again.",
        }, status=201)


class ResetSeedsView(APIView):
    """POST /api/config/reset-seeds/ (aliased at /api/reset-db, /api/clear) — wipes + reseeds demo data."""

    permission_classes = [IsPlatformAdmin]
    serializer_class = GenericApiSerializer

    def post(self, request):
        from django.conf import settings
        if not settings.ALLOW_SEED_RESET:
            return Response({"detail": "Seed reset is disabled in this environment."}, status=403)
        call_command("seed_demo")
        return Response({"status": "reset_success"})
