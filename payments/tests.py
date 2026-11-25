from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import CommandError, call_command
from django.db import IntegrityError, close_old_connections, connections, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from doctors.models import DoctorProfile
from subscriptions.models import Cycle, Subscription, SubscriptionPlan
from . import services
from .models import Invoice, Payment, PaymentEvent, Refund


def doctor(email, number):
    user = User.objects.create_user(email)
    user.groups.add(Group.objects.get(name="Doctor"))
    DoctorProfile.objects.create(user=user, full_name=number, bmdc_number=number)
    return user


def staff_user():
    user = User.objects.create_user("finance@example.test", is_staff=True)
    user.groups.add(Group.objects.get(name="Admin"))
    return user


class BillingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = doctor("owner@example.test", "A1")
        cls.other = doctor("other@example.test", "A2")
        cls.staff = staff_user()
        cls.plan = SubscriptionPlan.objects.create(name="Annual", price=Decimal("1200.50"), billing_cycle=Cycle.ANNUAL)
        cls.lifetime = SubscriptionPlan.objects.create(name="Lifetime", price=9000, billing_cycle=Cycle.LIFETIME)

    def order(self, plan=None):
        return services.checkout(self.owner, (plan or self.plan).pk, uuid4())

    def payment(self, invoice, reference="TRANSFER-1"):
        return services.submit_payment(self.owner, invoice.number, reference, invoice.total_amount, "BDT")

    def settle(self, invoice, reference="TRANSFER-1"):
        payment = self.payment(invoice, reference)
        return services.review(self.staff, payment.pk, "verified", invoice.total_amount, "BDT")

    def test_checkout_replays_and_snapshots(self):
        key = uuid4()
        invoice = services.checkout(self.owner, self.plan.pk, key)
        self.plan.price = 999
        self.plan.save()
        self.assertEqual(services.checkout(self.owner, self.plan.pk, key), invoice)
        with self.assertRaises(ValidationError):
            services.checkout(self.owner, self.lifetime.pk, key)
        with self.assertRaises(ValidationError):
            self.order()
        self.assertEqual(invoice.items.get().total_price, Decimal("1200.50"))
        with self.assertRaises(IntegrityError), transaction.atomic():
            invoice.items.update(unit_price=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Invoice.objects.filter(pk=invoice.pk).update(total_amount=1)

    def test_amount_reference_and_currency_validation(self):
        invoice = self.order()
        for amount, currency in [(0, "BDT"), (invoice.total_amount, "USD")]:
            with self.assertRaises(ValidationError):
                services.submit_payment(self.owner, invoice.number, "T1", amount, currency)
        payment = self.payment(invoice)
        self.assertEqual(self.payment(invoice, " transfer-1 "), payment)
        with self.assertRaises(ValidationError):
            services.review(self.staff, payment.pk, "verified", invoice.total_amount, "USD")
        with self.assertRaises(ValidationError):
            services.review(self.staff, payment.pk, "verified", 1, "BDT")
        payment.refresh_from_db()
        self.assertEqual(payment.status, "pending")
        self.assertEqual(payment.events.count(), 1)

    def test_rejection_retry_and_cancel(self):
        invoice = self.order()
        payment = self.payment(invoice)
        with self.assertRaises(ValidationError):
            services.cancel(self.owner, invoice.number)
        with self.assertRaises(ValidationError):
            services.review(self.staff, payment.pk, "rejected", None, "", "")
        services.review(self.staff, payment.pk, "rejected", None, "", "Reference not found")
        self.settle(invoice, "CORRECT-REFERENCE")
        with self.assertRaises(ValidationError):
            services.cancel(self.owner, invoice.number)
        fresh = self.order()
        services.cancel(self.owner, fresh.number)
        with self.assertRaises(ValidationError):
            self.payment(fresh, "LATE")

    @patch("django.utils.timezone.localdate", return_value=date(2028, 2, 29))
    def test_renewal_lifetime_and_replay(self, clock):
        invoice = self.order()
        payment = self.settle(invoice)
        services.review(self.staff, payment.pk, "verified", invoice.total_amount, "BDT")
        term = Subscription.objects.get(pk=invoice.subscription_id)
        self.assertEqual((term.start_date, term.end_date), (date(2028, 2, 29), date(2029, 2, 28)))
        self.assertEqual(term.history.count(), 2)
        second = self.order()
        self.settle(second, "SECOND")
        renewed = Subscription.objects.get(pk=second.subscription_id)
        self.assertEqual((renewed.start_date, renewed.end_date), (term.end_date, date(2030, 2, 28)))
        self.assertEqual(renewed.coverage, "Scheduled")
        last = self.order(self.lifetime)
        self.settle(last, "LIFETIME")
        lifetime = Subscription.objects.get(pk=last.subscription_id)
        self.assertEqual(lifetime.start_date, renewed.end_date)
        self.assertIsNone(lifetime.end_date)
        with self.assertRaises(ValidationError):
            self.order()
        clock.return_value = date(2030, 2, 28)
        self.assertEqual(renewed.coverage, "Expired")
        self.assertEqual(lifetime.coverage, "Active")

    def test_full_refund_and_replay(self):
        invoice = self.order()
        payment = self.settle(invoice)
        with self.assertRaises(ValidationError):
            services.refund(self.staff, payment.pk, "RF-1", "Partial", amount=1)
        for _ in range(2):
            services.refund(self.staff, payment.pk, "RF-1", "Transfer returned")
        invoice.refresh_from_db()
        self.assertEqual((invoice.status, invoice.subscription.status), ("refunded", "refunded"))
        self.assertEqual(Refund.objects.get().amount, invoice.total_amount)
        self.assertEqual(payment.events.filter(kind="refunded").count(), 1)
        self.assertTrue(self.order().pk)

    def test_manual_payment_reference_cannot_move_between_doctors(self):
        first = self.order()
        self.payment(first)
        other = services.checkout(self.other, self.plan.pk, uuid4())
        with self.assertRaises(ValidationError):
            services.submit_payment(self.other, other.number, "TRANSFER-1", other.total_amount, "BDT")

    def test_scope_and_self_review(self):
        invoice = self.order()
        payment = self.payment(invoice)
        client = APIClient()
        client.force_authenticate(self.other)
        self.assertEqual(client.get(f"/api/v1/invoices/{invoice.number}/").status_code, 404)
        self.assertEqual(client.get(reverse("api-subscriptions")).data["count"], 0)
        self.assertEqual(client.post(f"/api/v1/payments/{payment.pk}/decision/",
                                    {"decision": "verified"}).status_code, 403)
        self.owner.is_staff = True
        self.owner.save()
        self.owner.groups.add(Group.objects.get(name="Admin"))
        with self.assertRaises(PermissionDenied):
            services.review(self.owner, payment.pk, "verified", invoice.total_amount, "BDT")

    def test_html_purchase_review_and_refund(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse("billing")), "1200.50")
        response = self.client.post(reverse("billing"), {"plan_id": self.plan.pk, "key": uuid4()}, follow=True)
        self.assertContains(response, "Submit transfer reference")
        invoice = Invoice.objects.get()
        self.client.post(reverse("invoice-payment", args=[invoice.number]),
                         {"reference": "WEB", "amount": "1200.50", "currency": "BDT"})
        self.client.force_login(self.staff)
        payment = Payment.objects.get()
        self.assertContains(self.client.get(reverse("payment-queue")), "WEB")
        response = self.client.post(reverse("payment-decision", args=[payment.pk]),
                                    {"decision": "verified", "amount": "1200.50", "currency": "BDT"}, follow=True)
        self.assertContains(response, "Record a full refund")
        response = self.client.post(reverse("payment-refund", args=[payment.pk]),
                                    {"reference": "WEB-REFUND", "reason": "Returned"}, follow=True)
        self.assertContains(response, "WEB-REFUND")

    def test_api_purchase_and_reconciliation(self):
        client = APIClient()
        client.force_authenticate(self.owner)
        response = client.post(reverse("api-invoices"), {"plan_id": self.plan.pk, "key": str(uuid4())})
        self.assertEqual(response.status_code, 201)
        url = f"/api/v1/invoices/{response.data['number']}/payments/"
        response = client.post(url, {"amount": "1200.50", "currency": "BDT", "reference": "API"})
        self.assertEqual(response.status_code, 201)
        client.force_authenticate(self.staff)
        response = client.post(f"/api/v1/payments/{response.data['id']}/decision/",
                               {"decision": "verified", "amount": "1200.50", "currency": "BDT"})
        self.assertEqual(response.data["status"], "verified")
        self.assertEqual(client.get("/api/v1/payments/").data["count"], 1)

    def test_simulated_event_replay(self):
        invoice = self.order()
        event = uuid4()
        for _ in range(2):
            call_command("simulate_payment", str(invoice.number), "--reference", "SIM-1",
                         "--event", str(event), "--reviewer", self.staff.email)
        self.assertEqual(Payment.objects.get().provider, "simulator")
        self.assertEqual(PaymentEvent.objects.filter(kind="verified").count(), 1)

    def test_conflicting_simulator_event_rolls_back_other_invoice(self):
        first, event = self.order(), uuid4()
        call_command("simulate_payment", str(first.number), "--reference", "SIM-1",
                     "--event", str(event), "--reviewer", self.staff.email)
        second = self.order()
        with self.assertRaises(CommandError):
            call_command("simulate_payment", str(second.number), "--reference", "SIM-2",
                         "--event", str(event), "--reviewer", self.staff.email)
        self.assertFalse(second.payments.exists())
        self.assertEqual(second.subscription.status, Subscription.State.PENDING)


class ConcurrentSettlementTests(TransactionTestCase):
    def test_simultaneous_verifications_only_grant_one_term(self):
        owner = doctor("lock@example.test", "LOCK")
        staff = staff_user()
        plan = SubscriptionPlan.objects.create(name="Annual", price=100, billing_cycle=Cycle.ANNUAL)
        invoice = services.checkout(owner, plan.pk, uuid4())
        payment = services.submit_payment(owner, invoice.number, "LOCK-1", 100, "BDT")
        barrier = Barrier(2)

        def verify():
            close_old_connections()
            try:
                actor = User.objects.get(pk=staff.pk)
                barrier.wait(timeout=10)
                return services.review(actor, payment.pk, "verified", 100, "BDT").status
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(verify) for _ in range(2)]
            self.assertEqual([task.result() for task in futures], ["verified", "verified"])
        self.assertEqual(payment.events.filter(kind="verified").count(), 1)
        self.assertEqual(invoice.subscription.history.filter(new_status="paid").count(), 1)
