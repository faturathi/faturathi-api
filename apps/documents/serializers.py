from rest_framework import serializers

from .models import Document, DocumentLine
from .pint_om import refresh_pint_snapshot
from .services import recompute_totals


class DocumentLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentLine
        fields = ["line_id", "item_name", "description", "quantity", "unit_code",
                  "unit_price", "discount", "vat_category", "vat_rate", "line_net"]
        read_only_fields = ["line_net"]


class DocumentSerializer(serializers.ModelSerializer):
    """Full internal representation with writable nested lines. Persists via recompute_totals."""

    lines = DocumentLineSerializer(many=True)

    class Meta:
        model = Document
        fields = [
            "id", "direction", "document_type", "doc_type", "is_b2c", "is_export",
            "invoice_number", "uuid_v5",
            "transaction_type_code", "issue_date", "issue_time", "due_date", "tax_point_date",
            "customer", "counterparty_name", "counterparty_vatin", "counterparty_endpoint",
            "currency", "line_extension_amount", "allowance_total", "charge_total",
            "tax_exclusive_amount", "tax_amount", "tax_inclusive_amount", "payable_amount",
            "payment_means_code", "payment_iban", "payment_terms", "status", "billing_reference",
            "source", "notes", "ap_status", "erp_system", "extra_data",
            "company", "created_at", "updated_at", "lines",
        ]
        read_only_fields = [
            "id", "doc_type", "is_b2c", "uuid_v5", "line_extension_amount", "tax_exclusive_amount",
            "tax_amount", "tax_inclusive_amount", "payable_amount", "company", "created_at", "updated_at",
        ]

    def create(self, validated_data):
        lines_data = validated_data.pop("lines")
        document = Document.objects.create(**validated_data)
        for line in lines_data:
            DocumentLine.objects.create(
                document=document, company=document.company, created_by=document.created_by, **line)
        recompute_totals(document)
        refresh_pint_snapshot(document)
        return document

    def update(self, instance, validated_data):
        lines_data = validated_data.pop("lines", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if lines_data is not None:
            instance.lines.all().delete()
            for line in lines_data:
                DocumentLine.objects.create(
                    document=instance, company=instance.company, created_by=instance.created_by, **line)
        recompute_totals(instance)
        refresh_pint_snapshot(instance)
        return instance
