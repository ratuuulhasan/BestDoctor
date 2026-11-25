from datetime import timedelta
from uuid import uuid4

from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import PatientProfile, RepresentativeProfile, User
from cms.models import BlogCategory, BlogPost
from doctors.models import DoctorProfile
from notifications.models import Notification
from referrals.models import Referral
from reviews.models import Review
from support.models import ContactMessage, SupportTicket
from verification.models import DoctorVerification


class CommunityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.patient = User.objects.create_user("patient@example.test")
        PatientProfile.objects.create(user=cls.patient, full_name="Reader")
        cls.patient.groups.add(Group.objects.get(name="Patient"))
        cls.admin = User.objects.create_user("staff@example.test", is_staff=True)
        cls.admin.groups.add(Group.objects.get(name="Admin"))
        cls.owner = User.objects.create_user("doctor@example.test")
        cls.doctor = DoctorProfile.objects.create(user=cls.owner, full_name="Test Doctor", bmdc_number="T")
        DoctorVerification.objects.create(doctor=cls.doctor, status="approved", registration_number="T")
        DoctorProfile.objects.filter(pk=cls.doctor.pk).update(is_published=True, is_verified=True)

    def test_patient_review_moderation_report_and_private_notifications(self):
        self.client.force_login(self.patient)
        self.client.post(reverse("write-review", args=[self.doctor.slug]), {"rating": 4, "comment": "Clear explanations."})
        item = Review.objects.get()
        profile = reverse("published-doctor", args=[self.doctor.slug])
        self.assertNotContains(self.client.get(profile), item.comment)
        self.client.force_login(self.admin)
        response = self.client.post(f"/api/v1/reviews/{item.pk}/moderate/", {"status": "approved"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(self.client.get(profile), item.comment)
        self.assertEqual(self.client.get("/api/v1/notifications/").json()["count"], 0)
        self.client.force_login(self.patient)
        self.client.post(reverse("report-review", args=[item.pk]), {"reason": "Please check"})
        self.assertEqual(item.reviewreport_set.count(), 1)
        notice = Notification.objects.get(user=self.patient)
        self.client.post(reverse("read-notice", args=[notice.pk]))
        self.assertTrue(Notification.objects.get(pk=notice.pk).is_read)
        self.assertContains(self.client.get(reverse("patient-home")), item.comment)

    def test_support_queue_and_ticket_privacy(self):
        self.client.force_login(self.patient)
        self.client.post(reverse("support-home"), {"subject": "Account", "message": "Please help", "priority": "normal"})
        ticket = SupportTicket.objects.get()
        detail = reverse("support-detail", args=[ticket.number])
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.client.force_login(self.admin)
        self.client.post(detail, {"action": "claim"})
        self.client.post(detail, {"action": "reply", "message": "We have reviewed it."})
        self.client.force_login(self.patient)
        self.assertContains(self.client.get(detail), "We have reviewed it.")
        self.client.post(detail, {"action": "close"})
        self.client.post(detail, {"action": "reply", "message": "blocked"})
        self.assertEqual(ticket.messages.count(), 2)

    def test_public_information_and_draft_visibility(self):
        for path in ("/pages/about/", "/pages/privacy/", "/pages/terms/", "/blog/", "/faq/", "/contact/"):
            self.assertEqual(self.client.get(path).status_code, 200)
        cat = BlogCategory.objects.create(name="Health", slug="health")
        post = BlogPost.objects.create(category=cat, title="New", slug="new", content="Story",
                                       published=True, published_at=timezone.now()+timedelta(days=1))
        self.assertEqual(self.client.get("/blog/new/").status_code, 404)
        post.published_at = timezone.now()
        post.save()
        self.assertContains(self.client.get("/blog/new/"), "Story")
        self.client.post("/contact/", {"name": "Guest", "email": "guest@example.test", "subject": "Info", "message": "Question"})
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_referral_registration_and_patient_registration(self):
        rep = RepresentativeProfile.objects.create(user=self.owner)
        self.owner.groups.add(Group.objects.get(name="Representative"))
        password = uuid4().hex
        self.client.post(reverse("register"), {"email": "new@example.test", "full_name": "Doctor B",
                         "bmdc_number": "B", "password1": password, "password2": password, "referral_code": rep.referral_code})
        self.assertEqual(Referral.objects.get().representative, rep)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get("/representative/"), "Doctor B")
        self.client.logout()
        self.client.post(reverse("patient-register"), {"email": "reader@example.test", "full_name": "Reader B",
                         "password1": password, "password2": password})
        self.assertTrue(PatientProfile.objects.filter(user__email="reader@example.test").exists())
