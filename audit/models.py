from django.db import models


class AuditLog(models.Model):
    actor_id = models.BigIntegerField(null=True)
    operation = models.CharField(max_length=12)
    table_name = models.CharField(max_length=100)
    object_id = models.BigIntegerField()
    changes = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-pk"]
        indexes = [models.Index(fields=["table_name", "object_id"])]


class ActivityLog(models.Model):
    user_id = models.BigIntegerField(null=True)
    route = models.CharField(max_length=120, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-pk"]
