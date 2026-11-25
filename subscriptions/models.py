from django.conf import settings
from django.db import models
from django.utils import timezone


class Cycle(models.TextChoices):
    ANNUAL = "annual", "Annual"
    LIFETIME = "lifetime", "Lifetime"


class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=120, unique=True)
    billing_cycle = models.CharField(max_length=10, choices=Cycle)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["price", "pk"]
        constraints = [models.CheckConstraint(condition=models.Q(price__gt=0), name="positive_plan_price")]

    def __str__(self):
        return self.name


class Subscription(models.Model):
    class State(models.TextChoices):
        PENDING = "pending", "Awaiting payment"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    doctor = models.ForeignKey("doctors.DoctorProfile", on_delete=models.PROTECT)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    billing_cycle = models.CharField(max_length=10, choices=Cycle)
    status = models.CharField(max_length=12, choices=State, default=State.PENDING)
    start_date = models.DateField(null=True)
    end_date = models.DateField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["doctor"], condition=models.Q(status="pending"), name="one_open_order"),
            models.CheckConstraint(condition=(
                models.Q(start_date=None, end_date=None, status__in=["pending", "cancelled"])
                | (models.Q(start_date__isnull=False, status__in=["paid", "refunded"]) & (
                    models.Q(billing_cycle=Cycle.LIFETIME, end_date=None)
                    | models.Q(billing_cycle=Cycle.ANNUAL, end_date__isnull=False, end_date__gt=models.F("start_date"))
                ))
            ), name="valid_subscription_dates"),
        ]
        indexes = [models.Index(fields=["doctor", "status", "end_date"])]

    @property
    def coverage(self):
        if self.status != self.State.PAID:
            return self.get_status_display()
        today = timezone.localdate()
        if self.start_date > today:
            return "Scheduled"
        if self.end_date and today >= self.end_date:
            return "Expired"
        return "Active"


class SubscriptionHistory(models.Model):
    subscription = models.ForeignKey(Subscription, related_name="history", on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    old_status = models.CharField(max_length=12, blank=True)
    new_status = models.CharField(max_length=12)
    remarks = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["pk"]
