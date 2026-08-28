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

    def test_password_then_demo_otp_returns_reloadable_session(self):
        company = Company.objects.create(
            short_code="AUTH", name_en="Auth Company", cr_number="CR-AUTH",
            vat_number="OM1100000088", peppol_participant_id="0248:OM1100000088")
        user = User.objects.create_user(
            "password-user@example.com", "Demo@1234", company=company,
            role="ADMIN", mfa_enabled=True)
        login = self.client.post("/api/auth/login", {
            "email": user.email, "password": "Demo@1234"}, format="json")
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.data["mfa_required"])

        verified = self.client.post("/api/auth/mfa-verify", {
            "email": user.email, "otp": "582910",
            "mfa_challenge": login.data["mfa_challenge"]}, format="json")
        self.assertEqual(verified.status_code, 200)
        self.assertIn("token", verified.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {verified.data['token']}")
        me = self.client.get("/api/auth/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data["email"], user.email)

    def test_password_and_otp_are_required_even_when_user_mfa_flag_is_disabled(self):
        company = Company.objects.create(
            short_code="AU2", name_en="Always MFA Company", cr_number="CR-AUTH2",
            vat_number="OM1100000099", peppol_participant_id="0248:OM1100000099")
        user = User.objects.create_user(
            "always-mfa@example.com", "Demo@1234", company=company,
            role="MAKER", mfa_enabled=False)

        login = self.client.post("/api/auth/login", {
            "email": user.email, "password": "Demo@1234"}, format="json")

        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.data["mfa_required"])
        self.assertNotIn("token", login.data)
        self.assertTrue(login.data["mfa_challenge"])

        bypass = self.client.post("/api/auth/mfa-verify", {
            "email": user.email, "otp": "582910"}, format="json")
        self.assertEqual(bypass.status_code, 401)
        self.assertNotIn("token", bypass.data)

    def test_email_only_otp_login_endpoint_is_not_available(self):
        response = self.client.post("/api/auth/email-otp", {
            "email": "anyone@example.com"}, format="json")
        self.assertEqual(response.status_code, 404)

# Create your tests here.
