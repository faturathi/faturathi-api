# Faturathi Backend

Faturathi is a multi-tenant SaaS backend for Oman PINT-OM electronic invoicing. It provides
invoice and adjustment-document creation, REST/ERP/file ingestion, validation, Peppol/OTA
transmission lifecycle simulation, AP processing, reporting, audit logs, company administration,
and JWT/MFA authentication.

## Technology

- Python 3.13 and Django 6
- Django REST Framework and SimpleJWT
- PostgreSQL
- drf-spectacular OpenAPI 3, Swagger UI, and ReDoc
- Gunicorn on AWS Elastic Beanstalk
- S3 and CloudFront for static/media storage

## Multi-tenancy and row-level isolation

The MVP uses a **shared PostgreSQL database and shared schema with tenant-keyed rows**. It does not
use `django-tenants`, which implements a different architecture: one PostgreSQL schema per tenant.

The business group is the SaaS tenant boundary. A group contains one or more legal `Company`
entities. Operational models inherit `TenantModel` and therefore have a mandatory indexed
`company_id`:

- Customer
- Document and DocumentLine
- Transmission
- SystemConfig and SystemLog
- Notification

Isolation is applied through:

1. JWT authentication and `ResolveActiveCompany` on every protected DRF request.
2. `request.active_company_ids`, limited to companies in the caller's own business group.
3. Tenant-filtered querysets on documents, customers, transmissions, reports, logs and notices.
4. `resolve_write_company`, which rejects ambiguous or out-of-scope writes.
5. Parent tenant inheritance for document lines and transmissions.
6. Tenant-filtered Django Admin querysets and company selectors.
7. Platform-wide access only for a Django superuser or a `SUPERADMIN` role. A company-less viewer
   receives no tenant scope.

This is application-enforced row isolation. PostgreSQL Row-Level Security is not currently enabled.
RLS or schema-per-tenant isolation can be added later as defense in depth, but either requires a
separate connection/session and migration design.

Clients select one legal entity with the `X-Company-ID` header (company UUID or short code). The
special value `group` permits a user to work across companies in their own business group. A
platform administrator must additionally send `X-Business-Group-ID: <group UUID>`; this scopes the
company list and makes `X-Company-ID: group` mean the selected tenant, never the whole platform.

## Local setup

```powershell
cd D:\Projects\Faturathi\backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py seed_uat_demo
python manage.py runserver 8000
```

Configure PostgreSQL in `.env`:

```env
DB_NAME=fathurathi
DB_USER=fathurathi
DB_PASSWORD=fathurathi
DB_HOST=localhost
DB_PORT=5432
```

## Sample data

Use `python manage.py seed_uat_demo` for a new, empty UAT database. It refuses to modify an
environment that already contains companies or business groups unless the explicit `--reset`
option is supplied.

The seed contains:

- 1 business/VAT group
- 3 legal companies
- 5 users
- 11 customers including walk-in customers
- 11 documents and their Peppol transmission histories
- Standard invoices, credit note, debit note, AR and AP examples
- Validated, sent, reported and rejected document/transmission states
- Security, validation, upload, ERP, Peppol, OTA, server, report and system logs

Demo credentials:

```text
Tenant user:   salim.h@intel-sol.om / Demo@1234
Platform user: superadmin@faturathi.netbue.om / Demo@1234
MFA code:      582910
```

The `sample_data/` directory contains CSV examples for all six document profiles and a formatted
Excel workbook containing the 73-field OTA reference structure.

## Django management commands and demonstration data

Run management commands from the backend directory after activating the virtual environment and
configuring the PostgreSQL connection:

```powershell
cd D:\Projects\Faturathi\backend
.\venv\Scripts\Activate.ps1
python manage.py migrate --noinput
```

On Linux, EC2 or Elastic Beanstalk, use the environment's Python executable, for example:

```bash
cd /srv/faturathi/backend
/srv/faturathi/venv/bin/python manage.py migrate --noinput
```

### Populate a new UAT database safely

```powershell
python manage.py seed_uat_demo
```

`seed_uat_demo` is the recommended UAT command. It creates the complete demonstration dataset when
the database has no company/group business data. When existing business data is detected, it exits
with an error and does not change anything.

The generated dataset includes:

- One Oman VAT/business group with an OM12 group VATIN
- Three tenant companies with separate OM11 VATINs and Peppol participant identifiers
- Platform administrator, tenant administrator, approver, maker and viewer accounts
- Tenant-level `SystemConfig` rows and walk-in/registered customers
- Standard AR invoices from manual, REST API, ERP, SFTP and spreadsheet sources
- An AP inbound invoice, credit note and debit note with billing references
- Document lines, calculated VAT totals and canonical PINT-OM JSON snapshots
- Queued/validated, AS4-sent, MLS-reported and OTA-rejected transmission examples
- User notifications and operational audit entries
- INFO, WARNING and ERROR logs covering authentication, validation, file upload, ERP sync,
  Peppol, OTA, application server health, report generation and retryable system errors

This data powers the dashboard counts, invoice register, AR/AP views, lifecycle reports,
transmission screens, notifications and system-log screens.

### Replace an existing environment with UAT data

```powershell
python manage.py seed_uat_demo --reset
```

> **Destructive operation:** `--reset` deletes existing application users, groups, companies,
> customers, documents, transmissions, configurations, notifications and logs before recreating
> the demonstration dataset. Take a verified database backup first. Never run this command against
> a production database.

### Low-level demo reset command

```powershell
python manage.py seed_demo
```

`seed_demo` is the low-level reset used internally by `seed_uat_demo`. It always wipes and rebuilds
the application dataset and does not perform the existing-business-data safety check. Prefer
`seed_uat_demo` for deployment scripts and operator use.

The `ALLOW_SEED_RESET` setting protects only the HTTP reset endpoints (`/api/config/reset-seeds`,
`/api/reset-db` and `/api/clear`). It does not prevent a server operator with shell access from
running `seed_demo`. Production must set `ALLOW_SEED_RESET=False` and restrict shell/SSH access.

### Verify the populated data

```powershell
python manage.py shell -c "from apps.company.models import CompanyGroup,Company; from apps.documents.models import Document; from apps.peppol.models import Transmission; from apps.config.models import SystemLog; from apps.user.models import User; print({'groups':CompanyGroup.objects.count(),'companies':Company.objects.count(),'users':User.objects.count(),'documents':Document.objects.count(),'transmissions':Transmission.objects.count(),'logs':SystemLog.objects.count()})"
```

Expected base totals are one group, three companies, five users, eleven documents, eleven
transmissions and nine demonstration system logs. Additional API activity may increase logs and
notifications.

Useful inspection commands:

```powershell
python manage.py showmigrations
python manage.py check
python manage.py shell -c "from apps.documents.models import Document; print(list(Document.objects.values_list('invoice_number','document_type','status','source')))"
python manage.py shell -c "from apps.config.models import SystemLog; print(list(SystemLog.objects.values_list('action','entity','detail')))"
```

### Create a production administrator without sample data

For production, do not run either seed command. Apply migrations and create a dedicated
administrator instead:

```powershell
python manage.py migrate --noinput
python manage.py createsuperuser
```

## Document types

| Profile | Internal key | UNCL1001 | Direction |
|---|---|---:|---|
| Standard Tax Invoice | `STANDARD_380` | 380 | AR |
| Simplified Tax Invoice | `SIMPLIFIED_B2C` | 380 | AR |
| Credit Note | `CREDIT_NOTE_381` | 381 | AR |
| Debit Note | `DEBIT_NOTE_383` | 383 | AR |
| Self-Billed Invoice | `SELF_BILLED_389` | 389 | AP |
| Self-Billed Credit Note | `SELF_BILLED_CN_261` | 261 | AP |

Important operational fields are relational for filtering and reports. Long-tail OTA data is stored
in `Document.extra_data`; the canonical representation is available under `extra_data.pint_om`.

## Authentication and Swagger

- OpenAPI schema: `GET /api/schema`
- Swagger UI: `GET /api/docs`
- ReDoc: `GET /api/redoc`

Swagger uses the SimpleJWT bearer security scheme. Log in, copy the access token, select
**Authorize**, and enter:

```text
Bearer <access-token>
```

Authentication flow:

```http
POST /api/auth/login
Content-Type: application/json

{"email":"salim.h@intel-sol.om","password":"Demo@1234"}
```

If MFA is required:

```http
POST /api/auth/mfa-verify
Content-Type: application/json

{"email":"salim.h@intel-sol.om","otp":"582910"}
```

Protected request:

```http
GET /api/invoices
Authorization: Bearer <access-token>
X-Company-ID: E1
```

## Principal API endpoints

### Identity and tenant administration

- `POST /api/auth/login`
- `POST /api/auth/mfa-verify`
- `GET /api/auth/me`
- `GET|POST|PATCH|DELETE /api/users`
- `GET|POST|PATCH|DELETE /api/entities`
- `GET|POST|PATCH|DELETE /api/company-groups`
- `GET|POST|PATCH|DELETE /api/customers`
- `GET|POST|PATCH /api/notifications`

### Documents and ingestion

- `GET|POST /api/invoices`
- `GET|PATCH|DELETE /api/invoices/{uuid}`
- `POST /api/invoices/{uuid}/validate`
- `POST /api/invoices/{uuid}/submit`
- `POST /api/invoices/{uuid}/resubmit`
- `POST /api/invoices/{uuid}/approve`
- `POST /api/invoices/{uuid}/cancel`
- `GET /api/invoices/{uuid}/pint-payload`
- `POST /api/invoices/inbound`
- `GET /api/document-types`
- `POST /api/upload-batch`
- `POST /api/upload-batch/file`
- `POST /api/validate`

All creation paths produce the same `Document` and `DocumentLine` records. Manual, REST, ERP,
SFTP, inbound AP, CSV and XLSX documents therefore appear in the same invoice register, reports,
logs and Peppol workflow.

### Peppol, reports and operations

- `GET /api/peppol/transmissions`
- `GET /api/reports/dashboard`
- `GET /api/reports/tax-grid`
- `GET /api/reports/tax-grid/export?format=csv`
- `GET /api/config`
- `GET /api/config/logs`
- `GET /api/health`

Swagger is the authoritative runtime list of endpoints and request/response schemas.

## User roles

| Role | Intended access |
|---|---|
| `SUPERADMIN` | Platform or business-group administration and all document operations |
| `ADMIN` | Tenant setup, companies, customers and user administration |
| `MAKER` | Create and maintain draft/rejected billing documents |
| `APPROVER` | Review, approve and submit documents |
| `VIEWER` | Read-only operational and reporting access |

Object lifecycle rules provide additional restrictions: submitted/reported documents cannot be
edited; rejected, pending and draft documents may be corrected.

## Company and business-group setup

1. A platform administrator creates a `CompanyGroup`.
2. Create one or more legal `Company` records with unique CR, OM11 VATIN and Peppol endpoint.
3. Configure invoice/credit-note numbering prefixes and suffixes.
4. Assign users to a company and role.
5. Create customers or use the tenant walk-in customer.
6. Select the working entity through `X-Company-ID` before writes.

OM12 group VATINs identify filing groups only. Individual Peppol participant companies require an
OM11 VATIN.

## Security

- JWT access and refresh tokens
- MFA-enabled login flow
- Business-group and company row isolation
- Tenant-derived writes; client-supplied tenant IDs are validated against allowed scope
- Soft deletion and creator/timestamp audit fields
- Immutable operational log API
- Production seed reset disabled by environment setting
- HTTPS proxy handling, secure cookies, HSTS and explicit CORS/CSRF origins
- Secrets supplied through environment variables, never committed

The demo MFA code and demo passwords must be replaced before production. Use AWS Secrets Manager
or SSM Parameter Store for database and Django secrets.

## High-level architecture

```text
React client / ERP / CSV-XLSX / External REST
                    |
             JWT + X-Company-ID
                    |
        Django REST API / tenant resolver
          |          |          |
     Documents    Reports    Administration
          |
   PINT-OM validation + canonical 73-field JSON
          |
   Peppol transmission / OTA / MLS lifecycle
          |
      PostgreSQL shared schema
       (company-keyed rows)

AWS: CloudFront -> Elastic Beanstalk/Gunicorn -> RDS PostgreSQL
                      |
                 S3 static/media
```

## Tests and schema validation

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py spectacular --file openapi.yml --validate
```

## AWS deployment

For EC2/RDS deployment, see `Docs/deployment.txt`. For Elastic Beanstalk, see
`DEPLOY_AWS_EB.md`. Pushes to `main` run PostgreSQL-backed tests and can deploy through the AWS
Elastic Beanstalk GitHub workflow.
