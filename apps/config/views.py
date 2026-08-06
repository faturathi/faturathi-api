from django.core.management import call_command
from django_filters import rest_framework as df_filters
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import SystemConfig, SystemLog
from .serializers import SystemConfigSerializer, SystemLogSerializer
from apps.utils.permissions import IsPlatformAdmin, IsTenantAdministrator, ResolveActiveCompany, resolve_write_company
from apps.utils.openapi import GenericApiSerializer


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
