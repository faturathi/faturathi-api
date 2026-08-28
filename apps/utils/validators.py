"""
Subset (~15 rules) of the PINT OM validation spec. Intentionally not a full Schematron
implementation (Golden Rule #5) — enough to make the demo's reject/resubmit flow feel real.
"""

import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from apps.utils.constants import BR_O_02_MESSAGE, ERROR_CODES, UNIT_CODES, VATIN_REGEX

SELLER_VATIN_REGEX = r"^OM\d{8,12}$"
CN_DOC_TYPES = {"381", "383", "261"}


def _round2(value) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _err(rule, field, code, message):
    return {"rule": rule, "field": field, "code": code, "message": message}


def validate_document(document) -> list[dict]:
    """Validate a Document (+ its DocumentLine rows) instance. Returns [] if clean."""
    errors: list[dict] = []
    lines = list(document.lines.all())

    # 1. MAND-FIELDS
    mandatory = {
        "invoice_number": document.invoice_number,
        "issue_date": document.issue_date,
        "issue_time": document.issue_time,
        "doc_type": document.doc_type,
        "currency": document.currency,
        "counterparty_name": document.counterparty_name,
    }
    for field, value in mandatory.items():
        if not value:
            errors.append(_err("MAND-FIELDS", field, "C1", f"'{field}' is required."))
    if not document.counterparty_endpoint and not document.is_b2c:
        errors.append(_err("MAND-FIELDS", "counterparty_endpoint", "C1",
                            "Counterparty electronic address (Peppol EAS) is required."))

    # 2. VATIN-FORMAT (B2B only)
    if not document.is_b2c and document.counterparty_vatin:
        if not re.match(VATIN_REGEX, document.counterparty_vatin):
            errors.append(_err("VATIN-FORMAT", "counterparty_vatin", "C5",
                                BR_O_02_MESSAGE.format(vatin=document.counterparty_vatin)))

    # 3. SELLER-VATIN
    seller_vatin = (document.counterparty_vatin if document.direction == "AP"
                    else document.company.vat_number if document.company_id else "")
    if not re.match(SELLER_VATIN_REGEX, seller_vatin or ""):
        errors.append(_err("SELLER-VATIN", "company.vat_number", "C5",
                            f"Seller VATIN '{seller_vatin}' must start with 'OM' followed by 8-12 digits."))

    # 4. DATE-FORMAT
    if document.issue_date and document.issue_date > date.today():
        errors.append(_err("DATE-FORMAT", "issue_date", "C3", "issue_date cannot be in the future."))
    if document.due_date and document.issue_date and document.due_date < document.issue_date:
        errors.append(_err("DATE-FORMAT", "due_date", "C3", "due_date cannot be before issue_date."))

    # 5. MATH-TOTAL
    if _round2(document.tax_inclusive_amount) != _round2(document.tax_exclusive_amount + document.tax_amount):
        errors.append(_err("MATH-TOTAL", "tax_inclusive_amount", "C8",
                            "tax_inclusive_amount must equal tax_exclusive_amount + tax_amount."))

    # 6. MATH-LINES
    lines_sum = sum((l.line_net for l in lines), Decimal("0"))
    if lines and _round2(document.line_extension_amount) != _round2(lines_sum):
        errors.append(_err("MATH-LINES", "line_extension_amount", "C8",
                            "line_extension_amount must equal the sum of line line_net amounts."))
    for line in lines:
        expected = (line.quantity * line.unit_price) - line.discount
        if _round2(line.line_net) != _round2(expected):
            errors.append(_err("MATH-LINES", f"lines[{line.line_id}].line_net", "C8",
                                f"Line {line.line_id}: line_net must equal quantity*unit_price - discount."))

    # 7. VAT-RATE
    for line in lines:
        expected_rate = Decimal("5") if line.vat_category == "S" else Decimal("0")
        if line.vat_rate != expected_rate:
            errors.append(_err("VAT-RATE", f"lines[{line.line_id}].vat_rate", "C6",
                                f"Category '{line.vat_category}' must use rate {expected_rate}."))

    # 8. UNIT-CODE
    for line in lines:
        if line.unit_code not in UNIT_CODES:
            suggestion = "EA" if line.unit_code == "PCS" else None
            msg = f"Unit code '{line.unit_code}' is not on the whitelist."
            if suggestion:
                msg += f" Did you mean '{suggestion}'?"
            errors.append(_err("UNIT-CODE", f"lines[{line.line_id}].unit_code", "C7", msg))

    # 9. CURRENCY
    if document.currency != "OMR":
        errors.append(_err("CURRENCY", "currency", "C4", "Only OMR is supported in this demo."))

    # 10. CN-REF
    if document.doc_type in CN_DOC_TYPES and not document.billing_reference_id:
        errors.append(_err("CN-REF", "billing_reference", "C9",
                            "Credit/Debit/Self-billed credit notes require a billing_reference."))
    if document.doc_type in CN_DOC_TYPES and not document.notes.strip():
        errors.append(_err("CN-REASON", "notes", "C9",
                           "Credit/Debit/Self-billed credit notes require an adjustment reason."))

    # 11. TXN-TYPE
    if not re.match(r"^[01]{20}$", document.transaction_type_code or ""):
        errors.append(_err("TXN-TYPE", "transaction_type_code", "C2",
                            "transaction_type_code must be exactly 20 chars of 0/1."))

    # 12. DUP-CHECK
    dup_qs = type(document).objects.filter(
        company=document.company, invoice_number=document.invoice_number, is_deleted=False
    ).exclude(pk=document.pk)
    if dup_qs.exists():
        errors.append(_err("DUP-CHECK", "invoice_number", "C10",
                            f"Invoice number '{document.invoice_number}' already exists for this company."))

    # 13. LINES-MIN
    if not lines:
        errors.append(_err("LINES-MIN", "lines", "C1", "At least one line is required."))
    else:
        expected_ids = list(range(1, len(lines) + 1))
        actual_ids = sorted(l.line_id for l in lines)
        if actual_ids != expected_ids:
            errors.append(_err("LINES-MIN", "lines", "C1", "Line ids must be sequential starting from 1."))

    # 14. PAYMENT
    if document.payment_means_code not in ("10", "30"):
        errors.append(_err("PAYMENT", "payment_means_code", "C11", "payment_means_code must be 10 or 30."))
    elif document.payment_means_code == "30" and not document.payment_iban:
        errors.append(_err("PAYMENT", "payment_iban", "C11", "IBAN is required for payment means 30 (transfer)."))

    return errors


# ---------------------------------------------------------------------------
# /api/validate: accepts the IBT-named nested payload used by faturathi-ui's
# PayloadSimulator / Postman collection. Subset of omanValidator.ts, not 1:1
# (Golden Rule #5 overrides the addendum's "port 1:1" note).
# ---------------------------------------------------------------------------

def validate_ibt_payload(raw: dict) -> dict:
    errors: list[dict] = []
    warnings: list[dict] = []

    seller = raw.get("SellerDetails") or {}
    buyer = raw.get("BuyerDetails") or {}
    totals = raw.get("Totals") or {}
    lines = raw.get("Lines") or []

    txn_type = str(raw.get("BTOM_001_OmanTransactionType") or "")
    is_simplified = len(txn_type) > 1 and txn_type[1] == "1"

    if not re.match(r"^[01]{20}$", txn_type):
        errors.append({"fieldId": "BTOM-001", "message": "BTOM_001_OmanTransactionType must be a 20-char 0/1 bitmap."})

    for field_id, value, label in [
        ("IBT-001", raw.get("IBT_001_InvoiceNumber"), "Invoice number"),
        ("IBT-002", raw.get("IBT_002_InvoiceIssueDate"), "Issue date"),
        ("IBT-005", raw.get("IBT_005_InvoiceCurrencyCode"), "Currency code"),
        ("IBT-027", seller.get("IBT_027_SellerName"), "Seller name"),
        ("IBT-034", seller.get("IBT_034_SellerIdentifier"), "Seller VATIN"),
        ("IBT-044", buyer.get("IBT_044_BuyerName"), "Buyer name"),
    ]:
        if not value:
            errors.append({"fieldId": field_id, "message": f"{label} ({field_id}) is required."})

    if not is_simplified:
        buyer_vat = buyer.get("IBT_048_BuyerVATIdentifier") or ""
        if not re.match(VATIN_REGEX, buyer_vat):
            errors.append({"fieldId": "IBT-048", "message": BR_O_02_MESSAGE.format(vatin=buyer_vat)})

    seller_vat = seller.get("IBT_034_SellerIdentifier") or ""
    if not re.match(SELLER_VATIN_REGEX, seller_vat):
        errors.append({"fieldId": "IBT-034", "message": f"Seller VATIN '{seller_vat}' violates Oman PINT-OM syntax rules."})

    net = Decimal(str(totals.get("IBT_109_InvoiceTotalNetAmount", 0) or 0))
    vat = Decimal(str(totals.get("IBT_110_InvoiceTotalVATAmount", 0) or 0))
    gross = totals.get("IBT_112_InvoiceTotalAmountWithVAT")
    if gross is not None and _round2(Decimal(str(gross))) != _round2(net + vat):
        errors.append({"fieldId": "IBT-112", "message": "IBT-112 must equal IBT-109 + IBT-110."})

    if not lines:
        warnings.append({"fieldId": "Lines", "message": "No invoice lines supplied; defaults were applied."})

    return {
        "isValid": len(errors) == 0,
        "isSimplified": is_simplified,
        "errors": errors,
        "warnings": warnings,
    }
