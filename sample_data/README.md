# PINT-OM 73-field document samples

The six CSV files and `faturathi_pint_om_73_field_samples.xlsx` cover every document profile
returned by `GET /api/document-types`. Each CSV contains nine Faturathi processing columns plus
all 73 fields from the April 2026 Oman PINT-OM reference guide.

## Import

- `POST /api/upload-batch/file` — multipart form field `file`; accepts CSV or XLSX.
- `POST /api/upload-batch` — JSON `{ "items": [...] }` using the same flat column names.
- `POST /api/invoices` — create a manual/ERP document.
- `POST /api/invoices/inbound` — receive an inbound AP document.
- `POST /api/validate` — receive the nested IBT/BTOM JSON representation.

All routes persist `Document` and `DocumentLine` records and therefore feed the same invoice
register, validation, Peppol submission, reports, logs, and transmission lifecycle.

## Processing and audit

- `GET /api/invoices` — unified tenant-scoped document register.
- `GET /api/invoices/{uuid}` — document summary used by the UI.
- `GET /api/invoices/{uuid}/pint-payload` — canonical OTA-facing JSON snapshot.
- `POST /api/invoices/{uuid}/validate` — validate without dispatch.
- `POST /api/invoices/{uuid}/submit` — validate and process through the Peppol engine.

For multiple lines in CSV, repeat the document header fields on each row. The current importer
creates one document per row; JSON and REST payloads support multiple nested `Lines` directly.
