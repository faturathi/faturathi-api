import csv
import json
from decimal import ROUND_HALF_UP, Decimal

from django.http import HttpResponse, JsonResponse

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


def json_export(filename: str, rows: list[dict]) -> JsonResponse:
    response = JsonResponse(rows, safe=False, json_dumps_params={"indent": 2, "default": str})
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _sql_literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def sql_export(filename: str, table_name: str, fieldnames: list[str], rows: list[dict]) -> HttpResponse:
    """Plain portable `INSERT` statements for the given rows — not a `pg_dump` binary/custom-format
    dump. A real `pg_dump` operates on whole tables/database and has no notion of tenant or date-
    range scoping, so shelling out to it here would risk exporting other tenants' data; this stays
    at the same tenant-filtered row level as the CSV/JSON exports, just serialized as SQL text."""
    lines = [
        f"-- Faturathi archive export: {table_name} ({len(rows)} rows)",
        f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(f'{f} TEXT' for f in fieldnames)});",
    ]
    for row in rows:
        values = ", ".join(_sql_literal(row.get(f)) for f in fieldnames)
        lines.append(f"INSERT INTO {table_name} ({', '.join(fieldnames)}) VALUES ({values});")
    response = HttpResponse("\n".join(lines) + "\n", content_type="application/sql")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
