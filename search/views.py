from django.core.paginator import Paginator
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache

from hospitals.models import Hospital
from locations.models import District, Division
from specialties.models import Specialty
from reviews.services import public_reviews
from .forms import DoctorSearchForm
from .queries import directory, profile_detail


def page(request, rows):
    return Paginator(rows, 12).get_page(request.GET.get("page"))


def home(request):
    return render(request, "search/home.html", {"districts": District.objects.all()})


def doctors(request):
    form = DoctorSearchForm(request.GET)
    rows = directory(**form.cleaned_data) if form.is_valid() else directory().none()
    return render(request, "search/doctors.html", {
        "form": form, "title": "Find a doctor", "page": page(request, rows),
    })


@never_cache
def profile(request, slug):
    doctor = get_object_or_404(profile_detail(), slug=slug)
    rows = public_reviews().filter(doctor=doctor)
    return render(request, "search/profile.html", {
        "doctor": doctor, "reviews": page(request, rows),
        "ratings": rows.aggregate(average=Avg("rating"), count=Count("pk")),
    })


def specialties(request):
    return render(request, "search/index.html", {"title": "Specialties", "kind": "specialty",
                  "page": page(request, Specialty.objects.filter(is_active=True))})


def specialty(request, slug):
    item = get_object_or_404(Specialty, slug=slug, is_active=True)
    return render(request, "search/doctors.html", {"title": item.name, "description": item.description,
                  "page": page(request, directory(specialty=item))})


def hospitals(request):
    return render(request, "search/index.html", {"title": "Hospitals", "kind": "hospital",
                  "page": page(request, Hospital.objects.filter(is_active=True).select_related("district", "hospital_type"))})


def hospital(request, slug):
    item = get_object_or_404(Hospital.objects.select_related("district", "hospital_type"), slug=slug, is_active=True)
    return render(request, "search/doctors.html", {"title": item.name, "facility": item,
                  "page": page(request, directory(hospital=item))})


def locations(request):
    return render(request, "search/index.html", {"title": "Divisions and districts", "kind": "division",
                  "page": page(request, Division.objects.prefetch_related("district_set"))})


def locality(request, division_slug, district_slug=None):
    division = get_object_or_404(Division, slug=division_slug)
    district = get_object_or_404(District, division=division, slug=district_slug) if district_slug else None
    return render(request, "search/doctors.html", {
        "title": f"Doctors in {district or division}", "page": page(request, directory(division=division, district=district)),
        "division": division, "district": district,
    })
