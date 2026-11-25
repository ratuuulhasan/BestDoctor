import calendar

from django.core.exceptions import ValidationError
from django.db import models, transaction

from core.directory import Facility
from doctors.models import DoctorProfile


class Chamber(Facility):
    hospital = models.ForeignKey("hospitals.Hospital", on_delete=models.PROTECT, blank=True, null=True)
    owner = models.ForeignKey(
        DoctorProfile, on_delete=models.PROTECT, blank=True, null=True, related_name="independent_chambers",
    )

    class Meta(Facility.Meta):
        constraints = [
            models.UniqueConstraint(fields=("district", "slug"), name="chamber_slug_district"),
            models.CheckConstraint(condition=models.Q(owner=None) | models.Q(hospital=None),
                                   name="doctor_owned_chamber_is_independent"),
        ]


class ChamberContact(models.Model):
    chamber = models.ForeignKey(Chamber, on_delete=models.CASCADE)
    contact_type = models.CharField(max_length=60)
    contact_value = models.CharField(max_length=180)


class DoctorChamber(models.Model):
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.PROTECT)
    chamber = models.ForeignKey(Chamber, on_delete=models.PROTECT)
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2)
    fee_type = models.CharField(max_length=64, default="Consultation")
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("doctor", "chamber"), name="doctor_chamber_once"),
            models.CheckConstraint(condition=models.Q(consultation_fee__gte=0), name="nonnegative_chamber_fee"),
        ]

    def __str__(self):
        return f"{self.chamber} · {self.doctor}"


class ChamberSchedule(models.Model):
    doctor_chamber = models.ForeignKey(DoctorChamber, on_delete=models.CASCADE)
    day_of_week = models.PositiveSmallIntegerField(choices=list(enumerate(calendar.day_name)))
    start_time = models.TimeField()
    end_time = models.TimeField()
    max_patients = models.PositiveSmallIntegerField(default=1)
    is_available = models.BooleanField(default=True)

    class Meta:
        ordering = ("day_of_week", "start_time", "pk")
        constraints = [
            models.CheckConstraint(condition=models.Q(end_time__gt=models.F("start_time")), name="schedule_ordered"),
            models.CheckConstraint(condition=models.Q(day_of_week__lt=7, max_patients__gt=0), name="valid_schedule"),
        ]

    def clean(self):
        if not (self.doctor_chamber_id and self.is_available and self.start_time and self.end_time):
            return
        overlaps = ChamberSchedule.objects.filter(
            doctor_chamber__doctor_id=self.doctor_chamber.doctor_id,
            day_of_week=self.day_of_week, is_available=True,
            start_time__lt=self.end_time, end_time__gt=self.start_time,
        ).exclude(pk=self.pk)
        if overlaps.exists():
            raise ValidationError("This doctor already has a visiting session during those hours.")

    @transaction.atomic
    def save(self, *args, **kwargs):
        DoctorProfile.objects.select_for_update().get(pk=self.doctor_chamber.doctor_id)
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.doctor_chamber.chamber} · {self.get_day_of_week_display()} {self.start_time:%H:%M}–{self.end_time:%H:%M}"


class ChamberHoliday(models.Model):
    doctor_chamber = models.ForeignKey(DoctorChamber, on_delete=models.CASCADE)
    holiday_date = models.DateField()
    reason = models.CharField(max_length=180, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("doctor_chamber", "holiday_date"), name="chamber_holiday_once")]

    def __str__(self):
        return f"{self.doctor_chamber.chamber} · {self.holiday_date}"
