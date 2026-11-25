from django.contrib import admin
from .models import Referral


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ("representative", "referred_doctor", "status", "created_at")
    list_filter = ("status",)
    readonly_fields = ("representative", "referred_doctor", "created_at")

    def has_add_permission(self, request):
        return False
