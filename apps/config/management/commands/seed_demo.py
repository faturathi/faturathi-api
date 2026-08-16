"""
Wipes and reseeds Faturathi demo data. Users/companies/invoices mirror faturathi-ui/server.ts's
SEED_ENTITIES / SEED_USERS / SEED_INVOICES verbatim (Addendum v1.1 section F), so the frontend
lands on numbers it already expects once wired to this API.
"""

from datetime import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.company.models import Company, CompanyBranch, CompanyGroup, Customer
from apps.config.models import SystemConfig, SystemLog
from apps.config.demo_logs import populate_demo_logs
from apps.documents.models import Document, DocumentLine
from apps.documents.pint_om import build_pint_payload, refresh_pint_snapshot
from apps.documents.services import recompute_totals
from apps.peppol.models import Transmission
from apps.user.models import Notification, User

SEED_PASSWORD = "Demo@1234"

CAT_RATE = {"S": Decimal("5"), "Z": Decimal("0"), "E": Decimal("0")}

SOURCE_BY_CHANNEL = {
    "REST API": "REST_API",
    "SFTP Sync": "SFTP",
    "File Upload": "BATCH",
    "ERP Integration": "ERP",
    "Manual Entry": "MANUAL",
    "AP Inbound REST API (/api/invoices/inbound)": "AP_INBOUND",
}

# Verbatim from faturathi-ui/server.ts SEED_INVOICES.
SEED_INVOICES = [
    dict(n="IIS-2026-08-0099", d="2026-08-02", t="14:20:00", direction="AR", doc_type="380",
         cp="Muscat Marine Services SAOC", cpv="11008877", eas="0248:11008877",
         net="3200.000", vat="160.000", status="REJECTED", tt="10000000000000000000",
         uuid="8a7b6c5d-4e3f-2a1b-0c9d-8e7f6a5b4c3d", cat="S", ent="E1", sVat="OM1100123456",
         erp_system="SAP S/4HANA", channel="REST API",
         lines=[("Navigational Radar Calibration & SLA Support", 1, "3200.000", "S")]),
    dict(n="IIS-2026-07-0042", d="2026-07-29", t="10:14:22", direction="AR", doc_type="380",
         cp="Johnson & Co. Ltd (Oman)", cpv="OM1100654321", eas="0248:OM1100654321",
         net="4500.000", vat="225.000", status="REPORTED", tt="10000000000000000000",
         uuid="a1b2c3d4-e5f6-5789-a1b2-c3d4e5f67890", cat="S", ent="E1", sVat="OM1100123456",
         erp_system="SAP S/4HANA", channel="REST API",
         lines=[("Enterprise AI Cloud Platform Connector", 1, "3500.000", "S"),
                ("Annual Maintenance & SLA Support", 1, "1000.000", "S")]),
    dict(n="AAE-2026-07-0108", d="2026-07-29", t="14:02:10", direction="AR", doc_type="380",
         cp="Al-bhurji Contracting LLC (Oman)", cpv="OM1100778899", eas="0248:OM1100778899",
         net="12500.000", vat="625.000", status="REPORTED", tt="10000000000000000000",
         uuid="b2c3d4e5-f6a7-5890-b2c3-d4e5f6a78901", cat="S", ent="E2", sVat="OM1100223344",
         erp_system="Oracle Cloud ERP", channel="SFTP Sync",
         lines=[("Heavy Machinery Supply & Site Logistics", 5, "2500.000", "S")]),
    dict(n="ABS-2026-07-0201", d="2026-07-28", t="11:30:00", direction="AR", doc_type="380",
         is_export=True, cp="Abdulla NASS GROUP (Bahrain)", cpv="BH100200300",
         eas="0248:997770000097", net="18400.000", vat="0.000", status="REPORTED",
         tt="10010000000000000000", uuid="c3d4e5f6-a7b8-5901-c3d4-e5f6a7b89012", cat="Z",
         ent="E3", sVat="OM1100334455", erp_system="Microsoft Dynamics 365", channel="ERP Integration",
         lines=[("Cross-Border Industrial Valve Systems (GCC Export)", 10, "1840.000", "Z")]),
    dict(n="IIS-2026-07-0099", d="2026-07-28", t="16:45:11", direction="AR", doc_type="380",
         cp="Mohammed. Jasim Enterprises (Oman)", cpv="OM1100889900", eas="0248:OM1100889900",
         net="2800.000", vat="140.000", status="SENT", tt="10000000000000000000",
         uuid="d4e5f6a7-b8c9-5012-d4e5-f6a7b8c90123", cat="S", ent="E1", sVat="OM1100123456",
         erp_system="Tally Prime", channel="File Upload",
         lines=[("Database Migration & Security Audit", 1, "2800.000", "S")]),
    dict(n="AAE-2026-07-0310", d="2026-07-27", t="09:15:00", direction="AR", doc_type="380",
         is_export=True, cp="Perfect Tech IT Solutions (UAE)", cpv="AE100500600",
         eas="0248:997770000097", net="9200.000", vat="0.000", status="REPORTED",
         tt="10010000000000000000", uuid="e5f6a7b8-c9d0-5123-e5f6-a7b8c9d01234", cat="Z",
         ent="E2", sVat="OM1100223344", erp_system="Odoo ERP", channel="REST API",
         lines=[("IT Infrastructure Hardware Modules", 4, "2300.000", "Z")]),
    dict(n="ABS-2026-07-0402", d="2026-07-27", t="15:20:45", direction="AR", doc_type="380",
         is_export=True, cp="Extra Solar Planet Company, (KSA)", cpv="SA300400500",
         eas="0248:997770000097", net="34500.000", vat="0.000", status="REPORTED",
         tt="10010000000000000000", uuid="f6a7b8c9-d0e1-5234-f6a7-b8c9d0e12345", cat="Z",
         ent="E3", sVat="OM1100334455", erp_system="SAP S/4HANA", channel="SFTP Sync",
         lines=[("Solar Energy Grid Controller Units — KSA Project", 10, "3450.000", "Z")]),
    dict(n="IIS-2026-07-0155", d="2026-07-26", t="13:00:00", direction="AR", doc_type="380",
         cp="Al-Tatweer Oil Company (Oman)", cpv="OM1100987654", eas="0248:OM1100987654",
         net="15800.000", vat="790.000", status="REPORTED", tt="10000000000000000000",
         uuid="0a1b2c3d-4e5f-6789-0a1b-2c3d4e5f6789", cat="S", ent="E1", sVat="OM1100123456",
         erp_system="Oracle Cloud ERP", channel="ERP Integration",
         lines=[("Upstream Oilfield Automation Controllers", 2, "7900.000", "S")]),
    dict(n="CN-2026-07-0012", d="2026-07-25", t="11:20:00", direction="AR", doc_type="381",
         document_type="CREDIT_NOTE_381",
         cp="Johnson & Co. Ltd (Oman)", cpv="OM1100654321", eas="0248:OM1100654321",
         net="-500.000", vat="-25.000", status="REPORTED", tt="10100000000000000000",
         uuid="1b2c3d4e-5f6a-7890-1b2c-3d4e5f6a7890", cat="S", cn_ref="IIS-2026-07-0042",
         notes="Adjustment reference: IIS-2026-07-0042 — service scope reduced, partial credit issued.",
         ent="E1", sVat="OM1100123456", erp_system="SAP S/4HANA", channel="Manual Entry",
         lines=[("Service credit adjustment", 1, "-500.000", "S")]),
    dict(n="DN-2026-07-0013", d="2026-07-25", t="12:10:00", direction="AR", doc_type="383",
         document_type="DEBIT_NOTE_383",
         cp="Johnson & Co. Ltd (Oman)", cpv="OM1100654321", eas="0248:OM1100654321",
         net="250.000", vat="12.500", status="VALIDATED", tt="10000000000000000000",
         uuid="3d4e5f6a-7b8c-4901-8d2e-4f5a6b7c8901", cat="S", cn_ref="IIS-2026-07-0042",
         notes="Additional implementation effort approved against the original invoice.",
         ent="E1", sVat="OM1100123456", erp_system="Faturathi Quick Creator", channel="Manual Entry",
         lines=[("Approved implementation scope extension", 1, "250.000", "S")]),
    dict(n="PINV-2026-07-0099", d="2026-07-24", t="08:15:00", direction="AP", doc_type="380",
         cp="Alfaris Business Solutions", cpv="OM1100334455", eas="0248:OM1100334455",
         net="3400.000", vat="170.000", status="REPORTED", tt="10000000000000000000",
         uuid="2c3d4e5f-6a7b-8901-2c3d-4e5f6a7b8901", cat="S", ap="Approved · posted to ERP",
         ent="E1", sVat="OM1100334455", erp_system="Microsoft Dynamics 365", channel="REST API",
         lines=[("Enterprise Software Licenses — Q3", 1, "3400.000", "S")]),
]


class Command(BaseCommand):
    help = "Wipe and reseed Faturathi demo data (mirrors faturathi-ui/server.ts SEED_* arrays)."

    @transaction.atomic
    def handle(self, *args, **options):
        self._wipe()
        group = self._seed_company_group()
        companies = self._seed_companies(group)
        branches = self._seed_branches(companies)
        users = self._seed_users(companies)
        self._seed_system_configs(companies, users)
        customers = self._seed_customers(companies, users)
        self._seed_invoices(companies, branches, customers, users)
        self._seed_notifications(companies, users)
        self._seed_logs(companies, users)
        self.stdout.write(self.style.SUCCESS(
            f"Faturathi demo data reseeded: {len(companies)} companies, {len(users)} users, "
            f"{len(SEED_INVOICES)} invoices."
        ))

    # -- wipe ---------------------------------------------------------------

    def _wipe(self):
        Transmission.all_objects.all().delete()
        DocumentLine.all_objects.all().delete()
        Document.all_objects.all().delete()
        Notification.all_objects.all().delete()
        SystemLog.all_objects.all().delete()
        SystemConfig.all_objects.all().delete()
        Customer.all_objects.all().delete()
        CompanyBranch.all_objects.all().delete()
        User.objects.all().delete()
        Company.objects.all().delete()
        CompanyGroup.objects.all().delete()

    # -- tenants --------------------------------------------------------------

    def _seed_company_group(self):
        return CompanyGroup.objects.create(name="Faturathi Demo Group", group_vatin="OM1200001234")

    def _seed_companies(self, group):
        specs = [
            dict(short_code="E1", name_en="International Intelligence Solutions LLC",
                 cr_number="CR-1100123456", vat_number="OM1100123456",
                 prefixes=["IIS-", "INV-"], invoice_prefix="IIS-", city="Muscat", entity_type="HQ"),
            dict(short_code="E2", name_en="Aji Alibri Enterprises",
                 cr_number="CR-1100223344", vat_number="OM1100223344",
                 prefixes=["AAE-", "SOH-"], invoice_prefix="AAE-", city="Sohar", entity_type="SUBSIDIARY"),
            dict(short_code="E3", name_en="Alfaris Business Solutions",
                 cr_number="CR-1100334455", vat_number="OM1100334455",
                 prefixes=["ABS-"], invoice_prefix="ABS-", city="Salalah", entity_type="SUBSIDIARY"),
        ]
        companies = {}
        for spec in specs:
            company = Company.objects.create(
                company_group=group,
                peppol_participant_id=f"0248:{spec['vat_number']}",
                next_invoice_number=500,
                **spec,
            )
            companies[spec["short_code"]] = company
        return companies

    def _seed_branches(self, companies):
        """Operational outlets that share each legal company's VAT registration."""
        specs = {
            "E1": [
                ("MCT-01", "Muscat Main Branch", "IIS-MCT-", "/OM"),
                ("SOH-01", "Sohar Branch", "IIS-SOH-", "/OM"),
                ("SLL-01", "Salalah Branch", "IIS-SLL-", "/OM"),
            ],
            "E2": [("SOH-HQ", "Sohar Main Branch", "AAE-SOH-", "/OM")],
            "E3": [("SLL-HQ", "Salalah Main Branch", "ABS-SLL-", "/OM")],
        }
        result = {}
        for company_code, branch_specs in specs.items():
            result[company_code] = []
            for code, name, prefix, suffix in branch_specs:
                result[company_code].append(CompanyBranch.objects.create(
                    company=companies[company_code], code=code, name=name,
                    city="Muscat" if code.startswith("MCT") else "Sohar" if code.startswith("SOH") else "Salalah",
                    invoice_prefix=prefix, invoice_suffix=suffix,
                    credit_note_prefix=prefix.replace("IIS-", "CN-").replace("AAE-", "CN-").replace("ABS-", "CN-"),
                    credit_note_suffix="/CN", next_invoice_number=500,
                ))
        return result

    def _seed_users(self, companies):
        specs = [
            dict(email="superadmin@faturathi.netbue.om", role="SUPERADMIN", company=None,
                 first_name="Faturathi", last_name="Super Admin",
                 branch="All Group Entities (Muscat HQ)", designation="Platform Administrator"),
            dict(email="salim.h@intel-sol.om", role="SUPERADMIN", company=companies["E1"],
                 first_name="Salim", last_name="Al-Harthy",
                 branch="HQ Muscat", designation="Vendor Technical Staff"),
            dict(email="fatma.z@alibri.om", role="APPROVER", company=companies["E2"],
                 first_name="Fatma", last_name="Al-Zadjali",
                 branch="Muscat Main", designation="Finance Manager"),
            dict(email="ahmed.b@alfaris.om", role="MAKER", company=companies["E3"],
                 first_name="Ahmed", last_name="Al-Balushi",
                 branch="Salalah Ops", designation="Invoice Clerk"),
            dict(email="auditor@kpmg.om", role="VIEWER", company=None,
                 first_name="KPMG", last_name="Auditor",
                 branch="—", designation="External Auditor"),
        ]
        users = {}
        for spec in specs:
            email = spec.pop("email")
            users[email] = User.objects.create_user(
                email=email, password=SEED_PASSWORD, mfa_enabled=True, **spec)
        return users

    def _seed_system_configs(self, companies, users):
        admin_user = users["superadmin@faturathi.netbue.om"]
        for company in companies.values():
            SystemConfig.objects.create(company=company, created_by=admin_user)

    def _seed_customers(self, companies, users):
        admin_user = users["superadmin@faturathi.netbue.om"]
        specs = [
            ("E1", "Muscat Marine Services SAOC", "11008877"),
            ("E1", "Johnson & Co. Ltd (Oman)", "OM1100654321"),
            ("E1", "Mohammed. Jasim Enterprises (Oman)", "OM1100889900"),
            ("E1", "Al-Tatweer Oil Company (Oman)", "OM1100987654"),
            ("E2", "Al-bhurji Contracting LLC (Oman)", "OM1100778899"),
            ("E2", "Perfect Tech IT Solutions (UAE)", "AE100500600"),
            ("E3", "Abdulla NASS GROUP (Bahrain)", "BH100200300"),
            ("E3", "Extra Solar Planet Company, (KSA)", "SA300400500"),
        ]
        customers = {}
        for short_code, name, vatin in specs:
            company = companies[short_code]
            customers[(short_code, name)] = Customer.objects.create(
                company=company, name=name, vatin=vatin, peppol_endpoint=f"0248:{vatin}",
                created_by=admin_user,
            )
        for company in companies.values():
            Customer.objects.create(
                company=company, name="Custom Walk-in Customer", is_walkin=True,
                peppol_endpoint="0248:997770000099", created_by=admin_user,
            )
        return customers

    # -- invoices -------------------------------------------------------------

    def _seed_invoices(self, companies, branches, customers, users):
        admin_user = users["superadmin@faturathi.netbue.om"]
        created_by_number = {}

        branch_counters = {code: 0 for code in branches}
        for spec in SEED_INVOICES:
            company = companies[spec["ent"]]
            company_branches = branches.get(spec["ent"], [])
            branch = company_branches[branch_counters[spec["ent"]] % len(company_branches)] if company_branches else None
            branch_counters[spec["ent"]] += 1
            issue_date = datetime.strptime(spec["d"], "%Y-%m-%d").date()
            issue_time = datetime.strptime(spec["t"], "%H:%M:%S").time()
            customer = customers.get((spec["ent"], spec["cp"]))

            document = Document.objects.create(
                company=company, branch=branch, created_by=admin_user,
                direction=spec["direction"], document_type=spec.get("document_type", "STANDARD_380"),
                is_export=spec.get("is_export", False),
                invoice_number=spec["n"], issue_date=issue_date, issue_time=issue_time,
                transaction_type_code=spec["tt"], customer=customer,
                counterparty_name=spec["cp"], counterparty_vatin=spec["cpv"], counterparty_endpoint=spec["eas"],
                currency="OMR", payment_means_code="30", payment_iban="OM810180000000000000123",
                status=spec["status"], source=SOURCE_BY_CHANNEL.get(spec["channel"], "MANUAL"),
                erp_system=spec["erp_system"], ap_status=spec.get("ap", ""), notes=spec.get("notes", ""),
            )
            for idx, (name, qty, price, cat) in enumerate(spec["lines"], start=1):
                DocumentLine.objects.create(
                    company=company, created_by=admin_user, document=document, line_id=idx,
                    item_name=name, quantity=Decimal(str(qty)), unit_code="EA",
                    unit_price=Decimal(price), vat_category=cat, vat_rate=CAT_RATE[cat],
                )
            recompute_totals(document)
            document.uuid_v5 = spec["uuid"]
            document.save(update_fields=["uuid_v5"])
            refresh_pint_snapshot(document)
            created_by_number[spec["n"]] = document

            self._seed_transmission(document, spec, admin_user)

        # Wire the credit note's billing_reference now that both invoices exist.
        for spec in SEED_INVOICES:
            if spec.get("cn_ref"):
                document = created_by_number[spec["n"]]
                document.billing_reference = created_by_number[spec["cn_ref"]]
                document.save(update_fields=["billing_reference"])
                refresh_pint_snapshot(document)
                document.transmissions.update(payload=build_pint_payload(document))

    def _seed_transmission(self, document, spec, admin_user):
        now = timezone.now()
        payload = build_pint_payload(document)
        if spec["status"] == "REJECTED":
            Transmission.objects.create(
                company=document.company, created_by=admin_user, document=document, attempt=1,
                status="REJECTED", payload=payload,
                validation_errors=[{
                    "rule": "VATIN-FORMAT", "field": "counterparty_vatin", "code": "C5",
                    "message": (
                        f"Schematron Error BR-O-02: Buyer VATIN '{document.counterparty_vatin}' violates "
                        "Oman PINT-OM syntax rules. Must start with 'OM' followed by 8–12 digits "
                        "(e.g. OM1100887700)."
                    ),
                }],
                ota_response_code="C5", ota_message="Invalid Buyer VATIN",
            )
            return

        final_status = {
            "DRAFT": "QUEUED", "VALIDATED": "VALIDATED", "PENDING": "QUEUED",
            "SUBMITTED": "VALIDATING", "SENT": "AS4_SENT", "REPORTED": "MLS_RECEIVED",
        }.get(spec["status"], "QUEUED")
        sent = final_status in {"AS4_SENT", "ACK_RECEIVED", "TDD_REPORTED", "MLS_RECEIVED"}
        acknowledged = final_status in {"ACK_RECEIVED", "TDD_REPORTED", "MLS_RECEIVED"}
        Transmission.objects.create(
            company=document.company, created_by=admin_user, document=document, attempt=1,
            status=final_status, payload=payload,
            sent_at=now if sent else None, acked_at=now if acknowledged else None,
            reported_at=now if final_status == "MLS_RECEIVED" else None,
            ota_response_code="OK" if final_status not in {"QUEUED", "VALIDATING"} else "",
            mls_status="AB" if final_status == "MLS_RECEIVED" else "",
        )

    # -- notifications ----------------------------------------------------

    def _seed_notifications(self, companies, users):
        admin_user = users["superadmin@faturathi.netbue.om"]
        Notification.objects.create(
            company=companies["E1"], created_by=admin_user, user=users["salim.h@intel-sol.om"],
            title="Invoice Rejected", level="ERROR",
            message="IIS-2026-08-0099 was rejected by OTA: Invalid Buyer VATIN (C5).",
        )
        Notification.objects.create(
            company=companies["E3"], created_by=admin_user, user=users["ahmed.b@alfaris.om"],
            title="AP Invoice Approved", level="INFO",
            message="PINV-2026-07-0099 was approved and posted to ERP.",
        )

    def _seed_logs(self, companies, users):
        populate_demo_logs(companies=companies.values(), clear_demo=True)
