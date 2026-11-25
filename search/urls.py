from django.urls import path
from . import views
from .api import PublicDoctorList

urlpatterns = [
    path("api/v1/directory/doctors/", PublicDoctorList.as_view(), name="public-doctor-api"),
    path("", views.home, name="home"),
    path("doctors/", views.doctors, name="public-doctors"),
    path("doctors/<slug:slug>/", views.profile, name="published-doctor"),
    path("specialties/", views.specialties, name="public-specialties"),
    path("specialties/<str:slug>/", views.specialty, name="public-specialty"),
    path("hospitals/", views.hospitals, name="public-hospitals"),
    path("hospitals/<str:slug>/", views.hospital, name="public-hospital"),
    path("locations/", views.locations, name="public-locations"),
    path("locations/<str:division_slug>/", views.locality, name="public-division"),
    path("locations/<str:division_slug>/<str:district_slug>/", views.locality, name="public-district"),
]
