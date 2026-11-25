from django import forms

from hospitals.models import Hospital
from locations.models import District, Division
from specialties.models import Specialty


class DoctorSearchForm(forms.Form):
    q = forms.CharField(label="Doctor, specialty or facility", max_length=160, required=False)
    specialty = forms.ModelChoiceField(queryset=Specialty.objects.filter(is_active=True),
                                       required=False, empty_label="All specialties")
    division = forms.ModelChoiceField(queryset=Division.objects.all(), required=False,
                                      empty_label="All divisions")
    district = forms.ModelChoiceField(queryset=District.objects.all(), required=False,
                                      empty_label="All districts")
    hospital = forms.ModelChoiceField(queryset=Hospital.objects.filter(is_active=True),
                                      required=False, empty_label="All hospitals")
