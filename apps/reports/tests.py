from datetime import date, time

from django.test import TestCase
from rest_framework.test import APIClient

from apps.company.models import Company, CompanyBranch
from apps.documents.models import Document
from apps.user.models import User


class BranchReportingTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            short_code="RPT", name_en="Coffee Report LLC", cr_number="CR-RPT",
            vat_number="OM1100000077", peppol_participant_id="0248:OM1100000077",
        )
        self.branch = CompanyBranch.objects.create(
            company=self.company, code="MCT-01", name="Muscat Branch",
            invoice_prefix="MCT-", invoice_suffix="/OM",
        )
        self.user = User.objects.create_user(
            "report-admin@example.com", "Demo@1234", company=self.company, role="ADMIN"
        )
        Document.objects.create(
            company=self.company, branch=self.branch, created_by=self.user, direction="AR",
            invoice_number="MCT-0001/OM", issue_date=date.today(), issue_time=time(10),
            counterparty_name="Cash Customer", tax_exclusive_amount=10,
            tax_amount=0.5, tax_inclusive_amount=10.5,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_tax_grid_and_branch_summary_expose_operational_branch(self):
        grid = self.client.get(f"/api/reports/tax-grid?branch={self.branch.id}")
        self.assertEqual(grid.status_code, 200)
        self.assertEqual(grid.json()[0]["branch_code"], "MCT-01")
        summary = self.client.get("/api/reports/branch-summary")
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()[0]["document_count"], 1)
        self.assertEqual(summary.json()[0]["total"], 10.5)

# Create your tests here.
