from datetime import date, time

from rest_framework.test import APIClient, APITestCase

from apps.company.models import Company, CompanyGroup
from apps.documents.models import Document
from apps.user.models import User


class TenantIsolationTests(APITestCase):
    def setUp(self):
        group_a = CompanyGroup.objects.create(name="Group A", group_vatin="OM1200000001")
        group_b = CompanyGroup.objects.create(name="Group B", group_vatin="OM1200000002")
        self.company_a = Company.objects.create(
            company_group=group_a, short_code="A1", name_en="A LLC", cr_number="CR-A",
            vat_number="OM1100000001", peppol_participant_id="0248:OM1100000001")
        self.company_b = Company.objects.create(
            company_group=group_b, short_code="B1", name_en="B LLC", cr_number="CR-B",
            vat_number="OM1100000002", peppol_participant_id="0248:OM1100000002")
        self.user_a = User.objects.create_user("admin-a@example.com", None, company=self.company_a, role="ADMIN")
        self.viewer = User.objects.create_user("viewer@example.com", None, company=None, role="VIEWER")
        for company, number in ((self.company_a, "A-INV"), (self.company_b, "B-INV")):
            Document.objects.create(
                company=company, direction="AR", invoice_number=number,
                issue_date=date.today(), issue_time=time(10), counterparty_name="Buyer")
        self.client = APIClient()

    def test_header_cannot_escape_callers_business_group(self):
        self.client.force_authenticate(self.user_a)
        response = self.client.get("/api/invoices", HTTP_X_COMPANY_ID="B1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["n"] for row in response.json()], ["A-INV"])

    def test_companyless_viewer_has_no_implicit_platform_scope(self):
        self.client.force_authenticate(self.viewer)
        response = self.client.get("/api/invoices")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_viewer_cannot_create_documents(self):
        tenant_viewer = User.objects.create_user(
            "tenant-viewer@example.com", None, company=self.company_a, role="VIEWER")
        self.client.force_authenticate(tenant_viewer)
        response = self.client.post("/api/invoices", {}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_company_group_endpoint_returns_only_callers_group(self):
        self.client.force_authenticate(self.user_a)
        response = self.client.get("/api/company-groups")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        rows = payload.get("results", payload) if isinstance(payload, dict) else payload
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Group A")
