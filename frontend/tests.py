from datetime import time
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from chambers.models import Chamber, ChamberHoliday, ChamberSchedule, DoctorChamber
from doctors.models import DoctorProfile, DoctorQualification, DoctorSpecialty
from hospitals.models import Hospital, HospitalManager, HospitalType
from locations.models import Area, District, Division, Upazila
from specialties.models import Specialty


class DirectoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        division = Division.objects.create(name="Dhaka", slug="dhaka")
        cls.district = District.objects.create(division=division, name="Dhaka", slug="dhaka")
        cls.other = District.objects.create(division=division, name="Gazipur", slug="gazipur")
        upazila = Upazila.objects.create(district=cls.district, name="Savar", slug="savar")
        cls.area = Area.objects.create(upazila=upazila, name="Central", slug="central")
        cls.specialty = Specialty.objects.create(name="Medicine", slug="medicine")
        cls.facility = Hospital.objects.create(
            name="Teaching hospital", slug="teaching", district=cls.district, address="Savar",
            hospital_type=HospitalType.objects.create(name="Teaching"),
        )
        cls.chamber = Chamber.objects.create(name="Central", slug="central", district=cls.district)
        cls.user = User.objects.create_user("doctor@example.org")
        cls.user.groups.add(Group.objects.get(name="Doctor"))
        cls.doctor = DoctorProfile.objects.create(user=cls.user, full_name="Doctor A", bmdc_number="A1")
        cls.assignment = DoctorChamber.objects.create(doctor=cls.doctor, chamber=cls.chamber, consultation_fee=500)
        cls.other_user = User.objects.create_user("other@example.org")
        cls.other_doctor = DoctorProfile.objects.create(user=cls.other_user, full_name="Doctor B", bmdc_number="B2")

    def test_register_and_return_to_dashboard(self):
        response = self.client.post(reverse("register"), {
            "email": "New@example.org", "full_name": "New Doctor", "bmdc_number": " c3 ",
            "password1": "Example-pass-8331", "password2": "Example-pass-8331", "is_staff": True,
        }, follow=True)
        self.assertContains(response, "New Doctor")
        profile = DoctorProfile.objects.get(bmdc_number="C3")
        self.assertFalse(profile.user.is_staff or profile.is_published or profile.is_verified)
        self.assertTrue(profile.user.groups.filter(name="Doctor").exists())

    def test_duplicate_registration_has_no_partial_user(self):
        response = self.client.post(reverse("register"), {
            "email": "duplicate@example.org", "full_name": "Doctor A", "bmdc_number": "a1",
            "password1": "Example-pass-8331", "password2": "Example-pass-8331",
        })
        self.assertContains(response, "already recorded")
        self.assertFalse(User.objects.filter(email="duplicate@example.org").exists())

    def test_doctor_can_edit_own_profile_and_qualification(self):
        self.client.force_login(self.user)
        self.client.post(reverse("profile"), {
            "full_name": "Updated Doctor", "experience_years": 3, "is_verified": True,
        })
        self.doctor.refresh_from_db()
        self.assertEqual(self.doctor.full_name, "Updated Doctor")
        self.assertFalse(self.doctor.is_verified)
        response = self.client.post(reverse("record-new", args=["qualifications"]), {
            "degree": "MBBS", "institution": "College", "passing_year": 2018, "doctor": self.other_doctor.pk,
        }, follow=True)
        self.assertContains(response, "MBBS")
        self.assertEqual(DoctorQualification.objects.get().doctor, self.doctor)

    def test_cross_doctor_edit_and_schedule_assignment(self):
        self.client.force_login(self.user)
        item = DoctorQualification.objects.create(
            doctor=self.other_doctor, degree="MBBS", institution="College", passing_year=2020,
        )
        self.assertEqual(self.client.get(reverse("record-edit", args=["qualifications", item.pk])).status_code, 404)
        other = DoctorChamber.objects.create(doctor=self.other_doctor, chamber=self.chamber, consultation_fee=0)
        response = self.client.post(reverse("record-new", args=["holidays"]), {
            "doctor_chamber": other.pk, "holiday_date": "2027-01-01",
        })
        self.assertContains(response, "Select a valid choice")
        self.assertFalse(ChamberHoliday.objects.exists())

    def test_location_and_specialty_validation(self):
        self.facility.district = self.other
        self.facility.area = self.area
        with self.assertRaises(ValidationError):
            self.facility.full_clean()
        child = Specialty.objects.create(name="Internal", slug="internal", parent=self.specialty)
        self.specialty.parent = child
        with self.assertRaises(ValidationError):
            self.specialty.full_clean()

    def test_primary_specialty_and_fee_constraints(self):
        DoctorSpecialty.objects.create(doctor=self.doctor, specialty=self.specialty, is_primary=True)
        other = Specialty.objects.create(name="General", slug="general")
        with self.assertRaises(IntegrityError), transaction.atomic():
            DoctorSpecialty.objects.create(doctor=self.doctor, specialty=other, is_primary=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            DoctorChamber.objects.filter(pk=self.assignment.pk).update(consultation_fee=Decimal("-0.01"))

    def test_cross_chamber_overlap_and_adjacent_visits(self):
        limits = {"day_of_week": 0, "start_time": time(9), "end_time": time(10)}
        ChamberSchedule.objects.create(doctor_chamber=self.assignment, **limits)
        room = Chamber.objects.create(name="East", slug="east", district=self.other)
        second = DoctorChamber.objects.create(doctor=self.doctor, chamber=room, consultation_fee=100)
        with self.assertRaises(ValidationError):
            ChamberSchedule.objects.create(doctor_chamber=second, **limits)
        ChamberSchedule.objects.create(doctor_chamber=second, day_of_week=0, start_time=time(10), end_time=time(11))
        self.assertEqual(ChamberSchedule.objects.count(), 2)

    def test_manager_scope_and_revocation(self):
        self.other_user.groups.add(Group.objects.get(name="Hospital Manager"))
        self.client.force_login(self.other_user)
        url = reverse("facility-edit", args=[self.facility.pk, "hospital"])
        self.assertEqual(self.client.get(url).status_code, 404)
        assignment = HospitalManager.objects.create(hospital=self.facility, user=self.other_user)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {"name": "New hospital name", "district": self.district.pk, "address": "Savar"})
        self.facility.refresh_from_db()
        self.assertEqual(self.facility.name, "New hospital name")
        chamber_url = reverse("facility-record", args=[self.facility.pk, "chamber", self.chamber.pk])
        self.assertEqual(self.client.get(chamber_url).status_code, 404)
        assignment.is_active = False
        assignment.save()
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_directory_api_filters_and_private_doctor(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("hospital-list"), {"district": self.other.pk})
        self.assertEqual(response.json()["count"], 0)
        self.assertEqual(self.client.get(reverse("doctor-list")).json()["count"], 1)
        url = reverse("doctor-detail", args=[self.other_doctor.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(reverse("health")).json()["service"], "Best Doctor")

    def test_record_workflow(self):
        self.client.force_login(self.user)
        records = [
            ("experience", {"designation": "Consultant", "organization": "Clinic", "start_date": "2021-01-01"}),
            ("affiliations", {"hospital": self.facility.pk, "designation": "Consultant", "start_date": "2022-01-01"}),
            ("specialties", {"specialty": self.specialty.pk, "is_primary": "on"}),
            ("schedules", {"doctor_chamber": self.assignment.pk, "day_of_week": 1, "start_time": "09:00",
                           "end_time": "12:00", "max_patients": 12, "is_available": "on"}),
            ("holidays", {"doctor_chamber": self.assignment.pk, "holiday_date": "2027-01-01"}),
        ]
        for section, data in records:
            with self.subTest(section=section):
                response = self.client.post(reverse("record-new", args=[section]), data)
                self.assertRedirects(response, reverse("dashboard"))

    def test_private_chamber_creation_and_ownership(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("independent-new"), {
            "name": "Private room", "slug": "private-room", "district": self.district.pk,
            "address": "Savar", "is_active": "on", "owner": self.other_doctor.pk,
        })
        self.assertRedirects(response, reverse("dashboard"))
        room = Chamber.objects.get(slug="private-room")
        self.assertEqual(room.owner, self.doctor)
        self.other_user.groups.add(Group.objects.get(name="Doctor"))
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(reverse("independent-edit", args=[room.pk])).status_code, 404)

    def test_remove_owned_holiday(self):
        holiday = ChamberHoliday.objects.create(doctor_chamber=self.assignment, holiday_date="2027-02-01")
        url = reverse("record-remove", args=["holidays", holiday.pk])
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(self.client.post(url), reverse("dashboard"))
        self.assertFalse(ChamberHoliday.objects.exists())

    def test_admin_group_has_directory_access_only(self):
        self.user.groups.add(Group.objects.get(name="Admin"))
        self.assertTrue(self.user.has_perm("specialties.add_specialty"))
        self.assertFalse(self.user.has_perm("accounts.change_user"))
