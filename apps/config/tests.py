from datetime import date

from rest_framework.test import APIClient, APITestCase

from apps.company.models import Company, CompanyBranch, CompanyGroup
from apps.config.models import ErpDeliveryConfig, SupportTicket
from apps.user.models import User


class ApiCredentialTests(APITestCase):
    def setUp(self):
        group = CompanyGroup.objects.create(name="API Group", group_vatin="OM1200000099")
        self.company = Company.objects.create(
            company_group=group, short_code="API1", name_en="API Company", cr_number="CR-API",
            vat_number="OM1100000099", peppol_participant_id="0248:OM1100000099")
        self.admin = User.objects.create_user("api-admin@example.com", "secret", company=self.company, role="ADMIN")

    def test_generated_api_key_authenticates_inbound_document(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        created = client.post("/api/connectors/credentials", {"name": "Postman"}, format="json")
        self.assertEqual(created.status_code, 201)
        self.assertTrue(created.data["apiKey"].startswith("fat_live_"))
        self.assertEqual(created.data["bearerToken"].count("."), 2)

        machine = APIClient()
        response = machine.post("/api/invoices/inbound", {
            "n": "POSTMAN-INBOUND-1", "d": date.today().isoformat(), "t": "10:00:00",
            "cp": "Supplier", "cpv": "OM1100000088", "eas": "0248:OM1100000088",
            "lines": [["Item", 1, "10.000", "S 5%"]],
        }, format="json", HTTP_X_API_KEY=created.data["apiKey"])
        self.assertNotEqual(response.status_code, 401)
        self.assertEqual(response.status_code, 201)


class ErpDeliveryConfigTests(APITestCase):
    def setUp(self):
        group = CompanyGroup.objects.create(name="ERP Group", group_vatin="OM1200000088")
        self.company = Company.objects.create(
            company_group=group, short_code="ERP1", name_en="ERP Company", cr_number="CR-ERP",
            vat_number="OM1100000088", peppol_participant_id="0248:OM1100000088",
        )
        self.branch = CompanyBranch.objects.create(
            company=self.company, code="MCT-01", name="Muscat Branch",
        )
        self.technical_admin = User.objects.create_user(
            "technical@example.com", "secret", company=self.company, role="ADMIN",
            designation="Vendor Technical Staff",
        )
        self.portal_admin = User.objects.create_user(
            "portal@example.com", "secret", company=self.company, role="ADMIN",
            designation="Portal Administrator",
        )

    def test_technical_admin_can_create_central_and_branch_targets_without_secret_leak(self):
        self.client.force_authenticate(self.technical_admin)
        central = self.client.post("/api/erp-delivery-configs", {
            "company": str(self.company.id),
            "name": "SAP Central AP",
            "base_url": "https://erp.example.com",
            "endpoint_path": "/api/ap/invoices",
            "auth_type": "BEARER",
            "auth_token": "live-secret-token",
            "custom_headers": {"X-Tenant": "ERP1"},
            "payload_template": {"invoice_number": "{{invoice_number}}"},
        }, format="json")
        self.assertEqual(central.status_code, 201, central.json())
        self.assertTrue(central.json()["token_configured"])
        self.assertNotIn("auth_token", central.json())

        branch = self.client.post("/api/erp-delivery-configs", {
            "company": str(self.company.id),
            "branch": str(self.branch.id),
            "name": "Muscat Odoo AP",
            "base_url": "https://mct-erp.example.com",
            "auth_type": "API_KEY",
            "auth_header_name": "X-API-KEY",
            "auth_token": "branch-secret",
        }, format="json")
        self.assertEqual(branch.status_code, 201, branch.json())
        self.assertEqual(ErpDeliveryConfig.objects.filter(company=self.company).count(), 2)

        listing = self.client.get("/api/erp-delivery-configs")
        self.assertEqual(listing.status_code, 200)
        rows = listing.json().get("results", listing.json())
        self.assertEqual(len(rows), 2)
        self.assertTrue(all("auth_token" not in row for row in rows))

    def test_non_technical_portal_admin_is_forbidden(self):
        self.client.force_authenticate(self.portal_admin)
        response = self.client.get("/api/erp-delivery-configs")
        self.assertEqual(response.status_code, 403)


class SupportAndDocumentationTests(APITestCase):
    def setUp(self):
        group = CompanyGroup.objects.create(name="Support Group", group_vatin="OM1200000077")
        self.company = Company.objects.create(
            company_group=group, short_code="SUP1", name_en="Support Company",
            cr_number="CR-SUPPORT", vat_number="OM1100000077",
            peppol_participant_id="0248:OM1100000077",
        )
        self.admin = User.objects.create_user(
            "support-admin@example.com", "secret", company=self.company, role="ADMIN"
        )
        self.client.force_authenticate(self.admin)

    def test_created_support_ticket_is_immediately_listed_newest_first(self):
        older = SupportTicket.objects.create(
            company=self.company, created_by=self.admin, subject="Older issue",
            contact_email=self.admin.email, message="Previously raised issue",
        )
        created = self.client.post("/api/support/tickets", {
            "subject": "New visible issue", "category": "TECHNICAL",
            "contact_email": self.admin.email, "message": "Show this immediately",
        }, format="json")
        self.assertEqual(created.status_code, 201, created.json())
        listing = self.client.get("/api/support/tickets?page_size=100")
        self.assertEqual(listing.status_code, 200)
        rows = listing.json().get("results", listing.json())
        self.assertEqual(rows[0]["id"], created.json()["id"])
        self.assertNotEqual(rows[0]["id"], str(older.id))

    def test_document_api_catalogue_contains_all_six_profiles(self):
        response = self.client.get("/api/document-api-examples")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["count"], 6)
        self.assertEqual(
            {row["code"] for row in response.json()["examples"]},
            {"261", "380", "381", "383", "389"},
        )
        self.assertTrue(all(
            "header" in row["payload"]
            and "seller_details" in row["payload"]
            and "lines" in row["payload"]
            for row in response.json()["examples"]
        ))
