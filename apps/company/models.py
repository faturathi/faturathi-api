from django.db import models
from django.core.exceptions import ValidationError

from core.models import BaseModel, TenantModel


class CompanyGroup(BaseModel):
    """VAT filing group, e.g. 'Faturathi Demo Group'. Never appears on Peppol itself."""

    name = models.CharField(max_length=120)
    group_vatin = models.CharField(max_length=14)  # OM12xxxxxxxx — VAT filing only
    normalized_name = models.CharField(max_length=120, null=True, blank=True, unique=True, editable=False)
    normalized_vatin = models.CharField(max_length=14, null=True, blank=True, unique=True, editable=False)

    def clean(self):
        super().clean()
        name_key = self.name.strip().casefold()
        vat_key = self.group_vatin.strip().upper()
        conflicts = CompanyGroup.all_objects.filter(is_deleted=False).exclude(pk=self.pk)
        if conflicts.filter(name__iexact=self.name.strip()).exists():
            raise ValidationError({"name": "A VAT group with this name already exists."})
        if conflicts.filter(group_vatin=vat_key).exists():
            raise ValidationError({"group_vatin": "A VAT group with this group VATIN already exists."})
        self.normalized_name = name_key
        self.normalized_vatin = vat_key

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Company(BaseModel):
    """THE TENANT: one legal entity registered on Peppol with its own OM11 VATIN."""

    ENTITY_TYPE_CHOICES = [("HQ", "HQ"), ("SUBSIDIARY", "Subsidiary"), ("BRANCH", "Branch")]

    company_group = models.ForeignKey(
        CompanyGroup, null=True, blank=True, on_delete=models.SET_NULL, related_name="companies")
    short_code = models.CharField(max_length=4, blank=True)  # "E1", "E2", "E3"
    name_en = models.CharField(max_length=200)
    name_ar = models.CharField(max_length=200, blank=True)
    cr_number = models.CharField(max_length=20, unique=True)
    vat_number = models.CharField(max_length=14, unique=True)  # OM11xxxxxxxx
    peppol_participant_id = models.CharField(max_length=30)  # "0248:OM11xxxxxxxx"
    entity_type = models.CharField(max_length=12, choices=ENTITY_TYPE_CHOICES, default="HQ")
    branch_id_code = models.CharField(max_length=4, default="0000")
    invoice_prefix = models.CharField(max_length=12, default="INV-")
    invoice_suffix = models.CharField(max_length=8, default="/OM")
    credit_note_suffix = models.CharField(max_length=8, default="/CN")
    next_invoice_number = models.PositiveIntegerField(default=1)
    prefixes = models.JSONField(default=list, blank=True)  # ["IIS-", "INV-"]
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=60, default="Muscat")
    postal_code = models.CharField(max_length=10, blank=True)
    country_code = models.CharField(max_length=2, default="OM")
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["short_code"]

    def __str__(self):
        return f"{self.short_code} {self.name_en}".strip()


class CompanyBranch(TenantModel):
    """Operational outlet/branch under one legal company and one VAT registration.

    A branch is deliberately not a Company and is never a Peppol participant or tenant
    boundary.  It only identifies where a document originated and which local numbering
    series should be used (for example three coffee shops using the same OM11 VATIN).
    """

    code = models.CharField(max_length=12)
    name = models.CharField(max_length=120)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=60, default="Muscat")
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    invoice_prefix = models.CharField(max_length=20, default="INV-")
    invoice_suffix = models.CharField(max_length=12, default="/OM")
    credit_note_prefix = models.CharField(max_length=20, default="CN-")
    credit_note_suffix = models.CharField(max_length=12, default="/CN")
    next_invoice_number = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta(TenantModel.Meta):
        ordering = ["company__short_code", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"], condition=models.Q(is_deleted=False),
                name="uniq_active_branch_code_per_company",
            )
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"


class Customer(TenantModel):
    """Buyer/counterparty book per tenant."""

    name = models.CharField(max_length=200)
    vatin = models.CharField(max_length=14, blank=True)  # blank for B2C walk-in
    peppol_endpoint = models.CharField(max_length=30, blank=True)  # "0248:..."
    is_walkin = models.BooleanField(default=False)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    billing_address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=60, blank=True)
    postal_code = models.CharField(max_length=10, blank=True)
    country_code = models.CharField(max_length=2, default="OM")

    def __str__(self):
        return self.name
