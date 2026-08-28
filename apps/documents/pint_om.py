"""Canonical PINT-OM payload builder shared by every document ingestion channel.

The relational columns remain the searchable source of truth for operational fields.  The
``extra_data.pint_om`` snapshot contains the complete OTA-facing representation, including
conditional/optional members retained for backwards compatibility with the legacy API.
"""

from collections import defaultdict
from decimal import Decimal


def _money(value) -> float:
    return float(Decimal(str(value or 0)).quantize(Decimal("0.01")))


def build_pint_payload(document) -> dict:
    company = document.company
    lines = list(document.lines.all())
    vat_groups = defaultdict(lambda: {"taxable": Decimal("0"), "tax": Decimal("0"), "rate": Decimal("0")})
    pint_lines = []
    for line in lines:
        group = vat_groups[line.vat_category]
        group["taxable"] += line.line_net
        group["tax"] += line.line_net * line.vat_rate / Decimal("100")
        group["rate"] = line.vat_rate
        pint_lines.append({
            "IBT_126_LineIdentifier": str(line.line_id),
            "IBT_127_InvoiceLineNote": line.description,
            "IBT_129_InvoicedQuantity": float(line.quantity),
            "IBT_130_InvoicedQuantityUnitCode": line.unit_code,
            "IBT_131_InvoiceLineNetAmount": _money(line.line_net),
            "IBT_132_ReferencedPOLineReference": "",
            "IBT_133_InvoiceLineBuyerAccountingReference": "",
            "IBT_153_ItemName": line.item_name,
            "IBT_154_ItemDescription": line.description,
            "IBT_155_ItemSellerIdentifier": "",
            "IBT_157_ItemStandardIdentifier": "",
            "IBT_151_ItemVATCategoryCode": line.vat_category,
            "IBT_152_ItemVATRate": float(line.vat_rate),
            "IBT_146_ItemNetPrice": _money(line.unit_price - line.discount),
            "IBT_149_ItemPriceDiscount": _money(line.discount),
            "IBT_148_ItemGrossPrice": _money(line.unit_price),
            "IBT_150_ItemPriceBaseQuantity": 1,
        })

    vat_breakdown = []
    for code, values in sorted(vat_groups.items()):
        exemption = "" if code == "S" else ("VATEX-OM-ZERO" if code == "Z" else "VATEX-OM-EXEMPT")
        vat_breakdown.append({
            "IBT_116_VATCategoryTaxableAmount": _money(values["taxable"]),
            "IBT_117_VATCategoryTaxAmount": _money(values["tax"]),
            "IBT_118_VATCategoryCode": code,
            "IBT_119_VATRate": float(values["rate"]),
            "IBT_120_VATExemptionReasonCode": exemption,
            "IBT_121_VATExemptionReasonText": "" if code == "S" else "Oman VAT zero-rated/exempt supply",
            "TaxSchemeID": "VAT",
        })

    extra = document.extra_data or {}
    supplied = extra.get("ingested_payload", extra) if isinstance(extra, dict) else {}
    seller_supplied = supplied.get("SellerDetails", {}) if isinstance(supplied, dict) else {}
    buyer_supplied = supplied.get("BuyerDetails", {}) if isinstance(supplied, dict) else {}
    payment_supplied = supplied.get("PaymentDetails", {}) if isinstance(supplied, dict) else {}
    allowance_supplied = supplied.get("DocumentAllowancesCharges", {}) if isinstance(supplied, dict) else {}
    is_ap = document.direction == "AP"
    seller_name = document.counterparty_name if is_ap else company.name_en
    seller_vatin = document.counterparty_vatin if is_ap else company.vat_number
    seller_endpoint = document.counterparty_endpoint if is_ap else company.peppol_participant_id
    buyer_name = company.name_en if is_ap else document.counterparty_name
    buyer_vatin = company.vat_number if is_ap else document.counterparty_vatin
    buyer_endpoint = company.peppol_participant_id if is_ap else document.counterparty_endpoint

    return {
        "BTOM_001_OmanTransactionType": document.transaction_type_code,
        "BTOM_002_InvoiceUUID": str(document.uuid_v5) if document.uuid_v5 else "",
        "IBT_001_InvoiceNumber": document.invoice_number,
        "IBT_002_InvoiceIssueDate": document.issue_date.isoformat() if document.issue_date else "",
        "IBT_168_InvoiceIssueTime": document.issue_time.strftime("%H:%M:%S") if document.issue_time else "",
        "IBT_003_InvoiceTypeCode": document.doc_type,
        "IBT_024_SpecificationIdentifier": supplied.get("IBT_024_SpecificationIdentifier", "urn:peppol:pint:billing-1@om-1"),
        "IBT_023_BusinessProcessType": supplied.get("IBT_023_BusinessProcessType", "urn:peppol:bis:billing"),
        "IBT_007_TaxPointDate": document.tax_point_date.isoformat() if document.tax_point_date else (document.issue_date.isoformat() if document.issue_date else ""),
        "IBT_005_InvoiceCurrencyCode": document.currency,
        "IBT_006_VATAccountingCurrency": supplied.get("IBT_006_VATAccountingCurrency", "OMR"),
        "SellerDetails": {
            "IBT_027_SellerName": seller_name,
            "IBT_034_SellerIdentifier": seller_vatin,
            "IBT_034_1_SellerIdentifierScheme": "0248",
            "IBT_031_SellerVATIdentifier": seller_vatin,
            "IBT_031_1_SellerVATScheme": "VAT",
            "IBT_028_SellerTradingName": seller_supplied.get("IBT_028_SellerTradingName", seller_name),
            "IBT_035_SellerAddressLine1": seller_supplied.get("IBT_035_SellerAddressLine1", "" if is_ap else company.address),
            "IBT_037_SellerCity": seller_supplied.get("IBT_037_SellerCity", "" if is_ap else company.city),
            "IBT_038_SellerPostCode": seller_supplied.get("IBT_038_SellerPostCode", "" if is_ap else company.postal_code),
            "IBT_040_SellerCountryCode": seller_supplied.get("IBT_040_SellerCountryCode", "OM" if is_ap else company.country_code),
            "IBT_034_SellerElectronicAddress": seller_endpoint,
            "IBT_034_1_SellerElectronicAddressScheme": "0248",
        },
        "BuyerDetails": {
            "IBT_044_BuyerName": buyer_name,
            "IBT_049_BuyerIdentifier": buyer_vatin,
            "IBT_049_1_BuyerIdentifierScheme": "0248",
            "IBT_048_BuyerVATIdentifier": buyer_vatin,
            "IBT_048_1_BuyerVATScheme": "VAT",
            "IBT_045_BuyerTradingName": buyer_supplied.get("IBT_045_BuyerTradingName", buyer_name),
            "IBT_050_BuyerAddressLine1": buyer_supplied.get("IBT_050_BuyerAddressLine1", company.address if is_ap else ""),
            "IBT_052_BuyerCity": buyer_supplied.get("IBT_052_BuyerCity", company.city if is_ap else ""),
            "IBT_053_BuyerPostCode": buyer_supplied.get("IBT_053_BuyerPostCode", company.postal_code if is_ap else ""),
            "IBT_055_BuyerCountryCode": buyer_supplied.get("IBT_055_BuyerCountryCode", "OM"),
            "IBT_049_BuyerElectronicAddress": buyer_endpoint,
        },
        "PaymentDetails": {
            "IBT_081_PaymentMeansCode": document.payment_means_code,
            "IBT_084_PaymentAccountIdentifier": document.payment_iban,
            "IBT_009_PaymentDueDate": document.due_date.isoformat() if document.due_date else "",
            "IBT_020_PaymentTermsNote": document.payment_terms,
        } | payment_supplied,
        "DocumentAllowancesCharges": {
            "IBT_092_DocumentAllowanceAmount": _money(document.allowance_total),
            "IBT_094_DocumentAllowanceBaseAmount": _money(document.line_extension_amount),
            "IBT_096_DocumentAllowanceVATCategory": allowance_supplied.get("IBT_096_DocumentAllowanceVATCategory", "S"),
        },
        "Totals": {
            "IBT_106_SumLineNetAmount": _money(document.line_extension_amount),
            "IBT_107_SumAllowances": _money(document.allowance_total),
            "IBT_108_SumCharges": _money(document.charge_total),
            "IBT_109_InvoiceTotalNetAmount": _money(document.tax_exclusive_amount),
            "IBT_110_InvoiceTotalVATAmount": _money(document.tax_amount),
            "IBT_111_VATAmountInAccountingCurrency": _money(document.tax_amount),
            "IBT_112_InvoiceTotalAmountWithVAT": _money(document.tax_inclusive_amount),
            "IBT_115_AmountDueForPayment": _money(document.payable_amount),
        },
        "VATBreakdown": vat_breakdown,
        "Lines": pint_lines,
        "BillingReference": document.billing_reference.invoice_number if document.billing_reference_id else "",
        "AdjustmentReason": document.notes,
        "ProcessingMetadata": {
            "source": document.source,
            "source_label": document.get_source_display(),
            "erp_system": document.erp_system,
            "created_by": document.created_by.email if document.created_by_id else "",
            "created_at": document.created_at.isoformat() if document.created_at else "",
            "status": document.status,
            "branch_id": str(document.branch_id) if document.branch_id else "",
            "branch_code": document.branch.code if document.branch_id else "",
            "branch_name": document.branch.name if document.branch_id else "",
        },
    }


def refresh_pint_snapshot(document, ingested_payload=None) -> None:
    existing = document.extra_data if isinstance(document.extra_data, dict) else {}
    if "pint_om" in existing:
        existing = {key: value for key, value in existing.items() if key != "pint_om"}
    if ingested_payload is not None:
        existing["ingested_payload"] = ingested_payload
    document.extra_data = {**existing, "pint_om": build_pint_payload(document)}
    document.save(update_fields=["extra_data"])
