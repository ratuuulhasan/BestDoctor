from django.db import models


class DailyReport(models.Model):
    date = models.DateField(unique=True)
    metrics = models.JSONField(default=dict)
    generated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
