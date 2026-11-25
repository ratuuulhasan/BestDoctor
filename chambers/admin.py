from django.contrib import admin

from . import models

admin.site.register([
    models.Chamber,
    models.ChamberContact,
    models.DoctorChamber,
    models.ChamberSchedule,
    models.ChamberHoliday,
])
