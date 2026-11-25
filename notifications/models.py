from django.conf import settings
from django.db import models
from django.db import transaction


class NotificationPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    in_app_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=False)
    sms_enabled = models.BooleanField(default=False)


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=160)
    message = models.CharField(max_length=500)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["user", "is_read"])]


class EmailLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    subject = models.CharField(max_length=160)
    body = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    skipped = models.BooleanField(default=False)


class SubscriptionReminder(models.Model):
    subscription = models.ForeignKey("subscriptions.Subscription", on_delete=models.PROTECT)
    days_before = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["subscription", "days_before"], name="unique_term_reminder")]


@transaction.atomic
def notify(user, title, message):
    pref = NotificationPreference.objects.filter(user=user).first()
    if not pref or pref.in_app_enabled:
        Notification.objects.create(user=user, title=title, message=message)
    if pref and pref.email_enabled:
        EmailLog.objects.create(user=user, subject=title, body=message)
