from django.db import models


class SiteSetting(models.Model):
    key = models.CharField(max_length=60, choices=[("contact_intro", "Contact page introduction")], unique=True)
    value = models.CharField(max_length=500)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.get_key_display()
