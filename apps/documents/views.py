import csv
import io
import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView

from apps.config import services as config_services
from apps.config.models import ErpDeliveryConfig
from apps.company.models import CompanyBranch
from apps.peppol import services as peppol_services
from apps.utils.constants import DOCUMENT_TYPE_CATALOG
from apps.utils.permissions import CanOperateDocuments, ResolveActiveCompany, resolve_write_company
from apps.utils.validators import validate_document, validate_ibt_payload
from apps.utils.openapi import GenericApiSerializer, DocumentTypeSerializer

from . import compat
from .models import Document
from .serializers import DocumentSerializer
from .pint_om import refresh_pint_snapshot

try:
    import openpyxl
except ImportError:
    openpyxl = None


# Normalized AP approval-pool states (item 3/1e). `ap_status` was previously free text set only
# by `approve`; this keys it so the GET list filter (used by external ERP/desktop pull clients,
# item 2/4) can reliably select "the approved pool" instead of substring-matching display labels.
AP_STATUS_LABELS = {
    "pending": "Pending Approver Review",
    "approved": "Approved · posted to ERP",
    "query": "On Hold Query",
    "rejected": "Rejected by Approver",
}


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def _resolve_billing_reference(queryset, doc_payload: dict) -> dict:
    """Pops compat's inferred `_billing_reference_number` and, if it matches an existing
    document in scope, wires it up as the real billing_reference FK (best-effort)."""
    reference_number = doc_payload.pop("_billing_reference_number", None)
    if reference_number:
        reference = queryset.filter(invoice_number=reference_number).first()
        if reference:
            doc_payload["billing_reference"] = reference.id
    return doc_payload


def _resolve_branch(company, doc_payload: dict) -> dict:
    """Resolve a branch UUID or branch code within the selected legal company only."""
    branch_value = doc_payload.get("branch")
    if not branch_value:
        doc_payload["branch"] = None
        return doc_payload
    queryset = CompanyBranch.objects.filter(company=company, is_active=True)
    try:
        branch = queryset.filter(pk=branch_value).first()
    except (ValueError, TypeError, DjangoValidationError):
        branch = None
    branch = branch or queryset.filter(code__iexact=str(branch_value).strip()).first()
    if branch is None:
        raise ValidationError({
            "branch": ["Select an active branch belonging to the document's legal company."]
        })
    doc_payload["branch"] = str(branch.id)
    return doc_payload


class InvoiceViewSet(viewsets.ViewSet):
    """/api/invoices — plain-array list, invoice_number-keyed lookups (matches faturathi-ui)."""

    lookup_field = "invoice_number"
    serializer_class = DocumentSerializer
    permission_classes = [ResolveActiveCompany, CanOperateDocuments]
    lookup_value_regex = "[^/]+"

    def get_document(self, value):
        """Accept a stable UUID (preferred) or a slash-free legacy invoice number."""
        qs = self.get_queryset()
        try:
            return qs.get(pk=value)
        except (Document.DoesNotExist, ValueError, TypeError, DjangoValidationError):
            return get_object_or_404(qs, invoice_number=value)

    def get_queryset(self):
        return Document.objects.filter(
            company_id__in=getattr(self.request, "active_company_ids", [])
        ).prefetch_related("lines", "transmissions").select_related(
            "company", "branch", "billing_reference"
        )

    # -- CRUD -----------------------------------------------------------

    def list(self, request):
        qs = self.get_queryset()
        direction = request.query_params.get("dir")
        if direction:
            qs = qs.filter(direction=direction)
        status_param = request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        doc_type = request.query_params.get("doc_type")
        if doc_type:
            qs = qs.filter(doc_type=doc_type)
        branch = request.query_params.get("branch")
        if branch:
            try:
                qs = qs.filter(branch_id=branch)
            except (ValueError, TypeError, DjangoValidationError):
                qs = qs.filter(branch__code__iexact=branch)
        ap_status = request.query_params.get("ap_status")
        if ap_status:
            label = AP_STATUS_LABELS.get(ap_status.lower())
            qs = qs.filter(ap_status=label) if label else qs.filter(ap_status__icontains=ap_status)
        cpv = request.query_params.get("cpv") or request.query_params.get("counterparty_vatin")
        if cpv:
            qs = qs.filter(counterparty_vatin=cpv)
        cr_number = request.query_params.get("cr_number")
        if cr_number:
            qs = qs.filter(company__cr_number=cr_number)
        uuid_param = request.query_params.get("uuid")
        if uuid_param:
            qs = qs.filter(uuid_v5=uuid_param) if _is_uuid(uuid_param) else qs.none()
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(invoice_number__icontains=search) | Q(counterparty_name__icontains=search)
                | Q(counterparty_vatin__icontains=search))
        return Response([compat.to_compat(d) for d in qs])

    def retrieve(self, request, invoice_number=None):
        doc = self.get_document(invoice_number)
        return Response(compat.to_compat(doc))

    @action(detail=True, methods=["get"], url_path="pint-payload")
    def pint_payload(self, request, invoice_number=None):
        """Canonical OTA JSON used for audit, export, Peppol and diagnostics."""
        doc = self.get_document(invoice_number)
        refresh_pint_snapshot(doc)
        doc.refresh_from_db(fields=["extra_data"])
        return Response(doc.extra_data.get("pint_om", {}))

    def create(self, request):
        company = resolve_write_company(request, request.data)
        requested_direction = request.data.get("dir_internal") or request.data.get("direction")
        if not requested_direction:
            requested_direction = "AP" if request.data.get("document_type") in ("SELF_BILLED_389", "SELF_BILLED_CN_261") else "AR"
        doc_payload = compat.build_document_payload(request.data, direction=requested_direction)
        doc_payload = _resolve_branch(company, doc_payload)
        invoice_number = doc_payload.get("invoice_number", "")
        if Document.objects.filter(
            company=company, invoice_number=invoice_number, is_deleted=False
        ).exists():
            raise ValidationError({
                "invoice_number": [
                    f'Document number "{invoice_number}" already exists for {company.name_en}. '
                    "Use the next number in the company numbering series."
                ]
            })
        reference_number = request.data.get("billingReferenceNumber")
        if reference_number:
            reference = get_object_or_404(self.get_queryset(), invoice_number=reference_number)
            doc_payload["billing_reference"] = reference.id
            doc_payload.pop("_billing_reference_number", None)
        else:
            doc_payload = _resolve_billing_reference(self.get_queryset(), doc_payload)
        serializer = DocumentSerializer(data=doc_payload)
        serializer.is_valid(raise_exception=True)
        try:
            # Document, nested lines, PINT snapshot and audit log are one operation. A failure in
            # any step must not leave a document saved while the client receives an error.
            with transaction.atomic():
                document = serializer.save(
                    company=company, created_by=request.user, direction=requested_direction
                )
                type(company).objects.filter(pk=company.pk).update(
                    next_invoice_number=F("next_invoice_number") + 1
                )
                if document.branch_id:
                    CompanyBranch.objects.filter(pk=document.branch_id).update(
                        next_invoice_number=F("next_invoice_number") + 1
                    )
                config_services.log(
                    request, "INVOICE_CREATE", entity="Document", entity_id=document.invoice_number
                )
        except IntegrityError as exc:
            if "uniq_invoice_no_per_company" in str(exc):
                raise ValidationError({
                    "invoice_number": [
                        f'Document number "{invoice_number}" already exists for {company.name_en}.'
                    ]
                }) from exc
            raise
        return Response(compat.to_compat(document), status=status.HTTP_201_CREATED)

    def partial_update(self, request, invoice_number=None):
        doc = self.get_document(invoice_number)
        if doc.status not in ("DRAFT", "REJECTED", "PENDING"):
            return Response({"detail": "Only draft/pending/rejected invoices can be edited."},
                             status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        doc_payload = compat.build_document_payload(request.data, direction=doc.direction)
        if any(key in request.data for key in ("branch", "branch_id", "branchId")):
            doc_payload = _resolve_branch(doc.company, doc_payload)
        else:
            doc_payload.pop("branch", None)
        doc_payload.pop("invoice_number", None)  # invoice number stays fixed on edit
        doc_payload = _resolve_billing_reference(self.get_queryset(), doc_payload)
        serializer = DocumentSerializer(doc, data=doc_payload, partial=True)
        serializer.is_valid(raise_exception=True)
        document = serializer.save()
        config_services.log(request, "INVOICE_UPDATE", entity="Document", entity_id=document.invoice_number)
        return Response(compat.to_compat(document))

    def destroy(self, request, invoice_number=None):
        doc = self.get_document(invoice_number)
        doc.soft_delete()
        config_services.log(request, "INVOICE_DELETE", entity="Document", entity_id=invoice_number)
        return Response({"status": "deleted", "id": invoice_number})

    # -- lifecycle actions ------------------------------------------------

    @action(detail=True, methods=["post"])
    def validate(self, request, invoice_number=None):
        doc = self.get_document(invoice_number)
        errors = validate_document(doc)
        return Response({"valid": not errors, "errors": errors})

    @action(detail=True, methods=["post"])
    def submit(self, request, invoice_number=None):
        doc = self.get_document(invoice_number)
        peppol_services.submit_document(doc, request.user)
        config_services.log(request, "INVOICE_SUBMIT", entity="Document",
                             entity_id=doc.invoice_number, status=doc.status)
        return Response(compat.to_compat(doc))

    @action(detail=True, methods=["post"])
    def resubmit(self, request, invoice_number=None):
        doc = self.get_document(invoice_number)
        cpv = request.data.get("cpv")
        if cpv:
            doc.counterparty_vatin = cpv
            doc.counterparty_endpoint = f"0248:{cpv}"
        if request.data.get("net") is not None:
            doc.tax_exclusive_amount = Decimal(str(request.data["net"]))
        if request.data.get("vat") is not None:
            doc.tax_amount = Decimal(str(request.data["vat"]))
        doc.tax_inclusive_amount = doc.tax_exclusive_amount + doc.tax_amount
        doc.payable_amount = doc.tax_inclusive_amount
        doc.save(update_fields=["counterparty_vatin", "counterparty_endpoint",
                                 "tax_exclusive_amount", "tax_amount",
                                 "tax_inclusive_amount", "payable_amount"])

        peppol_services.resubmit_document(doc, request.user)
        config_services.log(request, "INVOICE_RESUBMIT", entity="Document",
                             entity_id=doc.invoice_number, status=doc.status)
        invoice = compat.to_compat(doc)
        if doc.status == "REJECTED":
            latest_transmission = doc.transmissions.order_by("-created_at").first()
            return Response({
                "status": "rejected",
                "message": "Re-submission failed PINT-OM validation rules.",
                "error": invoice["err"],
                "errors": latest_transmission.validation_errors if latest_transmission else [],
                "invoice": invoice,
            }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        return Response({
            "status": "resubmitted",
            "message": "Invoice re-submitted successfully to Oman Tax Authority C5 clearance and cleared.",
            "invoice": invoice,
        })

    @action(detail=True, methods=["post"])
    def approve(self, request, invoice_number=None):
        doc = self.get_document(invoice_number)
        if doc.direction != "AP":
            raise ValidationError({"document": ["Only inbound/AP documents can be approved for ERP posting."]})
        if doc.ap_status == AP_STATUS_LABELS["approved"]:
            return Response(compat.to_compat(doc))
        if doc.ap_status == AP_STATUS_LABELS["rejected"]:
            raise ValidationError({"status": ["A rejected AP document must be corrected before approval."]})
        targets = ErpDeliveryConfig.objects.filter(company=doc.company, is_active=True)
        delivery_target = targets.filter(branch_id=doc.branch_id).first() if doc.branch_id else None
        if delivery_target is None:
            delivery_target = targets.filter(branch__isnull=True).first()
        extra_data = dict(doc.extra_data or {})
        extra_data["erp_delivery"] = {
            "status": "CONFIGURED_FOR_DELIVERY" if delivery_target else "CONFIGURATION_REQUIRED",
            "configuration_id": str(delivery_target.id) if delivery_target else None,
            "configuration_name": delivery_target.name if delivery_target else None,
            "scope": delivery_target.branch.code if delivery_target and delivery_target.branch_id else "COMPANY",
        }
        doc.ap_status = AP_STATUS_LABELS["approved"]
        doc.erp_system = delivery_target.name if delivery_target else doc.erp_system
        doc.extra_data = extra_data
        doc.save(update_fields=["ap_status", "erp_system", "extra_data"])
        config_services.log(
            request, "AP_APPROVE", entity="Document", entity_id=doc.invoice_number,
            erp_delivery=extra_data["erp_delivery"],
        )
        payload = compat.to_compat(doc)
        payload["erpDelivery"] = extra_data["erp_delivery"]
        return Response(payload)

    @action(detail=True, methods=["post"])
    def reject(self, request, invoice_number=None):
        doc = self.get_document(invoice_number)
        doc.ap_status = AP_STATUS_LABELS["rejected"]
        doc.status = "REJECTED"
        note = request.data.get("notes") or request.data.get("reason")
        if note:
            doc.notes = note
            doc.save(update_fields=["ap_status", "status", "notes"])
        else:
            doc.save(update_fields=["ap_status", "status"])
        config_services.log(request, "AP_REJECT", entity="Document", entity_id=doc.invoice_number)
        return Response({"status": "rejected", "id": invoice_number, "ap_status": doc.ap_status})

    @action(detail=True, methods=["post"])
    def query(self, request, invoice_number=None):
        doc = self.get_document(invoice_number)
        doc.ap_status = AP_STATUS_LABELS["query"]
        note = request.data.get("notes") or request.data.get("reason")
        if note:
            doc.notes = note
            doc.save(update_fields=["ap_status", "notes"])
        else:
            doc.save(update_fields=["ap_status"])
        config_services.log(request, "AP_QUERY", entity="Document", entity_id=doc.invoice_number)
        return Response({"status": "query", "id": invoice_number, "ap_status": doc.ap_status})

    @action(detail=True, methods=["post"])
    def cancel(self, request, invoice_number=None):
        doc = self.get_document(invoice_number)
        reference_note = request.data.get("reference_note") or request.data.get("cn")
        if not reference_note:
            return Response({"detail": "A credit-note reference note is required to cancel."},
                             status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        doc.status = "CANCELLED"
        doc.notes = reference_note
        doc.save(update_fields=["status", "notes"])
        config_services.log(request, "INVOICE_CANCEL", entity="Document", entity_id=doc.invoice_number)
        return Response(compat.to_compat(doc))

    # -- AP inbound simulation (Postman demo) -----------------------------

    @action(detail=False, methods=["post"], url_path="inbound")
    def inbound(self, request):
        return self._create_inbound(request)

    @action(detail=False, methods=["post"], url_path="ap")
    def ap_alias(self, request):
        return self._create_inbound(request)

    def _create_inbound(self, request):
        payload = request.data
        company = resolve_write_company(request, request.data)
        doc_payload = compat.build_document_payload(payload, direction="AP")
        doc_payload = _resolve_branch(company, doc_payload)
        doc_payload = _resolve_billing_reference(self.get_queryset(), doc_payload)
        serializer = DocumentSerializer(data=doc_payload)
        serializer.is_valid(raise_exception=True)
        document = serializer.save(
            company=company, created_by=request.user, direction="AP", source="AP_INBOUND",
            ap_status="Pending Approver Review",
            erp_system=payload.get("erpSystem", "Postman / External ERP (AP Inbound)"),
        )
        peppol_services.submit_document(document, request.user, force_status="TDD_REPORTED")
        config_services.log(request, "INVOICE_INBOUND_AP", entity="Document", entity_id=document.invoice_number)
        return Response({
            "status": "created",
            "message": "Inbound AP invoice received, validated via AS4/PINT-OM C3 leg, and queued for AP approval.",
            "invoiceNumber": document.invoice_number,
            "invoice": compat.to_compat(document),
        }, status=status.HTTP_201_CREATED)


class BatchUploadView(APIView):
    serializer_class = GenericApiSerializer
    permission_classes = [ResolveActiveCompany, CanOperateDocuments]
    """POST /api/upload-batch {items:[...]} — loop create+submit (JSON body)."""

    def post(self, request):
        items = request.data.get("items") if isinstance(request.data, dict) else request.data
        items = items or []
        company = resolve_write_company(request, request.data)
        queryset = Document.objects.filter(company_id__in=request.active_company_ids)
        created, errors = _create_documents_from_rows(
            items, company, request.user, queryset, source="BATCH", erp_default="File Upload (JSON)")
        config_services.log(request, "INVOICE_BATCH_UPLOAD", entity="Document",
                             count=len(created), error_count=len(errors))
        return Response({"status": "success" if not errors else "partial",
                          "count": len(created), "created": created, "errors": errors})


def _create_documents_from_rows(rows, company, user, queryset, source: str, erp_default: str):
    """Shared create+submit loop for JSON batch upload and CSV/XLSX file upload."""
    created, errors = [], []
    for idx, item in enumerate(rows, start=1):
        try:
            direction = item.get("dir_internal") or item.get("dir") or item.get("direction") or "AR"
            doc_payload = compat.build_document_payload(item, direction=direction)
            doc_payload = _resolve_branch(company, doc_payload)
            doc_payload = _resolve_billing_reference(queryset, doc_payload)
            doc_payload.setdefault("erp_system", "")
            doc_payload["erp_system"] = doc_payload["erp_system"] or erp_default
            serializer = DocumentSerializer(data=doc_payload)
            serializer.is_valid(raise_exception=True)
            document = serializer.save(company=company, created_by=user, direction=direction, source=source)
            transmission = peppol_services.submit_document(document, user)
            result = compat.to_compat(document)
            created.append(result)
            if document.status == "REJECTED":
                errors.append({
                    "row": idx,
                    "invoice_number": document.invoice_number,
                    "document_id": str(document.id),
                    "errors": transmission.validation_errors,
                    "error": "; ".join(error.get("message", str(error)) for error in transmission.validation_errors),
                })
        except Exception as exc:
            errors.append({"row": idx, "invoice_number": item.get("n") or item.get("invoice_number"),
                            "error": str(exc)})
    return created, errors


def _group_flat_rows(rows: list[dict]) -> list[dict]:
    """Combine repeated flat CSV/XLSX rows into one document with nested line tuples."""
    grouped: dict[str, dict] = {}
    for index, row in enumerate(rows, start=1):
        number = (row.get("invoice_number") or row.get("IBT_001_InvoiceNumber")
                  or row.get("n") or f"__row_{index}")
        if number not in grouped:
            grouped[number] = dict(row)
            grouped[number]["lines"] = []
            grouped[number]["extra_data"] = {"ingested_rows": []}
        grouped[number]["extra_data"]["ingested_rows"].append(dict(row))
        item_name = row.get("item_name") or row.get("IBT_153_ItemName")
        if item_name:
            grouped[number]["lines"].append([
                item_name,
                row.get("quantity") or row.get("IBT_129_InvoicedQuantity") or 1,
                row.get("unit_price") or row.get("IBT_146_ItemNetPrice") or 0,
                row.get("vat_category") or row.get("IBT_151_ItemVATCategoryCode") or "S",
            ])
    return list(grouped.values())


class DocumentTypeCatalogView(APIView):
    serializer_class = DocumentTypeSerializer
    """GET /api/document-types — the 6-tile document type selector (Standard/Simplified/CN/DN/
    Self-Billed/Self-Billed CN), for the Quick Document Creator UI."""

    def get(self, request):
        return Response(DOCUMENT_TYPE_CATALOG)


class BatchFileUploadView(APIView):
    serializer_class = GenericApiSerializer
    permission_classes = [ResolveActiveCompany, CanOperateDocuments]
    """POST /api/upload-batch/file — multipart CSV or XLSX upload (field name 'file').
    Same create+submit pipeline as JSON batch upload; see sample_data/ for column layout."""

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response({"detail": "No file uploaded. Use multipart form field 'file'."},
                             status=status.HTTP_400_BAD_REQUEST)
        try:
            rows = _group_flat_rows(self._parse_rows(file_obj))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:  # corrupt/mismatched file content (bad zip, decode errors, ...)
            return Response(
                {"detail": f"'{file_obj.name}' could not be read: {exc}. "
                            "Check that the file is a genuine, uncorrupted .csv or .xlsx export."},
                status=status.HTTP_400_BAD_REQUEST)

        company = resolve_write_company(request, {})
        queryset = Document.objects.filter(company_id__in=request.active_company_ids)
        created, errors = _create_documents_from_rows(
            rows, company, request.user, queryset, source="BATCH",
            erp_default=f"File Upload ({file_obj.name})")
        config_services.log(request, "INVOICE_FILE_UPLOAD", entity="Document",
                             filename=file_obj.name, count=len(created), error_count=len(errors))
        return Response({"status": "success" if not errors else "partial",
                          "count": len(created), "created": created, "errors": errors})

    def _parse_rows(self, file_obj) -> list[dict]:
        name = (file_obj.name or "").lower()
        if name.endswith(".xlsx"):
            if openpyxl is None:
                raise ValueError("Server is missing the openpyxl package required to read .xlsx files.")
            header = file_obj.read(4)
            file_obj.seek(0)
            if header[:2] != b"PK":
                raise ValueError(
                    f"'{file_obj.name}' does not look like a real .xlsx file (wrong file signature) "
                    "— it may be renamed from a different file type. Re-export a genuine Excel file, "
                    "or upload .csv instead.")
            workbook = openpyxl.load_workbook(file_obj, data_only=True)
            sheet = workbook.active
            rows_iter = sheet.iter_rows(values_only=True)
            headers = [str(h).strip() if h is not None else "" for h in next(rows_iter, [])]
            rows = []
            for values in rows_iter:
                if all(v in (None, "") for v in values):
                    continue
                rows.append({headers[i]: values[i] for i in range(len(headers)) if i < len(values)})
            return rows

        if not name.endswith(".csv"):
            raise ValueError(f"Unsupported file type for '{file_obj.name}'. Upload a .csv or .xlsx file.")
        try:
            text = file_obj.read().decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"'{file_obj.name}' is not readable text — it looks like a binary file, not CSV."
            ) from exc
        if "\x00" in text:
            raise ValueError(f"'{file_obj.name}' contains binary data and is not a valid CSV file.")
        reader = csv.DictReader(io.StringIO(text))
        return [row for row in reader if any((v or "").strip() for v in row.values() if v is not None)]


class ValidateOmanView(APIView):
    serializer_class = GenericApiSerializer
    permission_classes = [ResolveActiveCompany, CanOperateDocuments]
    """POST /api/validate (alias /api/validate-oman) — IBT-named payload, persists as Reported/Rejected."""

    def post(self, request):
        raw = request.data
        result = validate_ibt_payload(raw)

        seller = raw.get("SellerDetails") or {}
        buyer = raw.get("BuyerDetails") or {}
        totals = raw.get("Totals") or {}
        lines = raw.get("Lines") or []

        company = resolve_write_company(request, request.data)
        invoice_number = raw.get("IBT_001_InvoiceNumber") or f"API-INV-{Document.objects.count() + 1000}"
        code = str(raw.get("IBT_003_InvoiceTypeCode") or "380")
        type_by_code = {"380": "SIMPLIFIED_B2C" if result["isSimplified"] else "STANDARD_380",
                        "381": "CREDIT_NOTE_381", "383": "DEBIT_NOTE_383",
                        "389": "SELF_BILLED_389", "261": "SELF_BILLED_CN_261"}
        direction = "AP" if type_by_code.get(code) in ("SELF_BILLED_389", "SELF_BILLED_CN_261") else "AR"
        doc_payload = {
            "direction": direction,
            "document_type": type_by_code.get(code, "STANDARD_380"),
            "invoice_number": invoice_number,
            "issue_date": raw.get("IBT_002_InvoiceIssueDate"),
            "issue_time": raw.get("IBT_168_InvoiceIssueTime") or "12:00:00",
            "transaction_type_code": raw.get("BTOM_001_OmanTransactionType") or "10000000000000000000",
            "counterparty_name": (
                seller.get("IBT_027_SellerName") if direction == "AP"
                else buyer.get("IBT_044_BuyerName")
            ) or ("Cash Customer" if result["isSimplified"] else ""),
            "counterparty_vatin": (
                seller.get("IBT_031_SellerVATIdentifier") if direction == "AP"
                else buyer.get("IBT_048_BuyerVATIdentifier")
            ) or "",
            "counterparty_endpoint": (
                seller.get("IBT_034_SellerElectronicAddress") if direction == "AP"
                else buyer.get("IBT_049_BuyerElectronicAddress")
            ) or "",
            "currency": "OMR",
            "payment_means_code": "30",
            "payment_iban": raw.get("PaymentDetails", {}).get("IBT_084_PaymentAccountIdentifier")
                            or "OM810180000000000000123",
            "status": "PENDING",
            "erp_system": "REST API / Postman Ingestion",
            "source": "REST_API",
            # Full ingested IBT-named payload (seller/buyer addresses, allowances, GTIN, delivery,
            # PaymentDetails, ...) — kept verbatim since only a subset is promoted to real columns.
            "extra_data": {"ingested_payload": raw},
            "branch": raw.get("branch_id") or raw.get("branchId") or raw.get("branch"),
            "lines": [
                {
                    "line_id": idx,
                    "item_name": line.get("IBT_153_ItemName", "PINT-OM Service Line"),
                    "quantity": line.get("IBT_129_InvoicedQuantity", 1),
                    "unit_code": line.get("IBT_130_QuantityUnitCode", "EA"),
                    "unit_price": line.get("IBT_146_ItemNetPrice", totals.get("IBT_109_InvoiceTotalNetAmount", 100)),
                    "discount": line.get("IBT_149_ItemPriceDiscount", 0),
                    "vat_category": line.get("IBT_151_ItemVATCategoryCode", "S"),
                    "vat_rate": line.get("IBT_152_ItemVATRate", 5),
                }
                for idx, line in enumerate(lines or [{}], start=1)
            ],
        }
        doc_payload = _resolve_branch(company, doc_payload)
        doc_payload["_billing_reference_number"] = raw.get("BillingReference") or raw.get("billing_reference")
        doc_payload = _resolve_billing_reference(self.get_queryset(), doc_payload)
        serializer = DocumentSerializer(data=doc_payload)
        serializer.is_valid(raise_exception=True)
        document = serializer.save(company=company, created_by=request.user, direction=direction)
        refresh_pint_snapshot(document, raw)

        if result["isValid"]:
            peppol_services.submit_document(document, request.user)
        else:
            document.status = "REJECTED"
            document.save(update_fields=["status"])

        config_services.log(request, "INVOICE_VALIDATE_API", entity="Document",
                             entity_id=document.invoice_number, is_valid=result["isValid"])
        invoice = compat.to_compat(document)
        body = {
            "isValid": result["isValid"],
            "status": "created" if result["isValid"] else "rejected",
            "message": ("Invoice validated successfully and created in Faturathi system."
                        if result["isValid"] else
                        "Invoice failed PINT-OM validation rules and was stored in the Rejected register."),
            "invoiceNumber": document.invoice_number,
            "invoice": invoice,
            "rejectionReasons": result["errors"],
            "warnings": result["warnings"],
            "uuidV5Generated": invoice["uuid"],
        }
        return Response(body, status=status.HTTP_200_OK if result["isValid"] else status.HTTP_422_UNPROCESSABLE_ENTITY)


class LegacyRequestsView(APIView):
    serializer_class = GenericApiSerializer
    """GET /api/requests — backwards-compat alias for the plain invoice list."""

    def get(self, request):
        qs = Document.objects.filter(company_id__in=request.active_company_ids)
        return Response([compat.to_compat(d) for d in qs])


class LegacyReceiveView(APIView):
    serializer_class = GenericApiSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        return Response({"status": "received", "message": "Invoice queued for PINT OM validation & TDD dispatch"})
