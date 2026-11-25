from django.contrib import admin

from . import models

admin.site.register([
    models.Division,
    models.District,
    models.Upazila,
    models.Area,
])
