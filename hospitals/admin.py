from django.contrib import admin

from . import models

admin.site.register([
    models.Hospital,
    models.HospitalType,
    models.HospitalImage,
    models.HospitalDoctor,
    models.HospitalManager,
])
