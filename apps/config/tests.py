from datetime import date

from rest_framework.test import APIClient, APITestCase

from apps.company.models import Company, CompanyGroup
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
