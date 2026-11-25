from django.contrib import admin

from .models import EmailLog


@admin.register(EmailLog)
class EmailDeliveryAdmin(admin.ModelAdmin):
    list_display = ("pk", "created_at", "attempts", "sent_at", "skipped")
    list_filter = ("skipped", "sent_at")
    fields = ("created_at", "attempts", "sent_at", "skipped")
    readonly_fields = fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
