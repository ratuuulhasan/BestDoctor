from django.db import models

from core.directory import NamedPlace


class Division(NamedPlace):
    slug = models.SlugField(max_length=180, unique=True, allow_unicode=True)


class District(NamedPlace):
    division = models.ForeignKey(Division, on_delete=models.PROTECT)

    class Meta(NamedPlace.Meta):
        constraints = [models.UniqueConstraint(fields=("division", "slug"), name="district_slug_parent")]


class Upazila(NamedPlace):
    district = models.ForeignKey(District, on_delete=models.PROTECT)

    class Meta(NamedPlace.Meta):
        constraints = [models.UniqueConstraint(fields=("district", "slug"), name="upazila_slug_parent")]


class Area(NamedPlace):
    upazila = models.ForeignKey(Upazila, on_delete=models.PROTECT)

    class Meta(NamedPlace.Meta):
        constraints = [models.UniqueConstraint(fields=("upazila", "slug"), name="area_slug_parent")]
