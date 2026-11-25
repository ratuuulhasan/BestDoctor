from django.core.exceptions import ValidationError
from django.db import models

from core.directory import NamedPlace


class Specialty(NamedPlace):
    slug = models.SlugField(max_length=180, unique=True, allow_unicode=True)
    parent = models.ForeignKey("self", blank=True, null=True, on_delete=models.PROTECT)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True)

    def clean(self):
        seen = {self.pk}
        node = self.parent if self.parent_id else None
        while node:
            if node.pk in seen:
                raise ValidationError({"parent": "Specialties cannot form a cycle."})
            seen.add(node.pk)
            node = node.parent
