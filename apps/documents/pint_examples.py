"""Canonical PINT-OM v1.0.1 request examples used by docs and the React editor."""

from copy import deepcopy
import uuid

from .pint_pipeline import (
    PINT_OM_BILLING, PINT_OM_SELF_BILLING, PROFILE_BILLING, PROFILE_SELF_BILLING,
)


def _uuid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://api.faturathi.com/pint-om/examples/{name}"))


def _base(name, number, code="380", transaction_type="10000000000000000000"):
    return {
        "header": {
            "btom_001_invoice_transaction_type": transaction_type,
            "btom_002_invoice_uuid": _uuid(name),
            "ibt_001_invoice_number": number,
            "ibt_002_invoice_issue_date": "2026-08-20",
            "ibt_168_invoice_issue_time": "10:14:22",
            "ibt_003_invoice_type_code": code,
            "ibt_024_specification_identifier": PINT_OM_BILLING,
            "ibt_023_business_process_type": PROFILE_BILLING,
            "ibt_005_invoice_currency_code": "OMR",
            "ibt_007_vat_point_date": "2026-08-20",
            "ibt_009_payment_due_date": "2026-09-19",
            "ibt_022_invoice_note": "Faturathi PINT-OM v1.0.1 API example",
        },
        "seller_details": {
            "ibt_027_seller_name": "International Intelligence Solutions LLC",
            "ibt_029_seller_identifier": "112345678900003",
            "ibt_029_1_seller_identifier_scheme": "OTHID",
            "ibt_031_seller_vatin": "OM1100123456",
            "ibt_031_1_tax_scheme_code": "VAT",
            "ibt_034_seller_electronic_address": "OM1100123456",
            "ibt_034_1_scheme_identifier": "0248",
            "ibt_035_seller_address_line_1": "Way 2317, Building 192",
            "ibt_036_seller_address_line_2": "Ruwi",
            "ibt_162_seller_address_line_3": "Muscat Governorate",
            "ibt_037_seller_city": "Muscat",
            "ibt_038_seller_post_code": "112",
            "ibt_040_seller_country_code": "OM",
            "ibt_041_seller_contact_name": "Ahmed Al-Harthy",
            "ibt_042_seller_contact_telephone": "+96824123456",
            "ibt_043_seller_contact_email": "billing@iis-oman.om",
        },
        "buyer_details": {
            "ibt_044_buyer_name": "Muscat Retail SAOC",
            "ibt_046_buyer_identifier": "112345679000001",
            "ibt_046_1_buyer_identifier_scheme": "OTHID",
            "ibt_048_buyer_vatin": "OM1100654321",
            "ibt_048_1_tax_scheme_code": "VAT",
            "ibt_049_buyer_electronic_address": "OM1100654321",
            "ibt_049_1_scheme_identifier": "0248",
            "ibt_050_buyer_address_line_1": "Al Khuwair Commercial Area",
            "ibt_051_buyer_address_line_2": "Building 44",
            "ibt_163_buyer_address_line_3": "Bawshar",
            "ibt_052_buyer_city": "Muscat",
            "ibt_053_buyer_post_code": "133",
            "ibt_055_buyer_country_code": "OM",
        },
        "payment_details": {
            "ibt_081_payment_means_code": "30",
            "ibt_084_payment_account_identifier": "OM9300001234567890123456",
            "ibt_020_payment_terms_note": "Net 30 days",
        },
        "totals": {
            "ibt_106_sum_of_line_net_amount": "500.000",
            "ibt_107_sum_of_allowances": "0.000",
            "ibt_108_sum_of_charges": "0.000",
            "ibt_109_invoice_total_without_vat": "500.000",
            "ibt_110_invoice_total_vat_amount": "25.000",
            "ibt_111_vat_amount_accounting_currency": "25.000",
            "ibt_112_invoice_total_with_vat": "525.000",
            "ibt_113_paid_amount": "0.000",
            "ibt_114_rounding_amount": "0.000",
            "ibt_115_amount_due_for_payment": "525.000",
        },
        "vat_breakdown": [{
            "ibt_116_vat_category_taxable_amount": "500.000",
            "ibt_117_vat_category_tax_amount": "25.000",
            "ibt_118_vat_category_code": "S",
            "ibt_118_1_tax_scheme_code": "VAT",
            "ibt_119_vat_category_rate": "5.00",
        }],
        "lines": [{
            "ibt_126_line_identifier": "1",
            "ibt_127_line_note": "Enterprise integration service",
            "ibt_129_invoiced_quantity": "1.000",
            "ibt_130_quantity_unit_code": "EA",
            "ibt_131_line_net_amount": "500.000",
            "ibt_146_item_net_price": "500.000",
            "ibt_151_item_vat_category_code": "S",
            "ibt_152_item_vat_rate": "5.00",
            "ibt_153_item_name": "PINT-OM Gateway Integration",
            "btom_016_line_vat_amount": "25.000",
            "btom_017_line_total_including_vat": "525.000",
            "btom_019_goods_or_services_identification": "S",
            "btom_033_industrial_classification_code": "620101",
            "btom_033_1_scheme_name": "CC",
        }],
    }


def get_pint_om_examples():
    standard = _base("b2b-standard", "INV-2026-0001")

    simplified = _base(
        "b2c-simplified", "SINV-2026-0002", transaction_type="01000000000000000000"
    )
    simplified["buyer_details"] = {
        "ibt_044_buyer_name": "Cash Customer",
        "ibt_048_buyer_vatin": "",
        "ibt_049_buyer_electronic_address": "",
        "ibt_055_buyer_country_code": "OM",
    }
    simplified["lines"][0].pop("btom_019_goods_or_services_identification")
    simplified["lines"][0].pop("btom_033_industrial_classification_code")
    simplified["lines"][0].pop("btom_033_1_scheme_name")

    credit = _base("credit-note", "CN-2026-0003", code="381")
    credit.pop("payment_details")
    credit["billing_reference"] = {
        "ibt_025_preceding_invoice_reference": "INV-2026-0001",
        "btom_031_preceding_invoice_uuid": standard["header"]["btom_002_invoice_uuid"],
        "ibt_026_preceding_invoice_issue_date": "2026-08-20",
        "btom_032_credit_debit_note_reason_code": "CAN",
        "btom_034_adjustment_reason": "Return of goods / price adjustment",
    }

    debit = _base("debit-note", "DN-2026-0004", code="383")
    debit["billing_reference"] = deepcopy(credit["billing_reference"])
    debit["billing_reference"]["btom_032_credit_debit_note_reason_code"] = "VAL"
    debit["billing_reference"]["btom_034_adjustment_reason"] = "Additional charge after invoice"

    self_billed = _base(
        "self-billed-invoice", "SBINV-2026-0005", code="389",
        transaction_type="10100000000000000000",
    )
    self_billed["header"]["ibt_024_specification_identifier"] = PINT_OM_SELF_BILLING
    self_billed["header"]["ibt_023_business_process_type"] = PROFILE_SELF_BILLING

    self_billed_credit = _base(
        "self-billed-credit-note", "SBCN-2026-0006", code="261",
        transaction_type="10100000000000000000",
    )
    self_billed_credit["header"]["ibt_024_specification_identifier"] = PINT_OM_SELF_BILLING
    self_billed_credit["header"]["ibt_023_business_process_type"] = PROFILE_SELF_BILLING
    self_billed_credit.pop("payment_details")
    self_billed_credit["billing_reference"] = {
        "ibt_025_preceding_invoice_reference": "SBINV-2026-0005",
        "btom_031_preceding_invoice_uuid": self_billed["header"]["btom_002_invoice_uuid"],
        "ibt_026_preceding_invoice_issue_date": "2026-08-20",
        "btom_032_credit_debit_note_reason_code": "CAN",
        "btom_034_adjustment_reason": "Self-billing correction",
    }

    return {
        "b2b_standard_tax_invoice_380": standard,
        "b2c_simplified_tax_invoice_380": simplified,
        "credit_note_381": credit,
        "debit_note_383": debit,
        "self_billed_invoice_389": self_billed,
        "self_billed_credit_note_261": self_billed_credit,
    }
