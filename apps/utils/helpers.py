import csv
from decimal import ROUND_HALF_UP, Decimal

from django.http import HttpResponse

from apps.utils.validators import CN_DOC_TYPES


def round_money(value, dp: int = 3) -> Decimal:
    quantum = Decimal("1").scaleb(-dp)
    return Decimal(value).quantize(quantum, rounding=ROUND_HALF_UP)


def next_invoice_number(company, doc_type: str = "380", issue_date=None) -> str:
    """Simple per-company series counter: PREFIX-YYYY-MM-0001 (CN-prefixed for credit/debit notes)."""
    from django.utils import timezone

    issue_date = issue_date or timezone.localdate()
    prefix = "CN-" if doc_type in CN_DOC_TYPES else company.invoice_prefix
    seq = company.next_invoice_number
    company.next_invoice_number = seq + 1
    company.save(update_fields=["next_invoice_number"])
    return f"{prefix}{issue_date.year}-{issue_date.month:02d}-{seq:04d}"


def csv_export(filename: str, fieldnames: list[str], rows: list[dict]) -> HttpResponse:
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.DictWriter(response, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return response
