import uuid

from django.conf import settings
from django.db import models


class SupportTicket(models.Model):
    number = models.UUIDField(default=uuid.uuid4, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="tickets", on_delete=models.PROTECT)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="assigned_tickets",
                                    null=True, on_delete=models.PROTECT)
    subject = models.CharField(max_length=160)
    priority = models.CharField(max_length=12, choices=[("normal", "Normal"), ("high", "High")], default="normal")
    closed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]


class SupportMessage(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.PROTECT, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    message = models.CharField(max_length=3000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["pk"]


class ContactMessage(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    subject = models.CharField(max_length=160)
    message = models.CharField(max_length=3000)
    handled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
