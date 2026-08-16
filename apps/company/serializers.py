import re

from rest_framework import serializers

from apps.utils.constants import ENTITY_GROUP_VATIN_REJECTION, GROUP_VATIN_REGEX, VATIN_REGEX

from .models import Company, CompanyBranch, CompanyGroup, Customer


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
    nextInvoiceNumber = serializers.IntegerField(source="next_invoice_number", read_only=True)
    company_group = serializers.PrimaryKeyRelatedField(
        queryset=CompanyGroup.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Company
        fields = ["id", "company_group", "name", "nameAr", "vatin", "pid", "prefixes", "status",
                  "short_code", "entity_type", "crNum", "branchId", "address", "city",
                  "email", "phone", "invoicePrefix", "invoiceSuffix", "creditNoteSuffix",
                  "nextInvoiceNumber", "is_active"]
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


class CompanyBranchSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name_en", read_only=True)
    company_vatin = serializers.CharField(source="company.vat_number", read_only=True)

    class Meta:
        model = CompanyBranch
        fields = [
            "id", "company", "company_name", "company_vatin", "code", "name", "address",
            "city", "contact_email", "contact_phone", "invoice_prefix", "invoice_suffix",
            "credit_note_prefix", "credit_note_suffix", "next_invoice_number", "is_active",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "company", "company_name", "company_vatin", "created_at", "updated_at",
        ]

    def validate_code(self, value):
        return value.strip().upper()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get("request")
        company = self.instance.company if self.instance else getattr(request, "active_company", None)
        if company is None and request is not None:
            requested = request.data.get("company")
            company = Company.objects.filter(
                id__in=getattr(request, "active_company_ids", []), pk=requested
            ).first() if requested else None
        code = attrs.get("code", getattr(self.instance, "code", ""))
        if company and code:
            queryset = CompanyBranch.objects.filter(company=company, code__iexact=code)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError({
                    "code": ["This branch code is already used by the selected company."]
                })
        return attrs


class CompanyGroupSerializer(serializers.ModelSerializer):
    company_count = serializers.SerializerMethodField()

    class Meta:
        model = CompanyGroup
        fields = ["id", "name", "group_vatin", "company_count"]
        read_only_fields = ["id", "company_count"]

    def get_company_count(self, obj):
        return obj.companies.filter(is_active=True).count()

    def validate_group_vatin(self, value):
        if not re.match(GROUP_VATIN_REGEX, value or ""):
            raise serializers.ValidationError('Group VATIN must be "OM12" followed by exactly 8 digits.')
        queryset = CompanyGroup.objects.filter(group_vatin=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("A VAT group with this group VATIN already exists.")
        return value

    def validate_name(self, value):
        value = value.strip()
        queryset = CompanyGroup.objects.filter(name__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("A VAT group with this name already exists.")
        return value
