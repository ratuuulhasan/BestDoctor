from django.conf import settings
from django.db import models


class Status(models.TextChoices):
    PENDING = "pending", "Pending review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    SUPERSEDED = "superseded", "Registration changed"


class DoctorVerification(models.Model):
    doctor = models.ForeignKey("doctors.DoctorProfile", on_delete=models.PROTECT, related_name="verifications")
    registration_number = models.CharField(max_length=48)
    status = models.CharField(max_length=16, choices=Status, default=Status.PENDING)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    reviewed_at = models.DateTimeField(null=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-submitted_at", "-pk"]
        permissions = [("review_evidence", "Can review private registration evidence")]
        indexes = [models.Index(fields=["status", "submitted_at"])]
        constraints = [models.UniqueConstraint(
            fields=["doctor"], condition=models.Q(status__in=["pending", "approved"]),
            name="one_current_registration_review",
        )]


class VerificationDocument(models.Model):
    verification = models.ForeignKey(DoctorVerification, on_delete=models.PROTECT, related_name="documents")
    document_type = models.CharField(max_length=64, default="BM&DC registration evidence")
    image = models.BinaryField()


class VerificationHistory(models.Model):
    verification = models.ForeignKey(DoctorVerification, on_delete=models.PROTECT, related_name="history")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    old_status = models.CharField(max_length=16, blank=True)
    new_status = models.CharField(max_length=16)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
