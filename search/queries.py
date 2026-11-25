from django.db.models import Exists, OuterRef, Prefetch, Q
from django.utils import timezone

from chambers.models import ChamberHoliday, ChamberSchedule, DoctorChamber
from hospitals.models import HospitalDoctor
from specialties.models import Specialty
from verification.services import published_profiles


def visits():
    return DoctorChamber.objects.filter(is_active=True, chamber__is_active=True).filter(
        Q(chamber__hospital=None) | Q(chamber__hospital__is_active=True)
    ).select_related("chamber__hospital", "chamber__district").order_by("chamber__name", "pk")


def affiliations():
    today = timezone.localdate()
    return HospitalDoctor.objects.filter(hospital__is_active=True, start_date__lte=today).filter(
        Q(end_date=None) | Q(end_date__gte=today)
    ).select_related("hospital__district")


def directory(q="", specialty=None, division=None, district=None, hospital=None):
    rows = published_profiles().order_by("full_name", "pk").prefetch_related(
        Prefetch("specialties", queryset=Specialty.objects.filter(is_active=True), to_attr="listed_specialties"),
    )
    consulting = visits().filter(doctor_id=OuterRef("pk"))
    employed = affiliations().filter(doctor_id=OuterRef("pk"))
    if specialty:
        rows = rows.filter(specialties=specialty)
    if division:
        consulting = consulting.filter(chamber__district__division=division)
        employed = employed.filter(hospital__district__division=division)
    if district:
        consulting = consulting.filter(chamber__district=district)
        employed = employed.filter(hospital__district=district)
    if hospital:
        consulting = consulting.filter(chamber__hospital=hospital)
        employed = employed.filter(hospital=hospital)
    if division or district or hospital:
        rows = rows.filter(Exists(consulting) | Exists(employed))
    if q:
        matching_specialty = Specialty.objects.filter(is_active=True, name__icontains=q,
                                                       doctorprofile=OuterRef("pk"))
        rows = rows.filter(
            Q(full_name__icontains=q) | Q(designation__icontains=q) | Exists(matching_specialty)
            | Exists(consulting.filter(Q(chamber__name__icontains=q) | Q(chamber__hospital__name__icontains=q)))
            | Exists(employed.filter(hospital__name__icontains=q))
        )
    return rows


def profile_detail():
    appointments = visits().prefetch_related(
        Prefetch("chamberschedule_set", queryset=ChamberSchedule.objects.filter(is_available=True),
                 to_attr="sessions"),
        Prefetch("chamberholiday_set", queryset=ChamberHoliday.objects.filter(
            holiday_date__gte=timezone.localdate()).order_by("holiday_date"), to_attr="holidays"),
    )
    return directory().prefetch_related(
        Prefetch("doctorchamber_set", queryset=appointments, to_attr="listed_visits"),
        Prefetch("hospitaldoctor_set", queryset=affiliations(), to_attr="listed_affiliations"),
        "doctorqualification_set", "doctorexperience_set",
    )
