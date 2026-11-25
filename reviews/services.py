from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from accounts.models import PatientProfile
from notifications.models import notify
from verification.services import published_profiles
from .models import Review, ReviewReport


def public_reviews():
    return Review.objects.filter(status=Review.Status.APPROVED, doctor__in=published_profiles())


@transaction.atomic
def submit(user, doctor_id, rating, comment):
    if not user.groups.filter(name="Patient").exists():
        raise PermissionDenied
    patient = get_object_or_404(PatientProfile.objects.select_for_update(), user=user)
    doctor = get_object_or_404(published_profiles(), pk=doctor_id)
    if doctor.user_id == user.pk:
        raise PermissionDenied
    if Review.objects.filter(patient=patient, doctor=doctor).exists():
        raise ValidationError("You already submitted a review for this doctor.")
    item = Review(patient=patient, doctor=doctor, rating=rating, comment=comment.strip())
    item.full_clean(exclude=["moderated_by", "moderated_at"])
    item.save()
    return item


@transaction.atomic
def moderate(user, pk, status):
    if not user.is_staff or not user.has_perm("reviews.change_review"):
        raise PermissionDenied
    item = get_object_or_404(Review.objects.select_for_update(), pk=pk)
    if user.pk in (item.patient.user_id, item.doctor.user_id):
        raise PermissionDenied
    if status not in (Review.Status.APPROVED, Review.Status.REJECTED):
        raise ValidationError("Choose approval or rejection.")
    if item.status != status:
        item.status, item.moderated_by, item.moderated_at = status, user, timezone.now()
        item.save(update_fields=["status", "moderated_by", "moderated_at"])
        notify(item.patient.user, "Review decision", f"Your review of {item.doctor} was {status}.")
    item.reviewreport_set.filter(resolved=False).update(resolved=True)
    return item


@transaction.atomic
def report(user, pk, reason):
    item = get_object_or_404(public_reviews().select_for_update(of=("self",)), pk=pk)
    if not reason.strip() or len(reason) > 500:
        raise ValidationError("Give a reason of up to 500 characters.")
    record, _ = ReviewReport.objects.get_or_create(review=item, reported_by=user, defaults={"reason": reason.strip()})
    return record
