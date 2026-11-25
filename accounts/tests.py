from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .admin import AccountCreationForm
from .roles import ROLE_NAMES


User = get_user_model()


class IdentityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("Owner@Example.org", "test-only-pass")

    def setUp(self):
        cache.clear()

    def test_email_authentication_and_hashing(self):
        self.assertEqual(self.user.email, "owner@example.org")
        self.assertNotEqual(self.user.password, "test-only-pass")
        self.assertEqual(
            authenticate(username="OWNER@example.org", password="test-only-pass"),
            self.user,
        )

    def test_database_rejects_case_variant(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(email="OWNER@EXAMPLE.ORG")

    def test_default_roles_and_no_self_assignment(self):
        self.assertSetEqual(set(Group.objects.values_list("name", flat=True)),
                            set(ROLE_NAMES))
        self.assertFalse(self.user.groups.exists())
        self.client.force_login(self.user)
        response = self.client.post(reverse("identity"), {"is_superuser": True})
        self.assertEqual(response.status_code, 405)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_superuser)

    def test_token_lifecycle_and_private_identity(self):
        client = APIClient()
        self.assertIn(client.get(reverse("identity")).status_code, (401, 403))
        token = client.post(reverse("token"), {
            "username": self.user.email, "password": "test-only-pass",
        }).data["token"]
        client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        response = client.get(reverse("identity"))
        self.assertEqual(response.data["id"], self.user.pk)
        self.assertNotIn("password", response.data)
        self.assertEqual(client.post(reverse("revoke")).status_code, 204)
        self.assertIn(client.get(reverse("identity")).status_code, (401, 403))

    def test_inactive_user_cannot_log_in(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(reverse("token"), {
            "username": self.user.email, "password": "test-only-pass",
        })
        self.assertEqual(response.status_code, 400)

    def test_login_rate_limit(self):
        for _ in range(10):
            self.client.post(reverse("token"), {})
        self.assertEqual(self.client.post(reverse("token"), {}).status_code, 429)

    def test_staff_cannot_elevate_user(self):
        self.user.is_staff = True
        self.user.save()
        self.user.user_permissions.add(Permission.objects.get(
            content_type__app_label="accounts", codename="change_user",
        ))
        self.client.force_login(self.user)
        url = reverse("admin:accounts_user_change", args=[self.user.pk])
        self.assertEqual(self.client.post(url, {"is_superuser": True}).status_code, 403)

    def test_admin_creation_form_rejects_bad_email(self):
        form = AccountCreationForm(data={"email": "invalid"})
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_superuser_contract(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser("root@example.org", is_staff=False)
        admin = User.objects.create_superuser("root@example.org")
        self.assertTrue(admin.is_superuser and admin.is_staff)

    def test_health_and_schema(self):
        self.assertEqual(self.client.get(reverse("health")).json()["status"], "ok")
        response = self.client.get(reverse("schema"), {"format": "json"})
        self.assertIn("/api/v1/me/", response.json()["paths"])
