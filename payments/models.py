import uuid

from django.conf import settings
from django.db import models


class Invoice(models.Model):
    class State(models.TextChoices):
        OPEN = "open", "Awaiting payment"
        PAID = "paid", "Paid"
        VOID = "void", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    number = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    subscription = models.OneToOneField("subscriptions.Subscription", on_delete=models.PROTECT)
    checkout_key = models.UUIDField()
    doctor = models.ForeignKey("doctors.DoctorProfile", on_delete=models.PROTECT)
    currency = models.CharField(max_length=3, default="BDT")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=12, choices=State, default=State.OPEN)
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["doctor", "checkout_key"], name="invoice_checkout_once"),
            models.CheckConstraint(condition=models.Q(total_amount__gt=0), name="positive_invoice"),
        ]


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, related_name="items", on_delete=models.PROTECT)
    description = models.CharField(max_length=160)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    @property
    def total_price(self):
        return self.quantity * self.unit_price


class Payment(models.Model):
    class State(models.TextChoices):
        PENDING = "pending", "Awaiting verification"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        REFUNDED = "refunded", "Refunded"

    invoice = models.ForeignKey(Invoice, related_name="payments", on_delete=models.PROTECT)
    provider = models.CharField(max_length=16, choices=[("manual", "Manual transfer"), ("simulator", "Local simulator")])
    reference = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=12, choices=State, default=State.PENDING)
    submitted_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True)

    class Meta:
        ordering = ["-pk"]
        permissions = [("review_payment", "Can reconcile payments and record refunds")]
        constraints = [
            models.UniqueConstraint(fields=["provider", "reference"], name="provider_transaction_once"),
            models.UniqueConstraint(fields=["invoice"], condition=models.Q(status="pending"), name="one_pending_payment"),
            models.UniqueConstraint(fields=["invoice"], condition=models.Q(status__in=["verified", "refunded"]),
                                    name="one_settled_payment"),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="positive_payment"),
        ]


class PaymentEvent(models.Model):
    payment = models.ForeignKey(Payment, related_name="events", on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    provider = models.CharField(max_length=16)
    event_key = models.CharField(max_length=140)
    kind = models.CharField(max_length=16)
    notes = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["pk"]
        constraints = [models.UniqueConstraint(fields=["provider", "event_key"], name="provider_event_once")]


class Refund(models.Model):
    payment = models.OneToOneField(Payment, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=100, unique=True)
    reason = models.CharField(max_length=300)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
