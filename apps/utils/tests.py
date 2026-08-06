from datetime import date, time

from rest_framework.test import APIClient, APITestCase

from apps.company.models import Company, CompanyGroup
from apps.config.models import SystemConfig
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

    def test_platform_admin_business_group_header_limits_whole_group_scope(self):
        platform_admin = User.objects.create_superuser("platform@example.com", "secret")
        self.client.force_authenticate(platform_admin)
        group_id = str(self.company_a.company_group_id)
        response = self.client.get(
            "/api/invoices", HTTP_X_COMPANY_ID="group", HTTP_X_BUSINESS_GROUP_ID=group_id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["n"] for row in response.json()], ["A-INV"])

    def test_platform_admin_can_create_group_and_standalone_company(self):
        platform_admin = User.objects.create_superuser("platform2@example.com", "secret")
        self.client.force_authenticate(platform_admin)
        group = self.client.post("/api/company-groups", {
            "name": "New VAT Group", "group_vatin": "OM1200000098"}, format="json")
        self.assertEqual(group.status_code, 201)
        standalone = self.client.post("/api/entities", {
            "name": "Standalone LLC", "crNum": "CR-STAND", "vatin": "OM1100000098",
            "pid": "0248:OM1100000098", "short_code": "ST1", "prefixes": [],
            "standalone": True,
        }, format="json")
        self.assertEqual(standalone.status_code, 201)
        self.assertIsNone(Company.objects.get(cr_number="CR-STAND").company_group_id)

    def test_duplicate_company_group_name_or_vatin_is_rejected(self):
        platform_admin = User.objects.create_superuser("platform3@example.com", "secret")
        self.client.force_authenticate(platform_admin)
        by_name = self.client.post("/api/company-groups", {
            "name": "group a", "group_vatin": "OM1200000097"}, format="json")
        self.assertEqual(by_name.status_code, 400)
        by_vatin = self.client.post("/api/company-groups", {
            "name": "Another Group", "group_vatin": "OM1200000001"}, format="json")
        self.assertEqual(by_vatin.status_code, 400)

    def test_platform_admin_assigns_selected_group_to_subsidiary(self):
        platform_admin = User.objects.create_superuser("platform4@example.com", "secret")
        target_group = CompanyGroup.objects.create(name="Target Group", group_vatin="OM1200000096")
        self.client.force_authenticate(platform_admin)
        response = self.client.post("/api/entities", {
            "name": "Selected Subsidiary LLC", "crNum": "CR-SUB", "vatin": "OM1100000096",
            "pid": "0248:OM1100000096", "short_code": "S1", "prefixes": [],
            "entity_type": "SUBSIDIARY", "company_group": str(target_group.id),
            "standalone": False,
        }, format="json")
        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(Company.objects.get(cr_number="CR-SUB").company_group_id, target_group.id)

    def test_group_with_companies_cannot_be_deleted(self):
        platform_admin = User.objects.create_superuser("platform5@example.com", "secret")
        self.client.force_authenticate(platform_admin)
        group = self.company_a.company_group
        response = self.client.delete(f"/api/company-groups/{group.id}")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["company_count"], 1)
        self.assertTrue(CompanyGroup.objects.filter(pk=group.id).exists())

    def test_empty_group_can_be_edited_and_deleted_by_platform_admin(self):
        platform_admin = User.objects.create_superuser("platform6@example.com", "secret")
        empty_group = CompanyGroup.objects.create(name="Empty Group", group_vatin="OM1200000095")
        self.client.force_authenticate(platform_admin)
        update = self.client.patch(f"/api/company-groups/{empty_group.id}", {
            "name": "Renamed Empty Group"}, format="json")
        self.assertEqual(update.status_code, 200, update.json())
        delete = self.client.delete(f"/api/company-groups/{empty_group.id}")
        self.assertEqual(delete.status_code, 204)
        self.assertFalse(CompanyGroup.objects.filter(pk=empty_group.id).exists())

    def test_tenant_admin_can_disable_and_reenable_user(self):
        managed_user = User.objects.create_user(
            "managed@example.com", "secret", company=self.company_a, role="VIEWER")
        self.client.force_authenticate(self.user_a)
        disabled = self.client.patch(f"/api/users/{managed_user.id}", {"is_active": False}, format="json")
        self.assertEqual(disabled.status_code, 200, disabled.json())
        listing = self.client.get("/api/users")
        rows = listing.json().get("results", listing.json()) if isinstance(listing.json(), dict) else listing.json()
        self.assertEqual(next(row for row in rows if row["id"] == str(managed_user.id))["status"], "Disabled")
        enabled = self.client.patch(f"/api/users/{managed_user.id}", {"is_active": True}, format="json")
        self.assertEqual(enabled.status_code, 200, enabled.json())
        managed_user.refresh_from_db()
        self.assertTrue(managed_user.is_active)

    def test_general_config_is_persisted_and_login_switch_is_enforced(self):
        login_user = User.objects.create_user(
            "login-switch@example.com", "secret", company=self.company_a, role="VIEWER",
            mfa_enabled=False,
        )
        self.client.force_authenticate(self.user_a)
        response = self.client.patch("/api/config", {
            "allow_user_logins": False, "enable_auto_backups": False,
        }, format="json")
        self.assertEqual(response.status_code, 200, response.json())
        config = SystemConfig.objects.get(company=self.company_a)
        self.assertFalse(config.allow_user_logins)
        self.assertFalse(config.enable_auto_backups)
        self.client.force_authenticate(user=None)
        login = self.client.post("/api/auth/login", {
            "email": login_user.email, "password": "secret"}, format="json")
        self.assertEqual(login.status_code, 403)
