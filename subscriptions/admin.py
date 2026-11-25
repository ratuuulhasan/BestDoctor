from django.contrib import admin

from .models import SubscriptionPlan


@admin.register(SubscriptionPlan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "billing_cycle", "price", "is_active")
    list_filter = ("billing_cycle", "is_active")
    search_fields = ("name",)
