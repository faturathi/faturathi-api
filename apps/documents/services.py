from decimal import Decimal

from apps.utils.helpers import round_money


def recompute_totals(document) -> None:
    """Recomputes DocumentLine.line_net and all Document total fields (IBT-106..115)."""
    lines = list(document.lines.all())

    line_extension = Decimal("0")
    tax_amount = Decimal("0")
    for line in lines:
        line.line_net = round_money((line.quantity * line.unit_price) - line.discount)
        line.save(update_fields=["line_net"])
        line_extension += line.line_net
        tax_amount += round_money(line.line_net * line.vat_rate / Decimal("100"))

    document.line_extension_amount = round_money(line_extension)
    document.tax_exclusive_amount = round_money(
        line_extension - document.allowance_total + document.charge_total)
    document.tax_amount = round_money(tax_amount)
    document.tax_inclusive_amount = round_money(document.tax_exclusive_amount + document.tax_amount)
    document.payable_amount = document.tax_inclusive_amount
    document.save(update_fields=[
        "line_extension_amount", "tax_exclusive_amount", "tax_amount",
        "tax_inclusive_amount", "payable_amount",
    ])
