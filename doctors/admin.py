from django.contrib import admin

from . import models

@admin.register(models.DoctorProfile)
class DoctorAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return ("user", "is_verified", "is_published") if obj else ("is_verified", "is_published")

    def save_model(self, request, obj, form, change):
        if change:
            obj.save(update_fields=[*form.changed_data, "updated_at"])
        else:
            super().save_model(request, obj, form, change)


admin.site.register([
    models.DoctorQualification,
    models.DoctorExperience,
    models.DoctorSpecialty,
    models.DoctorAward,
    models.DoctorLanguage,
    models.DoctorSocialLink,
])
