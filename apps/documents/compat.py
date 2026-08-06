"""
Translates between Faturathi's clean internal Document model and faturathi-ui's short-key
JSON contract (see Faturathi_Django_Backend_Architecture.md, Addendum v1.1 section C).
"""

import random
import re
from decimal import Decimal

from django.utils import timezone

from apps.utils.constants import (
    B2C_DUMMY, CN_DN_DOCUMENT_TYPE_KEYS, DOCUMENT_TYPE_BY_KEY, TT_B2C, TT_CREDIT_NOTE,
    TT_STANDARD, VAT_CATEGORIES,
)

_DEFAULT_TT_BY_DOCUMENT_TYPE = {
    "STANDARD_380": TT_STANDARD,
    "SIMPLIFIED_B2C": TT_B2C,
    "CREDIT_NOTE_381": TT_CREDIT_NOTE,
    "DEBIT_NOTE_383": TT_CREDIT_NOTE,
    "SELF_BILLED_389": TT_STANDARD,
    "SELF_BILLED_CN_261": TT_CREDIT_NOTE,
}

VAT_LABEL_BY_CODE = {c["code"]: c["label"] for c in VAT_CATEGORIES}
VAT_RATE_BY_CODE = {c["code"]: Decimal(c["rate"]) for c in VAT_CATEGORIES}

# Free-text "type" fallback for legacy/CSV payloads that don't send a document_type key directly.
_TYPE_LABEL_TO_KEY = [
    ("self-billed credit", "SELF_BILLED_CN_261"),
    ("self-billed invoice", "SELF_BILLED_389"),
    ("credit note", "CREDIT_NOTE_381"),
    ("debit note", "DEBIT_NOTE_383"),
    ("simplified", "SIMPLIFIED_B2C"),
]


def _resolve_document_type_key(payload: dict) -> str:
    explicit = payload.get("document_type") or payload.get("documentType") or payload.get("docType")
    if explicit in DOCUMENT_TYPE_BY_KEY:
        return explicit
    code = str(payload.get("doc_type") or payload.get("IBT_003_InvoiceTypeCode") or "")
    code_to_key = {"380": "STANDARD_380", "381": "CREDIT_NOTE_381", "383": "DEBIT_NOTE_383",
                   "389": "SELF_BILLED_389", "261": "SELF_BILLED_CN_261"}
    if code in code_to_key:
        return code_to_key[code]
    type_label = str(payload.get("type") or "").lower()
    for needle, key in _TYPE_LABEL_TO_KEY:
        if needle in type_label:
            return key
    if bool(payload.get("b2c")):
        return "SIMPLIFIED_B2C"
    return "STANDARD_380"


def _numeric(value, default="0") -> str:
    """Accept ERP/display values such as '1,250.000 OMR' at the API boundary."""
    cleaned = re.sub(r"[^0-9.\-]", "", str(value if value is not None else default).replace(",", ""))
    return cleaned or default


def _doc_type_label(document) -> str:
    if document.is_export:
        return "Export"
    entry = DOCUMENT_TYPE_BY_KEY.get(document.document_type)
    return entry["label"] if entry else "Standard Invoice"


def _tdd_label(document, transmission) -> str:
    if transmission is None:
        return "Queued"
    if transmission.status == "REJECTED":
        return f"Rejected · OTA Error {transmission.ota_response_code or 'C1'}"
    if document.direction == "AP":
        return "C3 leg · Ack" if transmission.status in (
            "ACK_RECEIVED", "TDD_REPORTED", "MLS_RECEIVED") else "C3 leg · In transit"
    if transmission.status == "AS4_SENT":
        return "Submit · In transit"
    if transmission.status in ("ACK_RECEIVED", "TDD_REPORTED", "MLS_RECEIVED"):
        return "Submit · Ack"
    return "Queued"


def to_compat(document) -> dict:
    """Document -> faturathi-ui Invoice JSON (types.ts Invoice interface)."""
    transmission = document.transmissions.order_by("-attempt").first()
    lines = [
        [line.item_name, float(line.quantity), f"{line.unit_price:.3f}",
         VAT_LABEL_BY_CODE.get(line.vat_category, "S 5%")]
        for line in document.lines.all()
    ]
    primary_cat = lines[0][3] if lines else VAT_LABEL_BY_CODE.get("S")

    err = None
    if document.status == "REJECTED" and transmission and transmission.validation_errors:
        first = transmission.validation_errors[0]
        err = first.get("message") if isinstance(first, dict) else str(first)

    return {
        "id": str(document.id),
        "n": document.invoice_number,
        "d": document.issue_date.isoformat() if document.issue_date else None,
        "t": document.issue_time.strftime("%H:%M:%S") if document.issue_time else None,
        "type": _doc_type_label(document),
        "documentType": document.document_type,
        "docTypeCode": document.doc_type,
        "dir": "Outbound (AR)" if document.direction == "AR" else "Inbound (AP)",
        "cp": document.counterparty_name,
        "cpv": document.counterparty_vatin,
        "eas": document.counterparty_endpoint,
        "net": float(document.tax_exclusive_amount),
        "vat": float(document.tax_amount),
        "st": document.get_status_display(),
        "tdd": _tdd_label(document, transmission),
        "err": err,
        "tt": document.transaction_type_code,
        "uuid": str(document.uuid_v5) if document.uuid_v5 else None,
        "cat": primary_cat,
        "ent": document.company.short_code if document.company_id else None,
        "sVat": document.company.vat_number if document.company_id else None,
        "erpSystem": document.erp_system or None,
        "sourceChannel": document.get_source_display(),
        "cn": document.billing_reference.invoice_number if document.billing_reference_id else None,
        "notes": document.notes,
        "validationErrors": transmission.validation_errors if transmission else [],
        "ap": document.ap_status or None,
        "b2c": document.is_b2c,
        "lines": lines,
        "createdAt": document.created_at.isoformat(),
        "source": document.source,
        "createdBy": document.created_by.email if document.created_by_id else None,
        "mlsStatus": transmission.mls_status if transmission else None,
        "extra": document.extra_data or {},
    }


def build_document_payload(payload: dict, direction: str = "AR") -> dict:
    """DocumentSerializer input, built from either faturathi-ui's short-key JSON (n/d/t/cp/cpv/...)
    or long-form flat keys (invoice_number/issue_date/counterparty_name/...) used by the sample
    CSV/XLSX batch files — both are accepted so the same pipeline handles UI, API, and file uploads."""
    seller = payload.get("SellerDetails") or {}
    buyer = payload.get("BuyerDetails") or {}
    payment = payload.get("PaymentDetails") or {}
    pint_lines = payload.get("Lines") or []
    if not pint_lines and payload.get("IBT_153_ItemName"):
        pint_lines = [payload]
    net = Decimal(str(payload.get("net", 0) or 0))
    vat_category_code = str(payload.get("vat_category") or "").upper()
    cat_label = payload.get("cat") or VAT_LABEL_BY_CODE.get(vat_category_code) or "S 5%"
    document_type_key = _resolve_document_type_key(payload)
    is_b2c = DOCUMENT_TYPE_BY_KEY[document_type_key]["is_b2c"]

    notes = payload.get("notes") or payload.get("reason") or ""
    if not notes and document_type_key in CN_DN_DOCUMENT_TYPE_KEYS:
        ref = payload.get("cn") or payload.get("billing_reference") or payload.get("cn_ref")
        notes = f"Adjustment reference: {ref}" if ref else "Adjustment / correction to a prior invoice."

    raw_lines = payload.get("lines") or ([{
        "name": line.get("IBT_153_ItemName"), "qty": line.get("IBT_129_InvoicedQuantity"),
        "price": line.get("IBT_146_ItemNetPrice"), "cat": line.get("IBT_151_ItemVATCategoryCode"),
        "unit": line.get("IBT_130_InvoicedQuantityUnitCode", "EA"),
        "discount": line.get("IBT_149_ItemPriceDiscount", 0),
        "description": line.get("IBT_154_ItemDescription", ""),
    } for line in pint_lines] if pint_lines else [[
        payload.get("itemName") or payload.get("item_name") or "Line item 1",
        payload.get("qty") or payload.get("quantity") or 1,
        payload.get("price") or payload.get("unit_price") or str(net),
        cat_label,
    ]])
    lines = []
    for idx, line in enumerate(raw_lines, start=1):
        if isinstance(line, dict):
            name, qty, price, line_cat = line.get("name"), line.get("qty"), line.get("price"), line.get("cat")
            unit, discount, description = line.get("unit", "EA"), line.get("discount", 0), line.get("description", "")
        else:
            name, qty, price, line_cat = (list(line) + [None, None, None, None])[:4]
            unit, discount, description = "EA", 0, ""
        line_cat_code = (line_cat or cat_label).split()[0] if (line_cat or cat_label) else "S"
        lines.append({
            "line_id": idx,
            "item_name": name or f"Line {idx}",
            "quantity": qty or 1,
            "description": description,
            "unit_code": unit,
            "unit_price": _numeric(price),
            "discount": _numeric(discount),
            "vat_category": line_cat_code,
            "vat_rate": VAT_RATE_BY_CODE.get(line_cat_code, Decimal("5")),
        })

    billing_reference_number = (payload.get("billing_reference") or payload.get("billingReference")
                                or payload.get("billingReferenceNumber") or payload.get("BillingReference") or payload.get("cn_ref") or payload.get("cn"))

    return {
        "direction": direction,
        "document_type": document_type_key,
        "invoice_number": (payload.get("n") or payload.get("invoiceNumber") or payload.get("invoice_number")
                           or payload.get("IBT_001_InvoiceNumber")
                           or f"INV-2026-{random.randint(1000, 9999)}"),
        "issue_date": (payload.get("d") or payload.get("date") or payload.get("issue_date")
                       or payload.get("IBT_002_InvoiceIssueDate")
                       or timezone.localdate().isoformat()),
        "issue_time": payload.get("t") or payload.get("issue_time") or payload.get("IBT_168_InvoiceIssueTime") or "12:00:00",
        "due_date": payload.get("due_date") or payload.get("IBT_009_PaymentDueDate") or payment.get("IBT_009_PaymentDueDate") or None,
        "tax_point_date": payload.get("tax_point_date") or payload.get("IBT_007_TaxPointDate") or None,
        "transaction_type_code": payload.get("tt") or payload.get("BTOM_001_OmanTransactionType") or _DEFAULT_TT_BY_DOCUMENT_TYPE[document_type_key],
        "counterparty_name": (payload.get("cp") or payload.get("customerName")
                               or payload.get("counterparty_name") or payload.get("IBT_044_BuyerName") or buyer.get("IBT_044_BuyerName") or ""),
        "counterparty_vatin": payload.get("cpv") or payload.get("counterparty_vatin") or payload.get("IBT_048_BuyerVATIdentifier") or buyer.get("IBT_048_BuyerVATIdentifier") or "",
        "counterparty_endpoint": (payload.get("eas") or payload.get("counterparty_endpoint")
                                  or payload.get("IBT_049_BuyerElectronicAddress") or buyer.get("IBT_049_BuyerElectronicAddress") or (B2C_DUMMY if is_b2c else "")),
        "currency": payload.get("IBT_005_InvoiceCurrencyCode") or "OMR",
        "payment_means_code": payload.get("payment_means_code") or payload.get("IBT_081_PaymentMeansCode") or payment.get("IBT_081_PaymentMeansCode") or "30",
        "payment_iban": payload.get("iban") or payload.get("payment_iban") or payload.get("IBT_084_PaymentAccountIdentifier") or payment.get("IBT_084_PaymentAccountIdentifier") or "OM810180000000000000123",
        "payment_terms": payload.get("payment_terms") or payload.get("IBT_020_PaymentTermsNote") or payment.get("IBT_020_PaymentTermsNote") or "",
        "status": payload.get("st_internal") or "PENDING",
        "source": payload.get("source") or "MANUAL",
        "notes": notes,
        "erp_system": payload.get("erpSystem") or payload.get("erp_system") or "",
        "extra_data": {"ingested_payload": payload.get("extra_data") or payload.get("extra") or payload},
        "lines": lines,
        # Not a Document field: the view resolves this invoice_number to a billing_reference FK.
        "_billing_reference_number": billing_reference_number,
    }
