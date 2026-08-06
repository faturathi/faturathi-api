import re

from rest_framework import serializers

from apps.utils.constants import ENTITY_GROUP_VATIN_REJECTION, GROUP_VATIN_REGEX, VATIN_REGEX

from .models import Company, CompanyGroup, Customer


class EntitySerializer(serializers.ModelSerializer):
    """Matches faturathi-ui's /api/entities contract: id, name, vatin, pid, prefixes[], status."""

    name = serializers.CharField(source="name_en")
    vatin = serializers.CharField(source="vat_number")
    pid = serializers.CharField(source="peppol_participant_id", required=False)
    status = serializers.SerializerMethodField()
    nameAr = serializers.CharField(source="name_ar", required=False, allow_blank=True)
    crNum = serializers.CharField(source="cr_number")
    branchId = serializers.CharField(source="branch_id_code", required=False)
    email = serializers.EmailField(source="contact_email", required=False, allow_blank=True)
    phone = serializers.CharField(source="contact_phone", required=False, allow_blank=True)
    invoicePrefix = serializers.CharField(source="invoice_prefix", required=False)
    invoiceSuffix = serializers.CharField(source="invoice_suffix", required=False)
    creditNoteSuffix = serializers.CharField(source="credit_note_suffix", required=False)

    class Meta:
        model = Company
        fields = ["id", "name", "nameAr", "vatin", "pid", "prefixes", "status",
                  "short_code", "entity_type", "crNum", "branchId", "address", "city",
                  "email", "phone", "invoicePrefix", "invoiceSuffix", "creditNoteSuffix", "is_active"]
        read_only_fields = ["id", "status"]

    def get_status(self, obj) -> str:
        return "Registered" if obj.is_active else "Terminated"

    def validate_vatin(self, value):
        if re.match(GROUP_VATIN_REGEX, value or ""):
            raise serializers.ValidationError(ENTITY_GROUP_VATIN_REJECTION)
        if not re.match(VATIN_REGEX, value or ""):
            raise serializers.ValidationError(ENTITY_GROUP_VATIN_REJECTION)
        return value

    def create(self, validated_data):
        validated_data.setdefault("peppol_participant_id", f"0248:{validated_data['vat_number']}")
        return super().create(validated_data)


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "name", "vatin", "peppol_endpoint", "is_walkin", "email", "phone",
                  "billing_address", "city", "postal_code", "country_code",
                  "company", "created_at", "updated_at"]
        read_only_fields = ["id", "company", "created_at", "updated_at"]


class CompanyGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyGroup
        fields = ["id", "name", "group_vatin"]
