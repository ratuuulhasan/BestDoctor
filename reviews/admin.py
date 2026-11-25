from django.contrib import admin

from .models import Review, ReviewReport
from .services import moderate


@admin.register(Review)
class ModerationAdmin(admin.ModelAdmin):
    list_display = ("doctor", "patient", "rating", "status", "created_at")
    list_filter = ("status",)
    readonly_fields = tuple(f.name for f in Review._meta.fields)
    actions = ["approve", "reject"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(permissions=["change"], description="Approve reviews and resolve reports")
    def approve(self, request, queryset):
        for pk in queryset.values_list("pk", flat=True):
            moderate(request.user, pk, Review.Status.APPROVED)

    @admin.action(permissions=["change"], description="Reject reviews and resolve reports")
    def reject(self, request, queryset):
        for pk in queryset.values_list("pk", flat=True):
            moderate(request.user, pk, Review.Status.REJECTED)


@admin.register(ReviewReport)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("review_id", "reason", "resolved", "created_at")
    list_filter = ("resolved",)
    readonly_fields = tuple(f.name for f in ReviewReport._meta.fields)
