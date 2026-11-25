from django.contrib import admin

from .models import ContactMessage


@admin.register(ContactMessage)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("subject", "name", "handled", "created_at")
    list_filter = ("handled",)
    readonly_fields = ("name", "email", "subject", "message", "created_at")
