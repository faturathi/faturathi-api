from django.contrib import admin

from .models import Document, DocumentLine
from apps.utils.admin_mixins import TenantAdminMixin


class DocumentLineInline(admin.TabularInline):
    model = DocumentLine
    extra = 0


@admin.register(DocumentLine)
class DocumentLineAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["document", "line_id", "item_name", "quantity", "unit_price", "vat_category", "line_net"]
    list_filter = ["vat_category", "unit_code"]
    search_fields = ["document__invoice_number", "item_name"]


@admin.register(Document)
class DocumentAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["invoice_number", "company", "direction", "document_type", "status",
                     "source", "issue_date", "tax_inclusive_amount"]
    list_filter = ["direction", "status", "document_type", "source"]
    search_fields = ["invoice_number", "counterparty_name", "counterparty_vatin"]
    readonly_fields = ["doc_type", "is_b2c", "uuid_v5"]
    inlines = [DocumentLineInline]
