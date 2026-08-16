from datetime import date, time

from django.test import TestCase
from rest_framework.test import APIClient

from apps.documents.models import Document
from apps.user.models import User

from .models import Company, CompanyBranch


class CompanyBranchApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            short_code="COF", name_en="One VAT Coffee LLC", cr_number="CR-COF",
            vat_number="OM1100000099", peppol_participant_id="0248:OM1100000099",
        )
        self.user = User.objects.create_user(
            "coffee-admin@example.com", "Demo@1234", company=self.company, role="ADMIN"
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_multiple_operational_branches_share_one_company_vatin(self):
        for code, name in (("MCT-01", "Muscat Coffee"), ("SOH-01", "Sohar Coffee")):
            response = self.client.post("/api/branches", {
                "company": str(self.company.id), "code": code, "name": name,
                "invoice_prefix": f"{code}-", "invoice_suffix": "/OM",
            }, format="json")
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json()["company_vatin"], self.company.vat_number)
        self.assertEqual(CompanyBranch.objects.filter(company=self.company).count(), 2)

    def test_duplicate_branch_code_is_rejected_and_used_branch_is_protected(self):
        branch = CompanyBranch.objects.create(company=self.company, code="MCT-01", name="Muscat")
        duplicate = self.client.post("/api/branches", {
            "company": str(self.company.id), "code": "mct-01", "name": "Duplicate",
        }, format="json")
        self.assertEqual(duplicate.status_code, 400)
        Document.objects.create(
            company=self.company, branch=branch, created_by=self.user, direction="AR",
            invoice_number="MCT-01-0001", issue_date=date.today(), issue_time=time(10),
        )
        protected = self.client.delete(f"/api/branches/{branch.id}")
        self.assertEqual(protected.status_code, 400)

# Create your tests here.
