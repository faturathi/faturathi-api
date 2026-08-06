from rest_framework.test import APIClient, APITestCase

from apps.company.models import Company
from .models import User


class UserProvisioningTests(APITestCase):
    def test_generated_temporary_password_is_returned_and_works(self):
        company = Company.objects.create(
            short_code="USR", name_en="User Company", cr_number="CR-USR",
            vat_number="OM1100000077", peppol_participant_id="0248:OM1100000077")
        admin = User.objects.create_user("admin-users@example.com", "secret", company=company, role="ADMIN")
        client = APIClient()
        client.force_authenticate(admin)
        response = client.post("/api/users", {
            "email": "new-user@example.com", "first_name": "New User", "role": "APPROVER",
            "company": str(company.id), "branch": "All Entities", "mfa": True,
        }, format="json")
        self.assertEqual(response.status_code, 201)
        temporary_password = response.data["temporaryPassword"]
        self.assertTrue(temporary_password)
        self.assertTrue(User.objects.get(email="new-user@example.com").check_password(temporary_password))

# Create your tests here.
