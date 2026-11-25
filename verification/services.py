from io import BytesIO

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError

from doctors.models import DoctorProfile
from .models import DoctorVerification, Status, VerificationDocument, VerificationHistory


def reviewer(user):
    return user.is_active and user.is_staff and user.has_perm("verification.review_evidence")


def own_profile(user):
    if not user.groups.filter(name="Doctor").exists():
        raise PermissionDenied
    return get_object_or_404(DoctorProfile, user=user, is_active=True)


def visible_to(user):
    rows = DoctorVerification.objects.select_related("doctor")
    if reviewer(user):
        return rows
    if user.groups.filter(name="Doctor").exists():
        return rows.filter(doctor__user=user, doctor__is_active=True)
    return rows.none()


def published_profiles():
    return DoctorProfile.objects.filter(
        is_active=True, user__is_active=True, is_verified=True, is_published=True,
        verifications__status=Status.APPROVED,
        verifications__registration_number=F("bmdc_number"),
    )


def evidence_bytes(upload):
    if not upload or upload.size > 5 * 1024 * 1024:
        raise ValidationError("Choose a JPEG or PNG image up to 5 MB.")
    try:
        with Image.open(upload, formats=("JPEG", "PNG")) as source:
            if source.width * source.height > 12_000_000:
                raise ValidationError("Choose an image of at most 12 megapixels.")
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.info.clear()
            output = BytesIO()
            image.save(output, format="JPEG", quality=88)
            if output.tell() > 5 * 1024 * 1024:
                raise ValidationError("The processed image exceeds 5 MB.")
            return output.getvalue()
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValidationError("Upload a readable JPEG or PNG image.") from exc


def submit(user, upload):
    owner = own_profile(user)
    image = evidence_bytes(upload)
    with transaction.atomic():
        doctor = get_object_or_404(DoctorProfile.objects.select_for_update(), pk=owner.pk, user=user, is_active=True)
        if doctor.verifications.filter(status__in=[Status.APPROVED, Status.PENDING]).exists():
            raise ValidationError("This registration is already approved or awaiting review.")
        item = DoctorVerification.objects.create(doctor=doctor, registration_number=doctor.bmdc_number)
        VerificationDocument.objects.create(verification=item, image=image)
        VerificationHistory.objects.create(verification=item, actor=user, new_status=item.status)
    return item


@transaction.atomic
def decide(user, pk, status, remarks):
    if not reviewer(user):
        raise PermissionDenied
    item = get_object_or_404(DoctorVerification, pk=pk)
    doctor = DoctorProfile.objects.select_for_update().get(pk=item.doctor_id)
    item.refresh_from_db()
    if doctor.user_id == user.pk:
        raise PermissionDenied
    if item.status != Status.PENDING or not doctor.is_active or not doctor.user.is_active:
        raise ValidationError("Only a pending submission for an active doctor can be reviewed.")
    if status not in (Status.REJECTED, Status.APPROVED) or (status == Status.REJECTED and not remarks.strip()):
        raise ValidationError("Choose a decision and include a reason for rejection.")
    if item.registration_number != doctor.bmdc_number:
        raise ValidationError("The registration number has changed. Fresh evidence is required.")
    item.status, item.remarks = status, remarks.strip()
    item.reviewed_at, item.reviewed_by = timezone.now(), user
    item.save(update_fields=["status", "remarks", "reviewed_at", "reviewed_by"])
    DoctorProfile.objects.filter(pk=doctor.pk).update(is_verified=status == Status.APPROVED, is_published=False)
    VerificationHistory.objects.create(
        verification=item, actor=user, old_status=Status.PENDING, new_status=status, remarks=item.remarks,
    )
    return item


@transaction.atomic
def set_publication(user, publish):
    owner = own_profile(user)
    doctor = get_object_or_404(DoctorProfile.objects.select_for_update(), pk=owner.pk, user=user, is_active=True)
    if publish and not doctor.verifications.filter(
        status=Status.APPROVED, registration_number=doctor.bmdc_number,
    ).exists():
        raise ValidationError("Approval for your current registration number is required.")
    if doctor.is_published != publish:
        DoctorProfile.objects.filter(pk=doctor.pk).update(is_published=publish)
        current = doctor.verifications.filter(status=Status.APPROVED).first()
        if current:
            VerificationHistory.objects.create(
                verification=current, actor=user, old_status=current.status, new_status=current.status,
                remarks="Profile published." if publish else "Profile withdrawn.",
            )
    return publish
