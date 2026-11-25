from django.contrib import admin
from .models import ActivityLog, AuditLog


class LogAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditLog)
class AuditAdmin(LogAdmin):
    list_display = ("created_at", "actor_id", "operation", "table_name", "object_id")
    list_filter = ("table_name", "operation")


@admin.register(ActivityLog)
class ActivityAdmin(LogAdmin):
    list_display = ("created_at", "route", "user_id")
    list_filter = ("route",)
