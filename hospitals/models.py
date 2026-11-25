from django.conf import settings
from django.db import models

from core.directory import DatedPosition, Facility


class HospitalType(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Hospital(Facility):
    hospital_type = models.ForeignKey(HospitalType, on_delete=models.PROTECT)
    slug = models.SlugField(max_length=180, unique=True, allow_unicode=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to="hospitals/", blank=True)
    is_verified = models.BooleanField(default=False)


class HospitalImage(models.Model):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    image = models.ImageField(upload_to="hospitals/gallery/")
    caption = models.CharField(max_length=180, blank=True)


class HospitalManager(models.Model):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    designation = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("hospital", "user"), name="hospital_manager_once")]


class HospitalDoctor(DatedPosition):
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT)
    doctor = models.ForeignKey("doctors.DoctorProfile", on_delete=models.PROTECT)

    class Meta(DatedPosition.Meta):
        constraints = DatedPosition.Meta.constraints + [
            models.UniqueConstraint(fields=("hospital", "doctor", "start_date"), name="hospital_doctor_start"),
            models.UniqueConstraint(fields=("hospital", "doctor"), condition=models.Q(end_date=None),
                                    name="hospital_doctor_current"),
        ]

    def __str__(self):
        return f"{self.hospital} · {self.designation}"
