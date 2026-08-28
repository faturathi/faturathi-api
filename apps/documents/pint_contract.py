"""Canonical lower-snake-case REST contract for PINT-OM 1.0.1.

The public DTO deliberately retains PINT business-term identifiers.  This keeps a
stable trace from REST JSON to UBL and to an SVRL assertion without exposing the
database representation as the integration contract.
"""

from rest_framework import serializers


class StrictSerializer(serializers.Serializer):
    """Reject unknown properties instead of silently discarding integration data."""

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            return super().to_internal_value(data)
        unknown = sorted(set(data) - set(self.fields))
        if unknown:
            raise serializers.ValidationError({key: ["Unknown property."] for key in unknown})
        return super().to_internal_value(data)


class HeaderSerializer(StrictSerializer):
    btom_001_invoice_transaction_type = serializers.RegexField(r"^[01]{20}$")
    btom_002_invoice_uuid = serializers.UUIDField()
    ibt_001_invoice_number = serializers.CharField(max_length=40)
    ibt_002_invoice_issue_date = serializers.DateField()
    ibt_168_invoice_issue_time = serializers.TimeField()
    ibt_003_invoice_type_code = serializers.ChoiceField(choices=("380", "381", "383", "389", "261"))
    ibt_024_specification_identifier = serializers.CharField(max_length=100)
    ibt_023_business_process_type = serializers.CharField(max_length=100)
    ibt_005_invoice_currency_code = serializers.CharField(min_length=3, max_length=3)
    ibt_006_vat_accounting_currency = serializers.CharField(min_length=3, max_length=3, required=False)
    ibt_007_vat_point_date = serializers.DateField(required=False)
    ibt_009_payment_due_date = serializers.DateField(required=False)
    ibt_010_buyer_reference = serializers.CharField(max_length=100, required=False)
    ibt_013_purchase_order_reference = serializers.CharField(max_length=100, required=False)
    ibt_022_invoice_note = serializers.CharField(max_length=500, required=False, allow_blank=True)
    btom_003_currency_exchange_rate = serializers.DecimalField(
        max_digits=18, decimal_places=7, required=False, min_value=0
    )


class SellerDetailsSerializer(StrictSerializer):
    ibt_027_seller_name = serializers.CharField(max_length=200)
    ibt_029_seller_identifier = serializers.CharField(max_length=50, required=False)
    ibt_029_1_seller_identifier_scheme = serializers.CharField(max_length=20, required=False)
    ibt_031_seller_vatin = serializers.CharField(max_length=14)
    ibt_031_1_tax_scheme_code = serializers.CharField(max_length=10, default="VAT")
    ibt_034_seller_electronic_address = serializers.CharField(max_length=50)
    ibt_034_1_scheme_identifier = serializers.CharField(max_length=10)
    ibt_035_seller_address_line_1 = serializers.CharField(max_length=200)
    ibt_036_seller_address_line_2 = serializers.CharField(max_length=200)
    ibt_162_seller_address_line_3 = serializers.CharField(max_length=200)
    ibt_037_seller_city = serializers.CharField(max_length=80)
    ibt_038_seller_post_code = serializers.CharField(max_length=20)
    ibt_040_seller_country_code = serializers.CharField(min_length=2, max_length=2)
    ibt_041_seller_contact_name = serializers.CharField(max_length=100, required=False)
    ibt_042_seller_contact_telephone = serializers.CharField(max_length=30)
    ibt_043_seller_contact_email = serializers.EmailField(required=False)


class BuyerDetailsSerializer(StrictSerializer):
    ibt_044_buyer_name = serializers.CharField(max_length=200)
    ibt_046_buyer_identifier = serializers.CharField(max_length=50, required=False)
    ibt_046_1_buyer_identifier_scheme = serializers.CharField(max_length=20, required=False)
    ibt_048_buyer_vatin = serializers.CharField(max_length=14, required=False, allow_blank=True)
    ibt_048_1_tax_scheme_code = serializers.CharField(max_length=10, required=False, allow_blank=True)
    ibt_049_buyer_electronic_address = serializers.CharField(max_length=50, required=False, allow_blank=True)
    ibt_049_1_scheme_identifier = serializers.CharField(max_length=10, required=False, allow_blank=True)
    ibt_050_buyer_address_line_1 = serializers.CharField(max_length=200, required=False, allow_blank=True)
    ibt_051_buyer_address_line_2 = serializers.CharField(max_length=200, required=False, allow_blank=True)
    ibt_163_buyer_address_line_3 = serializers.CharField(max_length=200, required=False, allow_blank=True)
    ibt_052_buyer_city = serializers.CharField(max_length=80, required=False, allow_blank=True)
    ibt_053_buyer_post_code = serializers.CharField(max_length=20, required=False, allow_blank=True)
    ibt_055_buyer_country_code = serializers.CharField(min_length=2, max_length=2, default="OM")


class PaymentDetailsSerializer(StrictSerializer):
    ibt_081_payment_means_code = serializers.CharField(max_length=3, required=False)
    ibt_084_payment_account_identifier = serializers.CharField(max_length=34, required=False, allow_blank=True)
    ibt_020_payment_terms_note = serializers.CharField(max_length=200, required=False, allow_blank=True)


class TotalsSerializer(StrictSerializer):
    ibt_106_sum_of_line_net_amount = serializers.DecimalField(max_digits=18, decimal_places=3)
    ibt_107_sum_of_allowances = serializers.DecimalField(max_digits=18, decimal_places=3, default=0)
    ibt_108_sum_of_charges = serializers.DecimalField(max_digits=18, decimal_places=3, default=0)
    ibt_109_invoice_total_without_vat = serializers.DecimalField(max_digits=18, decimal_places=3)
    ibt_110_invoice_total_vat_amount = serializers.DecimalField(max_digits=18, decimal_places=3)
    ibt_111_vat_amount_accounting_currency = serializers.DecimalField(
        max_digits=18, decimal_places=3, required=False
    )
    ibt_112_invoice_total_with_vat = serializers.DecimalField(max_digits=18, decimal_places=3)
    ibt_113_paid_amount = serializers.DecimalField(max_digits=18, decimal_places=3, default=0)
    ibt_114_rounding_amount = serializers.DecimalField(max_digits=18, decimal_places=3, default=0)
    ibt_115_amount_due_for_payment = serializers.DecimalField(max_digits=18, decimal_places=3)


class VatBreakdownSerializer(StrictSerializer):
    ibt_116_vat_category_taxable_amount = serializers.DecimalField(max_digits=18, decimal_places=3)
    ibt_117_vat_category_tax_amount = serializers.DecimalField(max_digits=18, decimal_places=3)
    ibt_118_vat_category_code = serializers.ChoiceField(choices=("S", "Z", "E", "O"))
    ibt_118_1_tax_scheme_code = serializers.CharField(max_length=10, default="VAT")
    ibt_119_vat_category_rate = serializers.DecimalField(max_digits=6, decimal_places=2)
    ibt_120_vat_exemption_reason_text = serializers.CharField(max_length=200, required=False)
    ibt_121_vat_exemption_reason_code = serializers.CharField(max_length=30, required=False)


class InvoiceLineSerializer(StrictSerializer):
    ibt_126_line_identifier = serializers.CharField(max_length=30)
    ibt_127_line_note = serializers.CharField(max_length=300, required=False, allow_blank=True)
    ibt_129_invoiced_quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    ibt_130_quantity_unit_code = serializers.CharField(max_length=6)
    ibt_131_line_net_amount = serializers.DecimalField(max_digits=18, decimal_places=3)
    ibt_146_item_net_price = serializers.DecimalField(max_digits=18, decimal_places=3)
    ibt_151_item_vat_category_code = serializers.ChoiceField(choices=("S", "Z", "E", "O"))
    ibt_152_item_vat_rate = serializers.DecimalField(max_digits=6, decimal_places=2)
    ibt_153_item_name = serializers.CharField(max_length=200)
    btom_016_line_vat_amount = serializers.DecimalField(max_digits=18, decimal_places=3)
    btom_017_line_total_including_vat = serializers.DecimalField(max_digits=18, decimal_places=3)
    btom_019_goods_or_services_identification = serializers.ChoiceField(
        choices=("G", "S"), required=False
    )
    ibt_158_item_classification_identifier = serializers.CharField(max_length=30, required=False)
    ibt_158_1_item_classification_scheme = serializers.CharField(max_length=10, required=False)
    btom_033_industrial_classification_code = serializers.CharField(max_length=20, required=False)
    btom_033_1_scheme_name = serializers.CharField(max_length=10, required=False)


class BillingReferenceSerializer(StrictSerializer):
    ibt_025_preceding_invoice_reference = serializers.CharField(max_length=40)
    btom_031_preceding_invoice_uuid = serializers.UUIDField(required=False)
    ibt_026_preceding_invoice_issue_date = serializers.DateField(required=False)
    btom_032_credit_debit_note_reason_code = serializers.ChoiceField(
        choices=("CAN", "VAT", "VAL", "QTY")
    )
    btom_034_adjustment_reason = serializers.CharField(max_length=300)


class PintOmInvoiceSerializer(StrictSerializer):
    header = HeaderSerializer()
    seller_details = SellerDetailsSerializer()
    buyer_details = BuyerDetailsSerializer()
    payment_details = PaymentDetailsSerializer(required=False)
    billing_reference = BillingReferenceSerializer(required=False)
    totals = TotalsSerializer()
    vat_breakdown = VatBreakdownSerializer(many=True, min_length=1)
    lines = InvoiceLineSerializer(many=True, min_length=1)
    company = serializers.CharField(required=False, write_only=True)
    branch = serializers.CharField(required=False, allow_blank=True, write_only=True)
