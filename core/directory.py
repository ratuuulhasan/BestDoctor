from django.core.exceptions import ValidationError
from django.db import models


class NamedPlace(models.Model):
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, allow_unicode=True)

    class Meta:
        abstract = True
        ordering = ("name", "pk")

    def __str__(self):
        return self.name


class Facility(NamedPlace):
    district = models.ForeignKey("locations.District", on_delete=models.PROTECT)
    area = models.ForeignKey("locations.Area", null=True, blank=True, on_delete=models.PROTECT)
    address = models.TextField()
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    google_maps_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta(NamedPlace.Meta):
        abstract = True

    def clean(self):
        super().clean()
        if self.area_id and self.area.upazila.district_id != self.district_id:
            raise ValidationError({"area": "Choose an area in the selected district."})


class DatedPosition(models.Model):
    designation = models.CharField(max_length=160)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)

    class Meta:
        abstract = True
        ordering = ("-start_date", "pk")
        constraints = [models.CheckConstraint(
            condition=models.Q(end_date__isnull=True) | models.Q(end_date__gte=models.F("start_date")),
            name="%(app_label)s_%(class)s_dates",
        )]

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date must follow the start date."})

    @property
    def is_current(self):
        return self.end_date is None
