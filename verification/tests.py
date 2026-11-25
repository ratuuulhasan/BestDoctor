from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from threading import Barrier

from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from PIL import Image

from accounts.models import User
from doctors.models import DoctorProfile
from . import services
from .models import DoctorVerification, Status, VerificationDocument


def evidence():
    out = BytesIO()
    Image.new("RGB", (40, 30), "white").save(out, "PNG")
    return SimpleUploadedFile("registration.png", out.getvalue(), content_type="image/png")


def doctor_account():
    user = User.objects.create_user("doctor@example.org")
    user.groups.add(Group.objects.get(name="Doctor"))
    doctor = DoctorProfile.objects.create(user=user, full_name="Test Doctor", bmdc_number="T-123")
    return user, doctor


class VerificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.doctor = doctor_account()
        cls.staff = User.objects.create_user("reviewer@example.org", is_staff=True)
        cls.staff.groups.add(Group.objects.get(name="Admin"))
        cls.stranger = User.objects.create_user("other@example.org")
        cls.stranger.groups.add(Group.objects.get(name="Doctor"))

    def submit(self):
        return services.submit(self.owner, evidence())

    def test_web_submission_approval_publication_withdrawal(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("verification-home"), {"evidence": evidence()}, follow=True)
        self.assertContains(response, "Pending review")
        item = DoctorVerification.objects.get()
        self.assertEqual(item.registration_number, self.doctor.bmdc_number)
        url = reverse("published-doctor", args=[self.doctor.slug])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse("admin:index")), reverse("verification-queue"))
        self.assertContains(self.client.get(reverse("verification-queue")), self.doctor.full_name)
        self.client.post(reverse("verification-detail", args=[item.pk]), {"decision": "approved"})
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.owner)
        self.client.post(reverse("publication"), {"action": "publish"})
        self.client.logout()
        self.assertContains(self.client.get(url), self.doctor.full_name)
        self.client.force_login(self.owner)
        self.client.post(reverse("publication"), {"action": "withdraw"})
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(item.history.count(), 4)

    def test_rejection_requires_reason_and_allows_new_evidence(self):
        item = self.submit()
        with self.assertRaises(ValidationError):
            services.decide(self.staff, item.pk, Status.REJECTED, " ")
        services.decide(self.staff, item.pk, Status.REJECTED, "The number is unreadable.")
        with self.assertRaises(ValidationError):
            services.set_publication(self.owner, True)
        second = self.submit()
        self.assertNotEqual(second.pk, item.pk)
        self.assertEqual(item.history.last().remarks, "The number is unreadable.")

    def test_change_number_invalidates_even_if_original_number_returns(self):
        item = self.submit()
        services.decide(self.staff, item.pk, Status.APPROVED, "")
        services.set_publication(self.owner, True)
        for number in ("T-456", "T-123"):
            DoctorProfile.objects.filter(pk=self.doctor.pk).update(bmdc_number=number)
        self.doctor.refresh_from_db()
        item.refresh_from_db()
        self.assertFalse(self.doctor.is_published or self.doctor.is_verified)
        self.assertEqual(item.status, Status.SUPERSEDED)
        self.assertEqual(item.history.last().old_status, Status.APPROVED)
        self.assertFalse(services.published_profiles().exists())
        self.submit()

    def test_pending_number_change_and_repeated_decision(self):
        old = self.submit()
        DoctorProfile.objects.filter(pk=self.doctor.pk).update(bmdc_number="NEW")
        with self.assertRaises(ValidationError):
            services.decide(self.staff, old.pk, Status.APPROVED, "")
        current = self.submit()
        services.decide(self.staff, current.pk, Status.APPROVED, "")
        with self.assertRaises(ValidationError):
            services.decide(self.staff, current.pk, Status.REJECTED, "Changed mind")
        self.assertEqual(current.history.count(), 2)

    def test_document_access_and_response_headers(self):
        item = self.submit()
        doc = item.documents.get()
        url = reverse("verification-api-document", args=[doc.pk])
        self.assertIn(self.client.get(url).status_code, (401, 403))
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(reverse("verification-api")).json()["count"], 0)
        for user in (self.staff, self.owner):
            self.client.force_login(user)
            response = self.client.get(url)
            self.assertEqual(response["Content-Type"], "image/jpeg")
            self.assertIn("attachment", response["Content-Disposition"])
            self.assertIn("no-store", response["Cache-Control"])
            self.assertEqual(Image.open(BytesIO(response.content)).format, "JPEG")

    def test_unprivileged_staff_and_self_review(self):
        item = self.submit()
        url = reverse("verification-api-decision", args=[item.pk])
        self.owner.is_staff = True
        self.owner.save()
        self.owner.groups.add(Group.objects.get(name="Admin"))
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(url, {"decision": "approved"}).status_code, 403)
        self.stranger.is_staff = True
        self.stranger.save()
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.post(url, {"decision": "approved"}).status_code, 403)
        self.assertEqual(self.client.get(reverse("verification-queue")).status_code, 403)

    def test_invalid_and_oversized_files_leave_no_documents(self):
        for data in (b"not an image", b"x" * (5 * 1024 * 1024 + 1)):
            with self.assertRaises(ValidationError):
                services.submit(self.owner, SimpleUploadedFile("evidence.jpg", data))
        self.assertFalse(VerificationDocument.objects.exists())
        self.assertFalse(DoctorVerification.objects.exists())

    def test_api_flow_and_duplicate_submission(self):
        self.client.force_login(self.owner)
        url = reverse("verification-api")
        response = self.client.post(url, {"evidence": evidence()})
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["status"], "pending")
        self.assertEqual(len(data["documents"]), 1)
        self.assertEqual(self.client.post(url, {"evidence": evidence()}).status_code, 400)
        self.assertEqual(self.client.post(reverse("verification-api-publication"), {"published": True}).status_code, 400)
        self.client.force_login(self.staff)
        response = self.client.post(reverse("verification-api-decision", args=[data["id"]]), {"decision": "approved"})
        self.assertEqual(response.json()["status"], "approved")
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(reverse("verification-api-publication"), {"published": True}).status_code, 200)
        self.owner.is_active = False
        self.owner.save()
        self.assertFalse(services.published_profiles().exists())


class ConcurrentSubmissionTests(TransactionTestCase):
    def test_two_submissions_share_one_pending_slot(self):
        owner, _ = doctor_account()
        barrier = Barrier(2)

        def attempt():
            close_old_connections()
            try:
                user = User.objects.get(pk=owner.pk)
                barrier.wait(timeout=10)
                services.submit(user, evidence())
                return True
            except ValidationError:
                return False
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [pool.submit(attempt) for _ in range(2)]
            self.assertCountEqual([r.result() for r in results], [True, False])
        self.assertEqual(VerificationDocument.objects.count(), 1)
