from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.forms import DateInput, TimeInput, modelform_factory
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from chambers.models import Chamber, ChamberHoliday, ChamberSchedule, DoctorChamber
from doctors.forms import ProfileForm, RegistrationForm
from doctors.models import (
    DoctorAward, DoctorExperience, DoctorLanguage, DoctorProfile,
    DoctorQualification, DoctorSocialLink, DoctorSpecialty,
)
from hospitals.models import Hospital, HospitalDoctor
from specialties.models import Specialty

# Only these explicitly listed fields can be edited through the doctor portal.
RECORDS = {
    "qualifications": (DoctorQualification, ("degree", "institution", "passing_year", "description")),
    "experience": (DoctorExperience, ("organization", "designation", "start_date", "end_date")),
    "specialties": (DoctorSpecialty, ("specialty", "is_primary")),
    "affiliations": (HospitalDoctor, ("hospital", "designation", "start_date", "end_date")),
    "chambers": (DoctorChamber, ("chamber", "consultation_fee", "fee_type", "is_active")),
    "schedules": (ChamberSchedule, ("doctor_chamber", "day_of_week", "start_time", "end_time", "max_patients", "is_available")),
    "holidays": (ChamberHoliday, ("doctor_chamber", "holiday_date", "reason")),
    "awards": (DoctorAward, ("title", "organization", "award_date")),
    "languages": (DoctorLanguage, ("language", "proficiency")),
    "social-links": (DoctorSocialLink, ("platform", "url")),
}

REMOVABLE = {"qualifications", "experience", "specialties", "holidays", "awards", "languages", "social-links"}


def limited_auth(view):
    def dispatch(request, *args, **kwargs):
        if request.method == "POST":
            key = f"auth-form:{request.path}:{request.META.get('REMOTE_ADDR')}"
            cache.add(key, 0, timeout=60)
            if cache.incr(key) > 10:
                return HttpResponse("Try again in a minute.", status=429, headers={"Retry-After": "60"})
        return view(request, *args, **kwargs)
    return dispatch


def doctor_for(user):
    if not user.groups.filter(name="Doctor").exists():
        raise PermissionDenied
    return get_object_or_404(DoctorProfile, user=user, is_active=True)


def owned(model, doctor):
    if model in (ChamberHoliday, ChamberSchedule):
        return model.objects.filter(doctor_chamber__doctor=doctor).select_related("doctor_chamber__chamber")
    return model.objects.filter(doctor=doctor)


def form_page(request, form, title, back):
    return render(request, "frontend/form.html", {"form": form, "title": title, "back": back})


def save_form(form):
    try:
        with transaction.atomic():
            return form.save()
    except IntegrityError:
        form.add_error(None, "A matching record already exists or conflicts with this change.")
    except ValidationError as error:
        form.add_error(None, " ".join(error.messages))


@require_http_methods(["GET", "POST"])
@limited_auth
def register(request):
    if request.user.is_authenticated:
        return redirect("portal")
    form = RegistrationForm(request.POST or None)
    if form.is_valid():
        user = save_form(form)
        if user:
            login(request, user)
            return redirect("dashboard")
    return form_page(request, form, "Register as a doctor", "login")


@login_required
def portal(request):
    if request.user.groups.filter(name="Doctor").exists():
        return redirect("dashboard")
    if request.user.groups.filter(name="Hospital Manager").exists():
        return redirect("facilities")
    if request.user.is_staff:
        return redirect("admin:index")
    if request.user.groups.filter(name="Patient").exists():
        return redirect("patient-home")
    if request.user.groups.filter(name="Representative").exists():
        return redirect("referrals")
    raise PermissionDenied


@login_required
def dashboard(request):
    doctor = doctor_for(request.user)
    sections = [
        (key, key.replace("-", " ").capitalize(), owned(model, doctor))
        for key, (model, _) in RECORDS.items()
    ]
    return render(request, "frontend/dashboard.html", {"doctor": doctor, "sections": sections})


@login_required
@require_http_methods(["GET", "POST"])
def profile(request):
    form = ProfileForm(request.POST or None, request.FILES or None, instance=doctor_for(request.user))
    if form.is_valid() and save_form(form):
        messages.success(request, "Profile saved.")
        return redirect("dashboard")
    return form_page(request, form, "Edit doctor profile", "dashboard")


@login_required
@require_http_methods(["GET", "POST"])
def independent_chamber(request, pk=None):
    doctor = doctor_for(request.user)
    chamber = get_object_or_404(doctor.independent_chambers, pk=pk) if pk else Chamber(owner=doctor)
    form_type = modelform_factory(Chamber, fields=(
        "name", "slug", "district", "area", "address", "phone", "email", "google_maps_url", "is_active",
    ))
    form = form_type(request.POST or None, instance=chamber)
    if form.is_valid() and save_form(form):
        messages.success(request, "Chamber saved. Use Chambers to set your consultation fee.")
        return redirect("dashboard")
    return form_page(request, form, "Independent chamber", "dashboard")


@login_required
@require_http_methods(["GET", "POST"])
def record(request, section, pk=None):
    doctor = doctor_for(request.user)
    if section not in RECORDS:
        raise Http404
    model, fields = RECORDS[section]
    if pk:
        instance = get_object_or_404(owned(model, doctor), pk=pk)
    elif "doctor_chamber" in fields:
        instance = model()
    else:
        instance = model(doctor=doctor)
    widgets = {
        name: DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
        for name in fields if name.endswith("_date")
    }
    widgets.update({name: TimeInput(attrs={"type": "time"}) for name in fields if name.endswith("_time")})
    form_type = modelform_factory(model, fields=fields, widgets=widgets)
    form = form_type(request.POST or None, instance=instance)
    choices = {
        "doctor_chamber": DoctorChamber.objects.filter(doctor=doctor),
        "specialty": Specialty.objects.filter(Q(is_active=True) | Q(pk=getattr(instance, "specialty_id", None))),
        "hospital": Hospital.objects.filter(Q(is_active=True) | Q(pk=getattr(instance, "hospital_id", None))),
        "chamber": Chamber.objects.filter(Q(is_active=True) | Q(pk=getattr(instance, "chamber_id", None))),
    }
    for name, queryset in choices.items():
        if name in form.fields:
            form.fields[name].queryset = queryset
    if form.is_valid() and save_form(form):
        messages.success(request, "Record saved.")
        return redirect("dashboard")
    verb = "Edit" if pk else "Add"
    return render(request, "frontend/form.html", {
        "form": form, "title": f"{verb} {model._meta.verbose_name}", "back": "dashboard",
        "remove_section": section if pk and section in REMOVABLE else None, "pk": pk,
    })


@login_required
@require_POST
def remove_record(request, section, pk):
    if section not in REMOVABLE:
        raise Http404
    model, _ = RECORDS[section]
    instance = get_object_or_404(owned(model, doctor_for(request.user)), pk=pk)
    instance.delete()
    messages.success(request, "Record removed.")
    return redirect("dashboard")


def managed(user):
    if not user.groups.filter(name="Hospital Manager").exists():
        raise PermissionDenied
    return Hospital.objects.filter(hospitalmanager__user=user, hospitalmanager__is_active=True)


@login_required
def facilities(request):
    return render(request, "frontend/facilities.html", {"hospitals": managed(request.user)})


@login_required
@require_http_methods(["GET", "POST"])
def facility_edit(request, hospital_id, kind, pk=None):
    hospital = get_object_or_404(managed(request.user), pk=hospital_id)
    fields = ("name", "district", "area", "address", "phone", "email", "google_maps_url")
    if kind == "hospital" and pk is None:
        instance = hospital
        fields += ("website",)
    elif kind == "chamber":
        instance = get_object_or_404(Chamber, hospital=hospital, pk=pk) if pk else Chamber(hospital=hospital)
        fields += ("slug", "is_active")
    else:
        raise Http404
    form_type = modelform_factory(type(instance), fields=fields)
    form = form_type(request.POST or None, instance=instance)
    if form.is_valid() and save_form(form):
        messages.success(request, "Facility saved.")
        return redirect("facilities")
    return form_page(request, form, f"Manage {kind}", "facilities")
