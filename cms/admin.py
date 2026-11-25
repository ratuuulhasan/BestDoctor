from django.contrib import admin

from .models import BlogCategory, BlogPost, BlogTag, FAQ, FAQCategory, Page


@admin.register(BlogPost, Page)
class ContentAdmin(admin.ModelAdmin):
    list_display = ("title", "published", "published_at")
    list_filter = ("published",)
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("author",)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.author = request.user
        super().save_model(request, obj, form, change)


admin.site.register([BlogCategory, BlogTag, FAQCategory, FAQ])
