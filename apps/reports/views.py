from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.documents.compat import to_compat
from apps.documents.models import Document
from apps.company.models import CompanyBranch
from apps.config import services as config_services
from apps.utils.constants import VAT_CATEGORIES
from apps.utils.helpers import csv_export, json_export, sql_export
from apps.utils.openapi import GenericApiSerializer

PENDING_STATUSES = ["DRAFT", "VALIDATED", "PENDING", "SUBMITTED"]


class DashboardView(APIView):
    serializer_class = GenericApiSerializer
    """GET /api/reports/dashboard/ — counts + AR/AP totals for the active tenant scope."""

    def get(self, request):
        qs = Document.objects.filter(company_id__in=request.active_company_ids)
        since_24h = timezone.now() - timedelta(hours=24)

        totals = qs.aggregate(
            ar_total=Sum("tax_inclusive_amount", filter=Q(direction="AR")),
            ap_total=Sum("tax_inclusive_amount", filter=Q(direction="AP")),
        )

        return Response({
            "total_invoices": qs.count(),
            "validated_lt_24h": qs.filter(status="REPORTED", updated_at__gte=since_24h).count(),
            "verified_gt_24h": qs.filter(status="REPORTED", updated_at__lt=since_24h).count(),
            "pending": qs.filter(status__in=PENDING_STATUSES).count(),
            "rejected": qs.filter(status="REJECTED").count(),
            "cancelled": qs.filter(status="CANCELLED").count(),
            "ar_total": float(totals["ar_total"] or 0),
            "ap_total": float(totals["ap_total"] or 0),
            "currency": "OMR",
        })


def _filtered_queryset(request):
    qs = Document.objects.filter(company_id__in=request.active_company_ids).prefetch_related(
        "lines"
    ).select_related("company", "branch")
    params = request.query_params
    if params.get("dir"):
        qs = qs.filter(direction=params["dir"])
    if params.get("status"):
        qs = qs.filter(status=params["status"])
    if params.get("doc_type"):
        qs = qs.filter(doc_type=params["doc_type"])
    if params.get("branch"):
        branch = params["branch"]
        try:
            qs = qs.filter(branch_id=branch)
        except (ValueError, TypeError):
            qs = qs.filter(branch__code__iexact=branch)
    if params.get("date_from"):
        qs = qs.filter(issue_date__gte=params["date_from"])
    if params.get("date_to"):
        qs = qs.filter(issue_date__lte=params["date_to"])
    search = params.get("search")
    if search:
        qs = qs.filter(
            Q(invoice_number__icontains=search) | Q(counterparty_name__icontains=search)
            | Q(counterparty_vatin__icontains=search))
    return qs


def _grid_row(document) -> dict:
    compat_row = to_compat(document)
    return {
        "id": compat_row["id"],
        "invoice_number": compat_row["n"],
        "date": compat_row["d"],
        "time": compat_row["t"],
        "direction": document.direction,
        "type": compat_row["type"],
        "counterparty": compat_row["cp"],
        "counterparty_vatin": compat_row["cpv"],
        "net": compat_row["net"],
        "vat": compat_row["vat"],
        "total": round(compat_row["net"] + compat_row["vat"], 3),
        "status": compat_row["st"],
        "tdd": compat_row["tdd"],
        "error": compat_row["err"],
        "uuid": compat_row["uuid"],
        "company_id": str(document.company_id),
        "company_name": document.company.name_en,
        "company_vatin": document.company.vat_number,
        "branch_id": str(document.branch_id) if document.branch_id else None,
        "branch_code": document.branch.code if document.branch_id else "UNASSIGNED",
        "branch_name": document.branch.name if document.branch_id else "Company default / unassigned",
    }


class TaxGridView(APIView):
    serializer_class = GenericApiSerializer
    """GET /api/reports/tax-grid/ — invoice rows for the Standard Tax Report Data Grid."""

    def get(self, request):
        qs = _filtered_queryset(request)
        return Response([_grid_row(d) for d in qs])


class BranchSummaryView(APIView):
    serializer_class = GenericApiSerializer
    """GET /api/reports/branch-summary — totals by operational branch, not legal entity."""

    def get(self, request):
        documents = _filtered_queryset(request)
        branches = CompanyBranch.objects.filter(
            company_id__in=request.active_company_ids, is_active=True
        ).select_related("company")
        rows = []
        for branch in branches:
            totals = documents.filter(branch=branch).aggregate(
                document_count=Count("id"), net=Sum("tax_exclusive_amount"),
                vat=Sum("tax_amount"), total=Sum("tax_inclusive_amount"),
            )
            rows.append({
                "branch_id": str(branch.id), "branch_code": branch.code,
                "branch_name": branch.name, "company_id": str(branch.company_id),
                "company_name": branch.company.name_en,
                "company_vatin": branch.company.vat_number,
                "document_count": totals["document_count"] or 0,
                "net": float(totals["net"] or 0), "vat": float(totals["vat"] or 0),
                "total": float(totals["total"] or 0),
            })

        unassigned = documents.filter(branch__isnull=True).aggregate(
            document_count=Count("id"), net=Sum("tax_exclusive_amount"),
            vat=Sum("tax_amount"), total=Sum("tax_inclusive_amount"),
        )
        if unassigned["document_count"]:
            rows.append({
                "branch_id": None, "branch_code": "UNASSIGNED",
                "branch_name": "Company default / unassigned", "company_id": None,
                "company_name": "Multiple / company default", "company_vatin": "",
                "document_count": unassigned["document_count"],
                "net": float(unassigned["net"] or 0), "vat": float(unassigned["vat"] or 0),
                "total": float(unassigned["total"] or 0),
            })
        return Response(rows)


class TaxGridExportView(APIView):
    serializer_class = GenericApiSerializer
    """GET /api/reports/tax-grid/export/?format=csv"""

    def get(self, request):
        qs = _filtered_queryset(request)
        rows = [_grid_row(d) for d in qs]
        config_services.log(request, "ARCHIVE_EXPORT_REQUEST", entity="DocumentArchive", detail={
            "date_from": request.query_params.get("date_from"),
            "date_to": request.query_params.get("date_to"),
            "purpose": request.query_params.get("purpose", "Regulatory audit / internal review"),
            "row_count": len(rows),
        })
        fieldnames = ["invoice_number", "date", "type", "company_name", "company_vatin",
                      "branch_code", "branch_name", "counterparty", "counterparty_vatin",
                      "net", "vat", "total", "status", "tdd"]
        return csv_export("tax-grid.csv", fieldnames, rows)


class ArchiveExportView(APIView):
    serializer_class = GenericApiSerializer
    """GET /api/reports/archive/export?date_from=&date_to=&format=csv|json|sql|pgdump&purpose= —
    export over the full retained history (up to 10 years back), for the Reports & Archive UI's
    archive/backup controls. `pgdump` is served as the same tenant-scoped SQL INSERT statements as
    `sql` (see apps.utils.helpers.sql_export) — a literal pg_dump has no per-tenant/date filtering
    and would risk exporting other tenants' data, so it is not used here."""

    MAX_YEARS_BACK = 10
    FIELDNAMES = ["invoice_number", "date", "time", "direction", "type", "company_name",
                  "company_vatin", "branch_code", "branch_name", "counterparty",
                  "counterparty_vatin", "net", "vat", "total", "status", "tdd", "uuid"]

    def get(self, request):
        today = timezone.localdate()
        earliest_allowed = today.replace(year=today.year - self.MAX_YEARS_BACK)
        date_from = request.query_params.get("date_from") or earliest_allowed.isoformat()
        date_to = request.query_params.get("date_to") or today.isoformat()
        if date_from < earliest_allowed.isoformat():
            date_from = earliest_allowed.isoformat()
        export_format = (request.query_params.get("format") or "csv").lower()

        qs = (Document.objects.filter(company_id__in=request.active_company_ids)
              .filter(issue_date__gte=date_from, issue_date__lte=date_to)
              .prefetch_related("lines").order_by("issue_date"))
        rows = [_grid_row(d) for d in qs]

        config_services.log(
            request, "ARCHIVE_EXPORT", entity="Document", count=len(rows),
            date_from=date_from, date_to=date_to, format=export_format,
            purpose=request.query_params.get("purpose", ""),
        )

        base_name = f"faturathi-archive-{date_from}_to_{date_to}"
        if export_format == "json":
            return json_export(f"{base_name}.json", rows)
        if export_format in ("sql", "pgdump"):
            return sql_export(f"{base_name}.sql", "faturathi_archive", self.FIELDNAMES, rows)
        return csv_export(f"{base_name}.csv", self.FIELDNAMES, rows)


class VatGroupsView(APIView):
    serializer_class = GenericApiSerializer
    """GET/POST /api/vat-groups — VAT RATE CATEGORIES (S 5% / Z 0% / E Exempt), not company groups."""

    def get(self, request):
        return Response(VAT_CATEGORIES)

    def post(self, request):
        # Demo-only: master data is hardcoded; accept the POST but don't persist a new category.
        return Response({**request.data, "status": "Active"}, status=201)
