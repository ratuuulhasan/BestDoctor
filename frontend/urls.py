from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("workspace/", views.portal, name="portal"),
    path("login/", views.limited_auth(LoginView.as_view(template_name="frontend/login.html")), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("doctor/register/", views.register, name="register"),
    path("doctor/dashboard/", views.dashboard, name="dashboard"),
    path("doctor/profile/", views.profile, name="profile"),
    path("doctor/independent-chambers/new/", views.independent_chamber, name="independent-new"),
    path("doctor/independent-chambers/<int:pk>/", views.independent_chamber, name="independent-edit"),
    path("doctor/records/<slug:section>/new/", views.record, name="record-new"),
    path("doctor/records/<slug:section>/<int:pk>/", views.record, name="record-edit"),
    path("doctor/records/<slug:section>/<int:pk>/remove/", views.remove_record, name="record-remove"),
    path("manage/hospitals/", views.facilities, name="facilities"),
    path("manage/hospitals/<int:hospital_id>/<slug:kind>/", views.facility_edit, name="facility-edit"),
    path("manage/hospitals/<int:hospital_id>/<slug:kind>/<int:pk>/", views.facility_edit, name="facility-record"),
]
