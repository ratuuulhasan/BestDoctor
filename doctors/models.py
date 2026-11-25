import uuid

from django.conf import settings
from django.db import models

from core.directory import DatedPosition


class DoctorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    full_name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True, default=uuid.uuid4, editable=False)
    bmdc_number = models.CharField("BM&DC registration number", max_length=48, unique=True)
    designation = models.CharField(max_length=160, blank=True)
    biography = models.TextField(blank=True)
    gender = models.CharField(max_length=40, blank=True)
    experience_years = models.PositiveSmallIntegerField(default=0)
    profile_image = models.ImageField(upload_to="doctors/", blank=True)
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False, editable=False)
    is_published = models.BooleanField(default=False, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    specialties = models.ManyToManyField("specialties.Specialty", through="DoctorSpecialty")
    hospitals = models.ManyToManyField("hospitals.Hospital", through="hospitals.HospitalDoctor")
    chambers = models.ManyToManyField("chambers.Chamber", through="chambers.DoctorChamber")

    def clean(self):
        self.bmdc_number = self.bmdc_number.strip().upper()

    def __str__(self):
        return self.full_name


class DoctorQualification(models.Model):
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE)
    degree = models.CharField(max_length=120)
    institution = models.CharField(max_length=180)
    passing_year = models.PositiveSmallIntegerField()
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.degree}, {self.institution}"


class DoctorExperience(DatedPosition):
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE)
    organization = models.CharField(max_length=180)

    def __str__(self):
        return f"{self.designation}, {self.organization}"


class DoctorSpecialty(models.Model):
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE)
    specialty = models.ForeignKey("specialties.Specialty", on_delete=models.PROTECT)
    is_primary = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("doctor", "specialty"), name="doctor_specialty_once"),
            models.UniqueConstraint(fields=("doctor",), condition=models.Q(is_primary=True),
                                    name="doctor_one_primary_specialty"),
        ]

    def __str__(self):
        return str(self.specialty)


class DoctorAward(models.Model):
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE)
    title = models.CharField(max_length=160)
    organization = models.CharField(max_length=180)
    award_date = models.DateField()

    def __str__(self):
        return self.title


class DoctorLanguage(models.Model):
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE)
    language = models.CharField(max_length=80)
    proficiency = models.CharField(max_length=80)

    def __str__(self):
        return self.language


class DoctorSocialLink(models.Model):
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE)
    platform = models.CharField(max_length=80)
    url = models.URLField()

    def __str__(self):
        return self.platform
