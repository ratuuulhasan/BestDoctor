from datetime import timedelta

from celery import shared_task
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from subscriptions.models import Subscription
from .models import EmailLog, NotificationPreference, SubscriptionReminder, notify


@shared_task
def deliver_email():
    candidates = EmailLog.objects.filter(sent_at=None, skipped=False, attempts__lt=5)
    sent = 0
    for pk in list(candidates.order_by("attempts", "pk").values_list("pk", flat=True)[:100]):
        with transaction.atomic():
            item = candidates.select_for_update(skip_locked=True).filter(pk=pk).first()
            if not item:
                continue
            if not item.user.is_active or not NotificationPreference.objects.filter(user=item.user, email_enabled=True).exists():
                item.skipped = True
                item.save(update_fields=["skipped"])
                continue
            item.attempts += 1
            try:
                delivered = send_mail(item.subject, item.body, None, [item.user.email])
            except (OSError, ValueError):
                delivered = 0
            if delivered:
                item.sent_at = timezone.now()
                sent += 1
            item.save(update_fields=["attempts", "sent_at"])
    return sent


@shared_task
def expiry_reminders():
    today = timezone.localdate()
    rows = Subscription.objects.filter(status="paid", start_date__lte=today, end_date__gt=today,
                                       end_date__lte=today+timedelta(days=7), doctor__user__is_active=True)
    count = 0
    for pk in rows.values_list("pk", flat=True).iterator():
        with transaction.atomic():
            term = rows.select_for_update().filter(pk=pk).first()
            if not term or Subscription.objects.filter(doctor=term.doctor, status="paid", start_date=term.end_date).exists():
                continue
            days = (term.end_date - today).days
            _, new = SubscriptionReminder.objects.get_or_create(subscription=term, days_before=1 if days == 1 else 7)
            if new:
                notify(term.doctor.user, "Subscription expiring", f"Your subscription expires on {term.end_date}.")
                count += 1
    return count
