"""Hardcoded master data for the Faturathi demo (no DB tables per Golden Rule #3)."""

UNIT_CODES = {"EA", "KGM", "HUR", "LTR", "MTR", "DAY"}

VAT_CATEGORIES = [
    {"code": "S", "label": "S 5%", "rate": 5, "name": "Oman Standard Rate (5%)",
     "desc": "Standard 5% VAT rate applicable for general goods & services"},
    {"code": "Z", "label": "Z 0%", "rate": 0, "name": "Oman Zero Rate (0% Export)",
     "desc": "Zero-rated VAT for GCC export & international trade"},
    {"code": "E", "label": "E Exempt", "rate": 0, "name": "Exempt Services (0%)",
     "desc": "Statutory exempt financial & healthcare services"},
]

DOC_TYPES = {
    "380": "Standard Invoice",
    "381": "Credit Note",
    "383": "Debit Note",
    "389": "Self-Billed Invoice",
    "261": "Self-Billed Credit Note",
    "388_EXPORT": "Export",
    "388_B2C": "Simplified Invoice — B2C",
}

# The document-type selector (Quick Document Creator tiles): one clean key the frontend
# picks directly. "code" is the UNCL1001 IBT-003 value actually stored on Document.doc_type;
# is_b2c/is_self_billed are derived flags Document.save() syncs from this key.
DOCUMENT_TYPE_CATALOG = [
    {"key": "STANDARD_380", "code": "380", "label": "Standard Tax Invoice",
     "sublabel": "UNCL1001 Code: 380", "is_b2c": False, "direction_hint": "AR"},
    {"key": "SIMPLIFIED_B2C", "code": "380", "label": "Simplified Tax Invoice",
     "sublabel": "B2C profile", "is_b2c": True, "direction_hint": "AR"},
    {"key": "CREDIT_NOTE_381", "code": "381", "label": "Credit Note",
     "sublabel": "UNCL1001 Code: 381", "is_b2c": False, "direction_hint": "AR"},
    {"key": "DEBIT_NOTE_383", "code": "383", "label": "Debit Note",
     "sublabel": "UNCL1001 Code: 383", "is_b2c": False, "direction_hint": "AR"},
    {"key": "SELF_BILLED_389", "code": "389", "label": "Self-Billed Invoice",
     "sublabel": "UNCL1001 Code: 389", "is_b2c": False, "direction_hint": "AP"},
    {"key": "SELF_BILLED_CN_261", "code": "261", "label": "Self-Billed Credit Note",
     "sublabel": "UNCL1001 Code: 261", "is_b2c": False, "direction_hint": "AP"},
]
DOCUMENT_TYPE_BY_KEY = {entry["key"]: entry for entry in DOCUMENT_TYPE_CATALOG}
CN_DN_DOCUMENT_TYPE_KEYS = {"CREDIT_NOTE_381", "DEBIT_NOTE_383", "SELF_BILLED_CN_261"}

PAYMENT_MEANS = {"10": "Cash", "30": "Credit Transfer"}

OTA_NAMESPACE = "e0bc4ac8-b025-46e5-a76d-0c893fc3027e"

ERROR_CODES = {
    "C1": "Missing mandatory field",
    "C2": "Invalid transaction type bitmap",
    "C3": "Invalid date",
    "C4": "Invalid currency",
    "C5": "Invalid Buyer VATIN",
    "C6": "Invalid VAT rate for category",
    "C7": "Invalid unit code",
    "C8": "Totals mismatch",
    "C9": "Missing billing reference",
    "C10": "Duplicate invoice number",
    "C11": "Invalid payment means / missing IBAN",
}

B2C_DUMMY = "0248:997770000099"
EXPORT_DUMMY = "0248:997770000097"

# BTOM-001: 20-char transaction-type bitmap. Position 2 = simplified(B2C), position 3 = credit note,
# position 4 = export (see faturathi-ui/src/lib/omanValidator.ts).
TT_STANDARD = "10000000000000000000"
TT_B2C = "11000000000000000000"
TT_CREDIT_NOTE = "10100000000000000000"
TT_EXPORT = "10010000000000000000"

VATIN_REGEX = r"^OM11\d{8}$"
GROUP_VATIN_REGEX = r"^OM12\d{8}$"

BR_O_02_MESSAGE = (
    "Schematron Error BR-O-02: Buyer VATIN '{vatin}' violates Oman PINT-OM syntax rules. "
    "Must start with 'OM' followed by 8–12 digits (e.g. OM1100887700)."
)

ENTITY_GROUP_VATIN_REJECTION = (
    'VATIN must be "OM11" followed by exactly 8 digits (12 characters). '
    "OM12 group VATINs cannot be registered as individual Peppol participants."
)
