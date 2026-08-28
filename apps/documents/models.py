from django.db import models

from apps.utils.constants import DOCUMENT_TYPE_BY_KEY
from core.models import TenantModel


class Document(TenantModel):
    DIRECTION_CHOICES = [("AR", "AR / Sales"), ("AP", "AP / Purchase")]
    DOC_TYPE_CHOICES = [
        ("380", "Standard Tax Invoice"), ("381", "Credit Note"), ("383", "Debit Note"),
        ("389", "Self-Billed Invoice"), ("261", "Self-Billed Credit Note"),
    ]
    DOCUMENT_TYPE_CHOICES = [(entry["key"], entry["label"]) for entry in DOCUMENT_TYPE_BY_KEY.values()]
    STATUS_CHOICES = [
        ("DRAFT", "Draft"), ("VALIDATED", "Validated"), ("PENDING", "Pending"),
        ("SUBMITTED", "Submitted"), ("SENT", "Sent"), ("REPORTED", "Reported"),
        ("REJECTED", "Rejected"), ("CANCELLED", "Cancelled"),
    ]
    SOURCE_CHOICES = [
        ("MANUAL", "Manual Entry"), ("REST_API", "REST API"), ("BATCH", "File Upload"),
        ("SFTP", "SFTP Sync"), ("ERP", "ERP Integration"), ("AP_INBOUND", "AP Inbound REST API"),
    ]
    PAYMENT_MEANS_CHOICES = [("10", "Cash"), ("30", "Credit Transfer")]

    # identity
    direction = models.CharField(max_length=2, choices=DIRECTION_CHOICES)
    document_type = models.CharField(
        max_length=20, choices=DOCUMENT_TYPE_CHOICES, default="STANDARD_380")  # the UI's type selector
    doc_type = models.CharField(max_length=3, choices=DOC_TYPE_CHOICES, default="380")  # derived, see save()
    is_b2c = models.BooleanField(default=False)  # derived, see save()
    is_export = models.BooleanField(default=False)
    invoice_number = models.CharField(max_length=40)  # unique per company
    uuid_v5 = models.UUIDField(null=True, blank=True)  # BTOM-002, set on validation/submit
    transaction_type_code = models.CharField(max_length=20, default="10000000000000000000")  # BTOM-001

    # dates
    issue_date = models.DateField()
    issue_time = models.TimeField()
    due_date = models.DateField(null=True, blank=True)
    tax_point_date = models.DateField(null=True, blank=True)

    # parties (seller = self.company for AR; for AP seller data sits in counterparty_* fields)
    customer = models.ForeignKey(
        "company.Customer", null=True, blank=True, on_delete=models.PROTECT, related_name="documents")
    branch = models.ForeignKey(
        "company.CompanyBranch", null=True, blank=True, on_delete=models.PROTECT,
        related_name="documents",
        help_text="Operational branch/outlet; shares the document company's VATIN.",
    )
    counterparty_name = models.CharField(max_length=200, blank=True)
    counterparty_vatin = models.CharField(max_length=14, blank=True)
    counterparty_endpoint = models.CharField(max_length=30, blank=True)

    # money (OMR, 3dp stored, 2dp validated)
    currency = models.CharField(max_length=3, default="OMR")
    line_extension_amount = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    allowance_total = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    charge_total = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    tax_exclusive_amount = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    tax_inclusive_amount = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    payable_amount = models.DecimalField(max_digits=14, decimal_places=3, default=0)

    # payment
    payment_means_code = models.CharField(max_length=3, choices=PAYMENT_MEANS_CHOICES, default="30")
    payment_iban = models.CharField(max_length=34, blank=True)
    payment_terms = models.CharField(max_length=200, blank=True)

    # lifecycle
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="DRAFT")
    billing_reference = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="corrections")
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default="MANUAL")
    notes = models.CharField(max_length=255, blank=True)

    # AR/AP + ERP metadata (addendum D.3)
    ap_status = models.CharField(max_length=40, blank=True)  # "Pending Approver Review" / "Approved · posted to ERP"
    erp_system = models.CharField(max_length=40, blank=True)

    # Overflow for transaction-dependent PINT-OM terms (addresses, GTIN, allowances/charges
    # breakdown, delivery info, the raw ingested IBT-named payload, ...). Anything promoted to a
    # real column above should be read from that column, not from here — this is long-tail only.
    extra_data = models.JSONField(default=dict, blank=True)

    class Meta(TenantModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["company", "invoice_number"], condition=models.Q(is_deleted=False),
                name="uniq_invoice_no_per_company")
        ]

    def save(self, *args, **kwargs):
        mapping = DOCUMENT_TYPE_BY_KEY.get(self.document_type)
        if mapping:
            self.doc_type = mapping["code"]
            self.is_b2c = mapping["is_b2c"]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.invoice_number


class DocumentLine(TenantModel):
    VAT_CATEGORY_CHOICES = [("S", "Standard 5%"), ("Z", "Zero"), ("E", "Exempt")]

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="lines")
    line_id = models.PositiveSmallIntegerField()  # 1,2,3...
    item_name = models.CharField(max_length=200)
    description = models.CharField(max_length=255, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    unit_code = models.CharField(max_length=6, default="EA")
    unit_price = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    discount = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    vat_category = models.CharField(max_length=2, choices=VAT_CATEGORY_CHOICES, default="S")
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=5)
    line_net = models.DecimalField(max_digits=14, decimal_places=3, default=0)  # qty*price - discount

    class Meta(TenantModel.Meta):
        ordering = ["line_id"]

    def save(self, *args, **kwargs):
        if self.document_id:
            self.company_id = self.document.company_id
        super().save(*args, **kwargs)
