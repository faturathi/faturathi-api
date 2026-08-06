import uuid

from apps.utils.constants import OTA_NAMESPACE

NAMESPACE = uuid.UUID(OTA_NAMESPACE)


def generate(document) -> uuid.UUID:
    """
    BTOM-002: uuid5(OTA_NAMESPACE, "VATIN TYPE INVNO DATE VAT TOTAL".upper()).
    6 space-delimited fields, no scheme id. "Seller" = the invoice-issuing party:
    company.vat_number for AR, counterparty_vatin for AP (mirrors faturathi-ui/server.ts).
    """
    seller_vat = document.company.vat_number if document.direction == "AR" else document.counterparty_vatin
    input_str = " ".join([
        seller_vat or "",
        "380",
        document.invoice_number,
        document.issue_date.isoformat(),
        f"{document.tax_amount:.3f}",
        f"{document.tax_inclusive_amount:.3f}",
    ]).upper()
    return uuid.uuid5(NAMESPACE, input_str)
