from datetime import date, time

from django.test import TestCase

from apps.company.models import Company
from apps.user.models import User
from apps.utils.constants import DOCUMENT_TYPE_CATALOG

from .models import Document, DocumentLine
from .pint_om import refresh_pint_snapshot
from .services import recompute_totals
from .views import _group_flat_rows


class DocumentArchitectureTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            short_code="T1", name_en="Test Supplier LLC", cr_number="CR-T1",
            vat_number="OM1100123456", peppol_participant_id="0248:OM1100123456",
            address="Al Khuwair", city="Muscat", postal_code="112",
        )
        self.user = User.objects.create_user("maker@example.com", "Demo@1234", company=self.company)

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
