from datetime import date

from rest_framework.test import APIClient, APITestCase

from apps.company.models import Company, CompanyBranch, CompanyGroup
from apps.config.models import ErpDeliveryConfig
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
