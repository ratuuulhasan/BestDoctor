from decimal import Decimal
from uuid import uuid4

from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from audit.models import AuditLog
from doctors.models import DoctorProfile
from payments.models import Invoice
from subscriptions.models import SubscriptionPlan
from verification.tests import evidence


class PlatformAcceptanceTest(TestCase):
    def test_registration_publication_billing_and_community(self):
        doctor, patient, staff, visitor = (Client() for _ in range(4))
        admin = User.objects.create_user("workflow-staff@example.test", is_staff=True)
        admin.groups.add(Group.objects.get(name="Admin"))
        staff.force_login(admin)
        password = uuid4().hex
        doctor.post(reverse("register"), {"full_name": "Acceptance Doctor", "email": "workflow-doctor@example.test",
                    "bmdc_number": "WORKFLOW", "password1": password, "password2": password})
        profile = DoctorProfile.objects.get(bmdc_number="WORKFLOW")
        self.assertNotContains(visitor.get(reverse("public-doctors")), profile.full_name)
        doctor.post(reverse("verification-home"), {"evidence": evidence()})
        case = profile.verifications.get()
        staff.post(reverse("verification-detail", args=[case.pk]), {"decision": "approved"})
        doctor.post(reverse("publication"), {"action": "publish"})
        self.assertContains(visitor.get(reverse("public-doctors"), {"q": "Acceptance"}), profile.full_name)

        plan = SubscriptionPlan.objects.create(name="Acceptance annual", price=Decimal("150.00"), billing_cycle="annual")
        doctor.post(reverse("billing"), {"plan_id": plan.pk, "key": uuid4()})
        invoice = Invoice.objects.get()
        doctor.post(reverse("invoice-payment", args=[invoice.number]),
                    {"reference": "WORKFLOW", "amount": "150.00", "currency": "BDT"})
        payment = invoice.payments.get()
        staff.post(reverse("payment-decision", args=[payment.pk]),
                   {"decision": "verified", "amount": "150.00", "currency": "BDT"})
        self.assertContains(doctor.get(reverse("invoice-detail", args=[invoice.number])), "Active")

        patient.post(reverse("patient-register"), {"full_name": "Reader", "email": "workflow-patient@example.test",
                                                  "password1": password, "password2": password})
        self.assertEqual(patient.get(reverse("invoice-detail", args=[invoice.number])).status_code, 403)
        patient.post(reverse("write-review", args=[profile.slug]), {"rating": 5, "comment": "Helpful visit"})
        review = profile.review_set.get()
        staff.post(f"/api/v1/reviews/{review.pk}/moderate/", {"status": "approved"})
        self.assertContains(visitor.get(reverse("published-doctor", args=[profile.slug])), "Helpful visit")
        self.assertContains(patient.get(reverse("notifications")), "Review decision")
        patient.post(reverse("support-home"), {"subject": "My question", "priority": "normal", "message": "Hello"})
        self.assertContains(staff.get(reverse("support-home")), "My question")
        self.assertContains(staff.get(reverse("operations")), "150.00")
        self.assertTrue(AuditLog.objects.filter(actor_id=admin.pk, table_name="payments_payment").exists())
        doctor.post(reverse("publication"), {"action": "withdraw"})
        self.assertEqual(visitor.get(reverse("published-doctor", args=[profile.slug])).status_code, 404)
        self.assertNotContains(visitor.get(reverse("public-doctors")), profile.full_name)
