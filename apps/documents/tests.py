from datetime import date, time

from django.test import TestCase
from rest_framework.test import APIClient

from apps.company.models import Company, CompanyBranch
from apps.config.models import ErpDeliveryConfig
from apps.user.models import User
from apps.utils.constants import DOCUMENT_TYPE_CATALOG

from .models import Document, DocumentLine
from .pint_om import refresh_pint_snapshot
from .pint_examples import get_pint_om_examples
from .pint_pipeline import validate_pint_om_payload
from .services import recompute_totals
from .views import _group_flat_rows
from .compat import build_document_payload


class DocumentArchitectureTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            short_code="T1", name_en="Test Supplier LLC", cr_number="CR-T1",
            vat_number="OM1100123456", peppol_participant_id="0248:OM1100123456",
            address="Al Khuwair", city="Muscat", postal_code="112",
        )
        self.user = User.objects.create_user(
            "maker@example.com", "Demo@1234", company=self.company, role="ADMIN"
        )

    def test_all_six_document_profiles_derive_code_and_b2c(self):
        self.assertEqual(len(DOCUMENT_TYPE_CATALOG), 6)
        for index, profile in enumerate(DOCUMENT_TYPE_CATALOG, start=1):
            document = Document.objects.create(
                company=self.company, created_by=self.user, direction=profile["direction_hint"],
                document_type=profile["key"], invoice_number=f"TEST-{index}",
                issue_date=date.today(), issue_time=time(10), counterparty_name="Buyer LLC",
                counterparty_vatin="OM1100654321", counterparty_endpoint="0248:OM1100654321",
            )
            self.assertEqual(document.doc_type, profile["code"])
            self.assertEqual(document.is_b2c, profile["is_b2c"])

    def test_canonical_snapshot_contains_all_reference_sections_and_metadata(self):
        document = Document.objects.create(
            company=self.company, created_by=self.user, direction="AR", document_type="STANDARD_380",
            invoice_number="TEST-PINT-73", issue_date=date.today(), issue_time=time(10),
            counterparty_name="Buyer LLC", counterparty_vatin="OM1100654321",
            counterparty_endpoint="0248:OM1100654321", source="REST_API", erp_system="SAP S/4HANA",
        )
        DocumentLine.objects.create(
            company=self.company, created_by=self.user, document=document, line_id=1,
            item_name="Consulting", quantity=1, unit_price=100, vat_category="S", vat_rate=5,
        )
        recompute_totals(document)
        refresh_pint_snapshot(document)
        document.refresh_from_db()
        payload = document.extra_data["pint_om"]
        self.assertEqual(payload["IBT_001_InvoiceNumber"], "TEST-PINT-73")
        self.assertEqual(payload["SellerDetails"]["IBT_027_SellerName"], "Test Supplier LLC")
        self.assertEqual(payload["Lines"][0]["IBT_153_ItemName"], "Consulting")
        self.assertEqual(payload["ProcessingMetadata"]["source"], "REST_API")
        self.assertEqual(payload["ProcessingMetadata"]["created_by"], "maker@example.com")

    def test_flat_file_rows_are_grouped_into_one_document_with_multiple_lines(self):
        rows = [
            {"IBT_001_InvoiceNumber": "FILE-1", "IBT_153_ItemName": "Line A", "IBT_146_ItemNetPrice": "10"},
            {"IBT_001_InvoiceNumber": "FILE-1", "IBT_153_ItemName": "Line B", "IBT_146_ItemNetPrice": "20"},
        ]
        grouped = _group_flat_rows(rows)
        self.assertEqual(len(grouped), 1)
        self.assertEqual(len(grouped[0]["lines"]), 2)
        self.assertEqual(len(grouped[0]["extra_data"]["ingested_rows"]), 2)

    def test_manual_invoice_number_with_slash_is_preserved(self):
        payload = build_document_payload({
            "n": "NB-OM560/F", "cp": "Buyer LLC", "cpv": "OM1100654321",
            "eas": "0248:OM1100654321", "lines": [["Service", 1, "25.000 OMR", "S 5%"]],
        })
        self.assertEqual(payload["invoice_number"], "NB-OM560/F")
        self.assertEqual(payload["lines"][0]["unit_price"], "25.000")

    def test_ap_api_payload_uses_seller_and_normalizes_line_aliases(self):
        payload = build_document_payload({
            "IBT_001_InvoiceNumber": "AP-API-1",
            "SellerDetails": {"IBT_027_SellerName": "API Supplier LLC", "IBT_031_SellerVATIdentifier": "OM1100654321"},
            "lines": [{"item_name": "Hosting", "quantity": 2, "amount": "200.000", "vatCategory": "S"}],
        }, direction="AP")
        self.assertEqual(payload["counterparty_name"], "API Supplier LLC")
        self.assertEqual(payload["counterparty_vatin"], "OM1100654321")
        self.assertEqual(payload["lines"][0]["unit_price"], "100.000")

    def test_self_billed_snapshot_uses_counterparty_as_supplier(self):
        document = Document.objects.create(
            company=self.company, created_by=self.user, direction="AP", document_type="SELF_BILLED_389",
            invoice_number="SB-1", issue_date=date.today(), issue_time=time(10),
            counterparty_name="Actual Supplier LLC", counterparty_vatin="OM1100654321",
            counterparty_endpoint="0248:OM1100654321",
        )
        refresh_pint_snapshot(document)
        document.refresh_from_db()
        payload = document.extra_data["pint_om"]
        self.assertEqual(payload["SellerDetails"]["IBT_027_SellerName"], "Actual Supplier LLC")
        self.assertEqual(payload["BuyerDetails"]["IBT_044_BuyerName"], "Test Supplier LLC")

    def test_simplified_b2c_payload_allows_blank_vat_and_endpoint(self):
        payload = build_document_payload({
            "n": "B2C-1", "document_type": "SIMPLIFIED_B2C", "b2c": True,
            "cp": "Cash Customer", "cpv": "", "eas": "",
            "lines": [["Retail sale", 1, "10.000 OMR", "S 5%"]],
        })
        self.assertEqual(payload["counterparty_vatin"], "")
        self.assertEqual(payload["counterparty_endpoint"], "")

    def test_duplicate_document_number_returns_field_error_instead_of_500(self):
        Document.objects.create(
            company=self.company, created_by=self.user, direction="AR",
            invoice_number="INV-2026-Q-9941/OM", issue_date=date.today(), issue_time=time(10),
            counterparty_name="Existing Buyer",
        )
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.post("/api/v1/invoices", {
            "n": "INV-2026-Q-9941/OM", "d": "2026-08-11", "t": "10:00:00",
            "document_type": "STANDARD_380", "cp": "Custom Walk-in Retail Customer",
            "cpv": "OM1100998877", "eas": "0248:997770000099",
            "ent": str(self.company.id),
            "lines": [["IT Infrastructure Maintenance & SLA", 1, "450.000 OMR", "S 5%"]],
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("already exists", str(response.json()["error"]["fields"]["invoice_number"][0]))

    def test_ap_approval_returns_updated_document_and_is_idempotent(self):
        document = Document.objects.create(
            company=self.company, created_by=self.user, direction="AP",
            document_type="SELF_BILLED_389", invoice_number="AP-APPROVE-1",
            issue_date=date.today(), issue_time=time(10), counterparty_name="Supplier LLC",
            ap_status="Pending Approver Review",
        )
        client = APIClient()
        client.force_authenticate(self.user)
        url = f"/api/invoices/{document.id}/approve"
        first = client.post(url, {}, format="json")
        second = client.post(url, {}, format="json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["apStatus"], "ERP posting requested")
        self.assertEqual(second.status_code, 200)

    def test_skip_erp_records_decision_without_rejecting_document(self):
        document = Document.objects.create(
            company=self.company, created_by=self.user, direction="AP",
            document_type="SELF_BILLED_389", invoice_number="AP-SKIP-1",
            issue_date=date.today(), issue_time=time(10), counterparty_name="Supplier LLC",
            status="REPORTED", ap_status="Pending Approver Review",
        )
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.post(f"/api/invoices/{document.id}/skip_erp", {"reason": "Duplicate in ERP"}, format="json")
        self.assertEqual(response.status_code, 200, response.json())
        document.refresh_from_db()
        self.assertEqual(document.status, "REPORTED")
        self.assertEqual(document.ap_status, "Not Posted to ERP")
        self.assertEqual(document.extra_data["erp_posting_decision"]["reason"], "Duplicate in ERP")

    def test_ap_approval_prefers_branch_erp_target_over_company_central_target(self):
        branch = CompanyBranch.objects.create(company=self.company, code="MCT-01", name="Muscat")
        ErpDeliveryConfig.objects.create(
            company=self.company, name="Central SAP", base_url="https://central.example.com",
        )
        branch_target = ErpDeliveryConfig.objects.create(
            company=self.company, branch=branch, name="Branch Odoo",
            base_url="https://branch.example.com",
        )
        document = Document.objects.create(
            company=self.company, branch=branch, created_by=self.user, direction="AP",
            document_type="SELF_BILLED_389", invoice_number="AP-BRANCH-ERP-1",
            issue_date=date.today(), issue_time=time(10), counterparty_name="Supplier LLC",
            ap_status="Pending Approver Review",
        )
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.post(f"/api/invoices/{document.id}/approve", {}, format="json")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["erpDelivery"]["configuration_id"], str(branch_target.id))
        document.refresh_from_db()
        self.assertEqual(document.erp_system, "Branch Odoo")

    def test_ar_document_cannot_be_approved_as_ap(self):
        document = Document.objects.create(
            company=self.company, created_by=self.user, direction="AR",
            invoice_number="AR-NOT-AP", issue_date=date.today(), issue_time=time(10),
            counterparty_name="Buyer LLC",
        )
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.post(f"/api/invoices/{document.id}/approve", {}, format="json")
        self.assertEqual(response.status_code, 400)


class PintOmRestContractTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            short_code="P1", name_en="PINT Supplier LLC", cr_number="CR-PINT-1",
            vat_number="OM1100123456", peppol_participant_id="0248:OM1100123456",
            address="Way 2317, Building 192", city="Muscat", postal_code="112",
        )
        self.user = User.objects.create_user(
            "pint-maker@example.com", "Demo@1234", company=self.company, role="ADMIN"
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_all_six_lower_snake_case_examples_pass_official_pipeline(self):
        for name, payload in get_pint_om_examples().items():
            with self.subTest(profile=name):
                result = validate_pint_om_payload(payload)
                self.assertTrue(result["valid"], result["errors"])

    def test_dry_run_never_persists(self):
        before = Document.objects.count()
        payload = get_pint_om_examples()["b2b_standard_tax_invoice_380"]
        response = self.client.post("/api/v1/invoices/validate/", payload, format="json")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertTrue(response.json()["valid"])
        self.assertEqual(Document.objects.count(), before)

    def test_invalid_payload_returns_normalized_field_path_without_persisting(self):
        payload = get_pint_om_examples()["b2b_standard_tax_invoice_380"]
        payload["header"]["btom_002_invoice_uuid"] = "8d93b550-6c90-4e63-a792-39e28c421234"
        before = Document.objects.count()
        response = self.client.post("/api/v1/invoices/validate/", payload, format="json")
        self.assertEqual(response.status_code, 422, response.json())
        body = response.json()
        self.assertFalse(body["valid"])
        self.assertTrue(any(
            item["code"] == "IBR-002-OM"
            and item["field"] == "header.btom_002_invoice_uuid"
            for item in body["errors"]
        ))
        self.assertEqual(Document.objects.count(), before)

    def test_create_runs_same_pipeline_then_persists_once(self):
        payload = get_pint_om_examples()["self_billed_invoice_389"]
        response = self.client.post("/api/v1/invoices/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.json())
        self.assertTrue(response.json()["valid"])
        document = Document.objects.get(invoice_number="SBINV-2026-0005")
        self.assertEqual(document.direction, "AP")
        self.assertEqual(document.status, "VALIDATED")
        self.assertEqual(document.uuid_v5.version, 5)
        self.assertIn("ubl_xml", document.extra_data)

    def test_pascal_case_properties_are_rejected(self):
        response = self.client.post("/api/v1/invoices/validate/", {
            "SellerDetails": {}, "InvoiceNumber": "OLD-CONTRACT",
        }, format="json")
        self.assertEqual(response.status_code, 422)
        fields = {item["field"] for item in response.json()["errors"]}
        self.assertIn("SellerDetails", fields)
        self.assertIn("InvoiceNumber", fields)
