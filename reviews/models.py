from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Review(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    doctor = models.ForeignKey("doctors.DoctorProfile", on_delete=models.PROTECT)
    patient = models.ForeignKey("accounts.PatientProfile", on_delete=models.PROTECT)
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.CharField(max_length=2000)
    status = models.CharField(max_length=12, choices=Status, default=Status.PENDING, db_index=True)
    moderated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    moderated_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["doctor", "patient"], name="one_patient_review_per_doctor"),
            models.CheckConstraint(condition=models.Q(rating__range=(1, 5)), name="review_stars_range"),
        ]


class ReviewReport(models.Model):
    review = models.ForeignKey(Review, on_delete=models.PROTECT)
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=500)
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["review", "reported_by"], name="one_report_per_user")]
