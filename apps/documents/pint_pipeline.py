"""Central PINT-OM REST -> UBL -> official Schematron validation pipeline."""

from __future__ import annotations

import re
import uuid
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from xml.etree import ElementTree as ET

from .pint_contract import PintOmInvoiceSerializer


SPECIFICATION_VERSION = "1.0.1"
PINT_OM_BILLING = "urn:peppol:pint:billing-1@om-1"
PINT_OM_SELF_BILLING = "urn:peppol:pint:selfbilling-1@om-1"
PROFILE_BILLING = "urn:peppol:bis:billing"
PROFILE_SELF_BILLING = "urn:peppol:bis:selfbilling"
SELF_BILLED_CODES = {"389", "261"}
CREDIT_NOTE_CODES = {"381", "261"}
CORRECTION_CODES = {"381", "383", "261"}

NS_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
NS_INVOICE = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
NS_CREDIT_NOTE = "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
NS_SVRL = "http://purl.oclc.org/dsdl/svrl"

ET.register_namespace("cac", NS_CAC)
ET.register_namespace("cbc", NS_CBC)


def _error(code, field, business_term, message, source, severity="fatal"):
    return {
        "code": code,
        "severity": severity,
        "field": field,
        "business_term": business_term,
        "message": message,
        "source": source,
    }


def _business_term(field: str) -> str | None:
    match = re.search(r"(?:^|\.)(ibt|btom)_(\d+)", field)
    return f"{match.group(1).upper()}-{match.group(2)}" if match else None


def _flatten_serializer_errors(errors, prefix=""):
    normalized = []
    if isinstance(errors, dict):
        for key, value in errors.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            normalized.extend(_flatten_serializer_errors(value, path))
    elif isinstance(errors, list):
        for index, value in enumerate(errors):
            if isinstance(value, (dict, list)):
                normalized.extend(_flatten_serializer_errors(value, f"{prefix}[{index}]"))
            else:
                normalized.append(_error(
                    "REST-SCHEMA-001", prefix, _business_term(prefix), str(value), "drf_schema"
                ))
    else:
        normalized.append(_error(
            "REST-SCHEMA-001", prefix, _business_term(prefix), str(errors), "drf_schema"
        ))
    return normalized


def _decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _money(value: Decimal) -> str:
    text = format(_decimal(value).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _semantic_errors(data):
    header = data["header"]
    seller = data["seller_details"]
    buyer = data["buyer_details"]
    totals = data["totals"]
    lines = data["lines"]
    breakdowns = data["vat_breakdown"]
    code = header["ibt_003_invoice_type_code"]
    txn_type = header["btom_001_invoice_transaction_type"]
    simplified = txn_type == "01000000000000000000"
    errors = []

    invoice_uuid = header["btom_002_invoice_uuid"]
    if invoice_uuid.version != 5:
        errors.append(_error(
            "IBR-002-OM", "header.btom_002_invoice_uuid", "BTOM-002",
            "Invoice UUID must be a valid UUID version 5.", "pint_om_semantic"
        ))
    if not re.fullmatch(r"OM\d{10}", seller["ibt_031_seller_vatin"]):
        errors.append(_error(
            "IBR-003-OM", "seller_details.ibt_031_seller_vatin", "IBT-031",
            "Seller VATIN must be OM followed by exactly 10 digits.", "pint_om_semantic"
        ))
    buyer_vatin = buyer.get("ibt_048_buyer_vatin", "")
    if buyer_vatin and not re.fullmatch(r"OM\d{10}", buyer_vatin):
        errors.append(_error(
            "IBR-003-OM", "buyer_details.ibt_048_buyer_vatin", "IBT-048",
            "Buyer VATIN must be OM followed by exactly 10 digits.", "pint_om_semantic"
        ))
    if not simplified:
        for key, term in (
            ("ibt_048_buyer_vatin", "IBT-048"),
            ("ibt_049_buyer_electronic_address", "IBT-049"),
            ("ibt_049_1_scheme_identifier", "IBT-049-1"),
        ):
            if not buyer.get(key):
                errors.append(_error(
                    "IBR-OM-BUYER-001", f"buyer_details.{key}", term,
                    "This buyer field is required for a non-simplified invoice.", "pint_om_semantic"
                ))

    expected_spec = PINT_OM_SELF_BILLING if code in SELF_BILLED_CODES else PINT_OM_BILLING
    expected_profile = PROFILE_SELF_BILLING if code in SELF_BILLED_CODES else PROFILE_BILLING
    if header["ibt_024_specification_identifier"] != expected_spec:
        errors.append(_error(
            "IBR-SR-01", "header.ibt_024_specification_identifier", "IBT-024",
            f"Specification identifier must be {expected_spec} for invoice type {code}.",
            "pint_semantic"
        ))
    if header["ibt_023_business_process_type"] != expected_profile:
        errors.append(_error(
            "IBR-OM-PROFILE-001", "header.ibt_023_business_process_type", "IBT-023",
            f"Business process type must be {expected_profile} for invoice type {code}.",
            "pint_om_semantic"
        ))
    if code in SELF_BILLED_CODES and txn_type[2] != "1":
        errors.append(_error(
            "IBR-177-OM", "header.btom_001_invoice_transaction_type", "BTOM-001",
            "Self-billed documents require the self-billing transaction-type bit.",
            "pint_om_semantic"
        ))
    if simplified and code != "380":
        errors.append(_error(
            "IBR-OM-TYPE-001", "header.ibt_003_invoice_type_code", "IBT-003",
            "The simplified transaction type is only valid with invoice type code 380.",
            "pint_om_semantic"
        ))
    currency = header["ibt_005_invoice_currency_code"]
    if currency != "OMR" and not header.get("btom_003_currency_exchange_rate"):
        errors.append(_error(
            "IBR-004-OM", "header.btom_003_currency_exchange_rate", "BTOM-003",
            "An exchange rate is required when invoice currency is not OMR.", "pint_om_semantic"
        ))
    if header.get("ibt_006_vat_accounting_currency") not in (None, "OMR"):
        errors.append(_error(
            "IBR-OM-CURRENCY-001", "header.ibt_006_vat_accounting_currency", "IBT-006",
            "Oman VAT accounting currency must be OMR.", "pint_om_semantic"
        ))
    if code in CORRECTION_CODES and not data.get("billing_reference"):
        errors.append(_error(
            "IBR-OM-REF-001", "billing_reference.ibt_025_preceding_invoice_reference", "IBT-025",
            "Credit notes, debit notes and self-billed credit notes require a preceding invoice reference.",
            "pint_om_semantic"
        ))

    line_net_total = Decimal("0")
    line_vat_total = Decimal("0")
    by_category = {}
    for index, line in enumerate(lines):
        prefix = f"lines[{index}]"
        expected_net = line["ibt_129_invoiced_quantity"] * line["ibt_146_item_net_price"]
        if abs(line["ibt_131_line_net_amount"] - expected_net) > Decimal("0.001"):
            errors.append(_error(
                "IBR-126", f"{prefix}.ibt_131_line_net_amount", "IBT-131",
                "Line net amount must equal quantity multiplied by item net price.", "pint_semantic"
            ))
        expected_vat = (line["ibt_131_line_net_amount"] * line["ibt_152_item_vat_rate"] / Decimal("100"))
        if abs(line["btom_016_line_vat_amount"] - expected_vat) > Decimal("0.001"):
            errors.append(_error(
                "IBR-168-OM", f"{prefix}.btom_016_line_vat_amount", "BTOM-016",
                "Line VAT amount must equal line net amount multiplied by the VAT rate.", "pint_om_semantic"
            ))
        if abs(line["btom_017_line_total_including_vat"] - (
            line["ibt_131_line_net_amount"] + line["btom_016_line_vat_amount"]
        )) > Decimal("0.001"):
            errors.append(_error(
                "IBR-158-OM", f"{prefix}.btom_017_line_total_including_vat", "BTOM-017",
                "Line total including VAT must equal line net plus line VAT.", "pint_om_semantic"
            ))
        category = line["ibt_151_item_vat_category_code"]
        rate = line["ibt_152_item_vat_rate"]
        if (category == "S" and rate != Decimal("5")) or (category != "S" and rate != Decimal("0")):
            errors.append(_error(
                "IBR-OM-VAT-001", f"{prefix}.ibt_152_item_vat_rate", "IBT-152",
                "VAT category S requires 5%; Z, E and O require 0%.", "pint_om_semantic"
            ))
        if not simplified and not line.get("btom_019_goods_or_services_identification"):
            errors.append(_error(
                "IBR-078-OM", f"{prefix}.btom_019_goods_or_services_identification", "BTOM-019",
                "Goods or services identification is required for non-simplified invoices.",
                "pint_om_semantic"
            ))
        line_net_total += line["ibt_131_line_net_amount"]
        line_vat_total += line["btom_016_line_vat_amount"]
        key = (category, rate)
        grouped = by_category.setdefault(key, [Decimal("0"), Decimal("0")])
        grouped[0] += line["ibt_131_line_net_amount"]
        grouped[1] += line["btom_016_line_vat_amount"]

    checks = (
        ("ibt_106_sum_of_line_net_amount", line_net_total, "IBT-106", "IBR-106"),
        ("ibt_109_invoice_total_without_vat",
         totals["ibt_106_sum_of_line_net_amount"] - totals["ibt_107_sum_of_allowances"] + totals["ibt_108_sum_of_charges"],
         "IBT-109", "IBR-109"),
        ("ibt_110_invoice_total_vat_amount", line_vat_total, "IBT-110", "IBR-110"),
        ("ibt_112_invoice_total_with_vat",
         totals["ibt_109_invoice_total_without_vat"] + totals["ibt_110_invoice_total_vat_amount"],
         "IBT-112", "IBR-112"),
        ("ibt_115_amount_due_for_payment",
         totals["ibt_112_invoice_total_with_vat"] - totals["ibt_113_paid_amount"] + totals["ibt_114_rounding_amount"],
         "IBT-115", "IBR-115"),
    )
    for key, expected, term, rule in checks:
        if abs(totals[key] - expected) > Decimal("0.001"):
            errors.append(_error(
                rule, f"totals.{key}", term,
                f"Reported amount {_money(totals[key])} does not equal calculated amount {_money(expected)}.",
                "pint_semantic"
            ))
    for index, item in enumerate(breakdowns):
        key = (item["ibt_118_vat_category_code"], item["ibt_119_vat_category_rate"])
        expected = by_category.get(key, [Decimal("0"), Decimal("0")])
        if abs(item["ibt_116_vat_category_taxable_amount"] - expected[0]) > Decimal("0.001"):
            errors.append(_error(
                "IBR-OM-VAT-BASE", f"vat_breakdown[{index}].ibt_116_vat_category_taxable_amount", "IBT-116",
                "VAT taxable amount does not match the lines in this category/rate.", "pint_om_semantic"
            ))
        if abs(item["ibt_117_vat_category_tax_amount"] - expected[1]) > Decimal("0.001"):
            errors.append(_error(
                "IBR-OM-VAT-AMOUNT", f"vat_breakdown[{index}].ibt_117_vat_category_tax_amount", "IBT-117",
                "VAT category tax amount does not match line VAT in this category/rate.", "pint_om_semantic"
            ))
    return errors


def _sub(parent, namespace, tag_name, value=None, **attributes):
    element = ET.SubElement(parent, f"{{{namespace}}}{tag_name}", {k: str(v) for k, v in attributes.items()})
    if value is not None:
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        element.text = str(value)
    return element


def _party(root, element_name, details, seller, default_endpoint=None, account_uuid=None):
    wrapper = _sub(root, NS_CAC, element_name)
    if account_uuid:
        _sub(wrapper, NS_CBC, "AdditionalAccountID", account_uuid)
    party = _sub(wrapper, NS_CAC, "Party")
    prefix = "seller" if seller else "buyer"
    number = "034" if seller else "049"
    endpoint = details.get(f"ibt_{number}_{prefix}_electronic_address") or default_endpoint
    scheme = details.get(f"ibt_{number}_1_scheme_identifier")
    if endpoint:
        _sub(party, NS_CBC, "EndpointID", endpoint, schemeID=scheme or "0248")
    identifier = details.get(f"ibt_{'029' if seller else '046'}_{prefix}_identifier")
    if identifier:
        identification = _sub(party, NS_CAC, "PartyIdentification")
        _sub(identification, NS_CBC, "ID", identifier,
             schemeName=details.get(f"ibt_{'029' if seller else '046'}_1_{prefix}_identifier_scheme", "OTHID"))
    address = _sub(party, NS_CAC, "PostalAddress")
    field_numbers = ("035", "036", "162", "037", "038", "040") if seller else ("050", "051", "163", "052", "053", "055")
    names = ("StreetName", "AdditionalStreetName", "Line", "CityName", "PostalZone", "IdentificationCode")
    values = [
        details.get(f"ibt_{field_numbers[0]}_{prefix}_address_line_1"),
        details.get(f"ibt_{field_numbers[1]}_{prefix}_address_line_2"),
        details.get(f"ibt_{field_numbers[2]}_{prefix}_address_line_3"),
        details.get(f"ibt_{field_numbers[3]}_{prefix}_city"),
        details.get(f"ibt_{field_numbers[4]}_{prefix}_post_code"),
        details.get(f"ibt_{field_numbers[5]}_{prefix}_country_code"),
    ]
    for idx, value in enumerate(values):
        if not value:
            continue
        if names[idx] == "Line":
            _sub(_sub(address, NS_CAC, "AddressLine"), NS_CBC, "Line", value)
        elif names[idx] == "IdentificationCode":
            _sub(_sub(address, NS_CAC, "Country"), NS_CBC, "IdentificationCode", value)
        else:
            _sub(address, NS_CBC, names[idx], value)
    vatin = details.get(f"ibt_{'031' if seller else '048'}_{prefix}_vatin")
    if vatin:
        tax_scheme = _sub(party, NS_CAC, "PartyTaxScheme")
        _sub(tax_scheme, NS_CBC, "CompanyID", vatin)
        _sub(_sub(tax_scheme, NS_CAC, "TaxScheme"), NS_CBC, "ID", "VAT")
    legal = _sub(party, NS_CAC, "PartyLegalEntity")
    _sub(legal, NS_CBC, "RegistrationName", details[f"ibt_{'027' if seller else '044'}_{prefix}_name"])
    if seller:
        contact = _sub(party, NS_CAC, "Contact")
        if details.get("ibt_041_seller_contact_name"):
            _sub(contact, NS_CBC, "Name", details["ibt_041_seller_contact_name"])
        _sub(contact, NS_CBC, "Telephone", details["ibt_042_seller_contact_telephone"])
        if details.get("ibt_043_seller_contact_email"):
            _sub(contact, NS_CBC, "ElectronicMail", details["ibt_043_seller_contact_email"])


def map_json_to_ubl(data) -> str:
    header = data["header"]
    code = header["ibt_003_invoice_type_code"]
    credit_note = code in CREDIT_NOTE_CODES
    root_ns = NS_CREDIT_NOTE if credit_note else NS_INVOICE
    root = ET.Element(f"{{{root_ns}}}{'CreditNote' if credit_note else 'Invoice'}")
    _sub(root, NS_CBC, "CustomizationID", header["ibt_024_specification_identifier"])
    _sub(root, NS_CBC, "ProfileID", header["ibt_023_business_process_type"])
    _sub(root, NS_CBC, "ID", header["ibt_001_invoice_number"])
    _sub(root, NS_CBC, "UUID", header["btom_002_invoice_uuid"])
    _sub(root, NS_CBC, "IssueDate", header["ibt_002_invoice_issue_date"])
    _sub(root, NS_CBC, "IssueTime", header["ibt_168_invoice_issue_time"])
    if header.get("ibt_009_payment_due_date") and not credit_note:
        _sub(root, NS_CBC, "DueDate", header["ibt_009_payment_due_date"])
    type_element = "CreditNoteTypeCode" if credit_note else "InvoiceTypeCode"
    _sub(root, NS_CBC, type_element, code, name=header["btom_001_invoice_transaction_type"])
    if header.get("ibt_022_invoice_note"):
        _sub(root, NS_CBC, "Note", header["ibt_022_invoice_note"])
    if header.get("ibt_007_vat_point_date"):
        _sub(root, NS_CBC, "TaxPointDate", header["ibt_007_vat_point_date"])
    currency = header["ibt_005_invoice_currency_code"]
    _sub(root, NS_CBC, "DocumentCurrencyCode", currency)
    if header.get("ibt_006_vat_accounting_currency"):
        _sub(root, NS_CBC, "TaxCurrencyCode", header["ibt_006_vat_accounting_currency"])
    if header.get("ibt_010_buyer_reference"):
        _sub(root, NS_CBC, "BuyerReference", header["ibt_010_buyer_reference"])
    if data.get("billing_reference"):
        reference = data["billing_reference"]
        billing = _sub(root, NS_CAC, "BillingReference")
        document_ref = _sub(billing, NS_CAC, "InvoiceDocumentReference")
        _sub(document_ref, NS_CBC, "ID", reference["ibt_025_preceding_invoice_reference"])
        if reference.get("btom_031_preceding_invoice_uuid"):
            _sub(document_ref, NS_CBC, "UUID", reference["btom_031_preceding_invoice_uuid"])
        if reference.get("ibt_026_preceding_invoice_issue_date"):
            _sub(document_ref, NS_CBC, "IssueDate", reference["ibt_026_preceding_invoice_issue_date"])
        _sub(document_ref, NS_CBC, "DocumentStatusCode",
             reference["btom_032_credit_debit_note_reason_code"])
        _sub(document_ref, NS_CBC, "DocumentDescription", reference["btom_034_adjustment_reason"])
    simplified = header["btom_001_invoice_transaction_type"] == "01000000000000000000"
    _party(root, "AccountingSupplierParty", data["seller_details"], True,
           account_uuid=header["btom_002_invoice_uuid"] if simplified else None)
    _party(root, "AccountingCustomerParty", data["buyer_details"], False,
           default_endpoint="997770000099" if simplified else None)
    payment = data.get("payment_details")
    if payment and payment.get("ibt_081_payment_means_code") and not credit_note:
        means = _sub(root, NS_CAC, "PaymentMeans")
        _sub(means, NS_CBC, "PaymentMeansCode", payment["ibt_081_payment_means_code"])
        if payment.get("ibt_084_payment_account_identifier"):
            account = _sub(means, NS_CAC, "PayeeFinancialAccount")
            _sub(account, NS_CBC, "ID", payment["ibt_084_payment_account_identifier"], schemeID="IBAN")
    if payment and payment.get("ibt_020_payment_terms_note"):
        _sub(_sub(root, NS_CAC, "PaymentTerms"), NS_CBC, "Note", payment["ibt_020_payment_terms_note"])

    totals = data["totals"]
    tax_total = _sub(root, NS_CAC, "TaxTotal")
    _sub(tax_total, NS_CBC, "TaxAmount", _money(totals["ibt_110_invoice_total_vat_amount"]), currencyID=currency)
    for item in data["vat_breakdown"]:
        subtotal = _sub(tax_total, NS_CAC, "TaxSubtotal")
        _sub(subtotal, NS_CBC, "TaxableAmount", _money(item["ibt_116_vat_category_taxable_amount"]), currencyID=currency)
        _sub(subtotal, NS_CBC, "TaxAmount", _money(item["ibt_117_vat_category_tax_amount"]), currencyID=currency)
        category = _sub(subtotal, NS_CAC, "TaxCategory")
        _sub(category, NS_CBC, "ID", item["ibt_118_vat_category_code"])
        _sub(category, NS_CBC, "Percent", item["ibt_119_vat_category_rate"])
        if item.get("ibt_121_vat_exemption_reason_code"):
            _sub(category, NS_CBC, "TaxExemptionReasonCode", item["ibt_121_vat_exemption_reason_code"])
        if item.get("ibt_120_vat_exemption_reason_text"):
            _sub(category, NS_CBC, "TaxExemptionReason", item["ibt_120_vat_exemption_reason_text"])
        _sub(_sub(category, NS_CAC, "TaxScheme"), NS_CBC, "ID", "VAT")
    legal = _sub(root, NS_CAC, "LegalMonetaryTotal")
    amount_map = (
        ("LineExtensionAmount", "ibt_106_sum_of_line_net_amount"),
        ("TaxExclusiveAmount", "ibt_109_invoice_total_without_vat"),
        ("TaxInclusiveAmount", "ibt_112_invoice_total_with_vat"),
        ("AllowanceTotalAmount", "ibt_107_sum_of_allowances"),
        ("ChargeTotalAmount", "ibt_108_sum_of_charges"),
        ("PayableRoundingAmount", "ibt_114_rounding_amount"),
        ("PayableAmount", "ibt_115_amount_due_for_payment"),
    )
    for xml_name, key in amount_map:
        _sub(legal, NS_CBC, xml_name, _money(totals[key]), currencyID=currency)
    if totals["ibt_113_paid_amount"]:
        _sub(legal, NS_CBC, "PrepaidAmount", _money(totals["ibt_113_paid_amount"]), currencyID=currency)

    for line in data["lines"]:
        line_node = _sub(root, NS_CAC, "CreditNoteLine" if credit_note else "InvoiceLine")
        _sub(line_node, NS_CBC, "ID", line["ibt_126_line_identifier"])
        if line.get("ibt_127_line_note"):
            _sub(line_node, NS_CBC, "Note", line["ibt_127_line_note"])
        quantity_name = "CreditedQuantity" if credit_note else "InvoicedQuantity"
        _sub(line_node, NS_CBC, quantity_name, line["ibt_129_invoiced_quantity"],
             unitCode=line["ibt_130_quantity_unit_code"])
        _sub(line_node, NS_CBC, "LineExtensionAmount", _money(line["ibt_131_line_net_amount"]), currencyID=currency)
        item = _sub(line_node, NS_CAC, "Item")
        _sub(item, NS_CBC, "Name", line["ibt_153_item_name"])
        category = _sub(item, NS_CAC, "ClassifiedTaxCategory")
        _sub(category, NS_CBC, "ID", line["ibt_151_item_vat_category_code"])
        _sub(category, NS_CBC, "Percent", line["ibt_152_item_vat_rate"])
        _sub(_sub(category, NS_CAC, "TaxScheme"), NS_CBC, "ID", "VAT")
        goods_services = line.get("btom_019_goods_or_services_identification")
        if goods_services:
            spec_ref = _sub(item, NS_CAC, "ItemSpecificationDocumentReference")
            _sub(spec_ref, NS_CBC, "ID",
                 line.get("ibt_158_item_classification_identifier", "00000000"), schemeName="MP")
            _sub(spec_ref, NS_CBC, "DocumentTypeCode", goods_services)
        if line.get("ibt_158_item_classification_identifier"):
            commodity = _sub(item, NS_CAC, "CommodityClassification")
            _sub(commodity, NS_CBC, "ItemClassificationCode",
                 line["ibt_158_item_classification_identifier"],
                 listID=line.get("ibt_158_1_item_classification_scheme", "HS"))
        if line.get("btom_033_industrial_classification_code"):
            industrial = _sub(item, NS_CAC, "AdditionalItemIdentification")
            _sub(industrial, NS_CBC, "ID", line["btom_033_industrial_classification_code"],
                 schemeName=line.get("btom_033_1_scheme_name", "CC"))
        price = _sub(line_node, NS_CAC, "Price")
        _sub(price, NS_CBC, "PriceAmount", _money(line["ibt_146_item_net_price"]), currencyID=currency)
        extension = _sub(line_node, NS_CAC, "ItemPriceExtension")
        _sub(extension, NS_CBC, "Amount", _money(line["btom_017_line_total_including_vat"]), currencyID=currency)
        line_tax = _sub(extension, NS_CAC, "TaxTotal")
        _sub(line_tax, NS_CBC, "TaxAmount", _money(line["btom_016_line_vat_amount"]), currencyID=currency)
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


RULE_FIELD_MAP = {
    "IBR-001-OM": "header.btom_001_invoice_transaction_type",
    "IBR-002-OM": "header.btom_002_invoice_uuid",
    "IBR-003-OM": "seller_details.ibt_031_seller_vatin",
    "IBR-004-OM": "header.btom_003_currency_exchange_rate",
    "ALIGNED-IBRP-016-OM": "header.ibt_168_invoice_issue_time",
    "IBR-078-OM": "lines.btom_019_goods_or_services_identification",
    "IBR-168-OM": "lines.btom_016_line_vat_amount",
    "IBR-158-OM": "lines.btom_017_line_total_including_vat",
}


def _path_from_svrl(rule_id, location):
    if rule_id in RULE_FIELD_MAP:
        return RULE_FIELD_MAP[rule_id]
    location = location or ""
    candidates = (
        ("UUID", "header.btom_002_invoice_uuid"),
        ("IssueTime", "header.ibt_168_invoice_issue_time"),
        ("InvoiceTypeCode", "header.ibt_003_invoice_type_code"),
        ("CreditNoteTypeCode", "header.ibt_003_invoice_type_code"),
        ("AccountingSupplierParty", "seller_details"),
        ("AccountingCustomerParty", "buyer_details"),
        ("TaxSubtotal", "vat_breakdown"),
        ("InvoiceLine", "lines"),
        ("CreditNoteLine", "lines"),
        ("LegalMonetaryTotal", "totals"),
        ("BillingReference", "billing_reference"),
    )
    return next((path for token, path in candidates if token in location), "")


def _run_official_schematron(ubl_xml, invoice_type_code):
    try:
        from saxonche import PySaxonProcessor
    except ImportError:
        return [_error(
            "PINT-OM-ENGINE-UNAVAILABLE", "", None,
            "Official PINT-OM Schematron runtime is unavailable. Install backend requirements.",
            "pint_om_schematron"
        )], []
    family = "self-billing-1.0.1" if invoice_type_code in SELF_BILLED_CODES else "billing-1.0.1"
    transaction = "trn-creditnote" if invoice_type_code in CREDIT_NOTE_CODES else "trn-invoice"
    base = Path(__file__).resolve().parent / "schematron" / family / transaction / "schematron"
    stylesheets = (
        (base / "PINT-UBL-validation-preprocessed.xslt", "pint_shared_schematron"),
        (base / "PINT-jurisdiction-aligned-rules.xslt", "pint_om_schematron"),
    )
    errors, warnings = [], []
    with PySaxonProcessor(license=False) as processor:
        source = processor.parse_xml(xml_text=ubl_xml)
        compiler = processor.new_xslt30_processor()
        for stylesheet, source_name in stylesheets:
            executable = compiler.compile_stylesheet(stylesheet_file=str(stylesheet))
            svrl_text = executable.transform_to_string(xdm_node=source)
            svrl = ET.fromstring(svrl_text)
            for node in svrl.findall(f".//{{{NS_SVRL}}}failed-assert"):
                rule_id = node.attrib.get("id", "PINT-OM")
                severity = node.attrib.get("flag") or node.attrib.get("role") or "fatal"
                text_node = node.find(f"{{{NS_SVRL}}}text")
                message = " ".join("".join(text_node.itertext()).split()) if text_node is not None else rule_id
                field = _path_from_svrl(rule_id, node.attrib.get("location", ""))
                item = _error(rule_id, field, _business_term(field), message, source_name, severity)
                (warnings if severity.lower() == "warning" else errors).append(item)
    return errors, warnings


def validate_pint_om_payload(payload, *, include_ubl=False):
    serializer = PintOmInvoiceSerializer(data=payload)
    if not serializer.is_valid():
        return {
            "valid": False,
            "document_type": None,
            "invoice_type_code": None,
            "specification": "pint-om",
            "specification_version": SPECIFICATION_VERSION,
            "errors": _flatten_serializer_errors(serializer.errors),
            "warnings": [],
        }
    data = serializer.validated_data
    code = data["header"]["ibt_003_invoice_type_code"]
    ubl_xml = map_json_to_ubl(data)
    semantic_errors = _semantic_errors(data)
    schematron_errors, warnings = _run_official_schematron(ubl_xml, code)
    errors = semantic_errors + schematron_errors
    # One failed assertion can be detected in both the semantic preflight and the
    # official Schematron. Preserve the official finding and remove exact duplicates.
    unique = []
    seen = set()
    for item in errors:
        key = (item["code"], item["field"], item["message"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    result = {
        "valid": not unique,
        "document_type": "credit_note" if code in CREDIT_NOTE_CODES else "invoice",
        "invoice_type_code": code,
        "specification": "pint-om-self-billing" if code in SELF_BILLED_CODES else "pint-om",
        "specification_version": SPECIFICATION_VERSION,
        "errors": unique,
        "warnings": warnings,
    }
    if include_ubl:
        result["ubl_xml"] = ubl_xml
    result["validated_data"] = data
    return result
