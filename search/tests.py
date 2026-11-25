from datetime import time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from chambers.models import Chamber, ChamberHoliday, ChamberSchedule, DoctorChamber
from doctors.models import DoctorProfile, DoctorSpecialty
from hospitals.models import Hospital, HospitalDoctor, HospitalType
from locations.models import District, Division
from specialties.models import Specialty
from verification.models import DoctorVerification, Status


class PublicDirectoryTests(TestCase):
    @classmethod
    def doctor_fixture(cls, number, public=True):
        user = User.objects.create_user(f"{number}@example.test")
        doctor = DoctorProfile.objects.create(user=user, full_name=f"Doctor {number}", bmdc_number=number)
        if public:
            DoctorVerification.objects.create(doctor=doctor, registration_number=number, status=Status.APPROVED)
            DoctorProfile.objects.filter(pk=doctor.pk).update(is_verified=True, is_published=True)
        return doctor

    @classmethod
    def setUpTestData(cls):
        cls.division = Division.objects.create(name="Dhaka", slug="dhaka")
        cls.district = District.objects.create(division=cls.division, name="Central", slug="central")
        cls.other = District.objects.create(division=cls.division, name="West", slug="west")
        cls.spec = Specialty.objects.create(name="Cardiology", slug="কার্ডিওলজি")
        cls.hospital = Hospital.objects.create(name="Green Hospital", slug="green", district=cls.district,
                                              hospital_type=HospitalType.objects.create(name="General"))
        cls.doctor = cls.doctor_fixture("Published")
        cls.private = cls.doctor_fixture("Private", public=False)
        DoctorSpecialty.objects.create(doctor=cls.doctor, specialty=cls.spec)
        cls.room = Chamber.objects.create(name="Garden Room", slug="garden", district=cls.district,
                                          hospital=cls.hospital)
        cls.visit = DoctorChamber.objects.create(doctor=cls.doctor, chamber=cls.room, consultation_fee=650)
        ChamberSchedule.objects.create(doctor_chamber=cls.visit, day_of_week=0, start_time=time(10), end_time=time(12))
        ChamberHoliday.objects.create(doctor_chamber=cls.visit, holiday_date=timezone.localdate()+timedelta(days=1))
        cls.doctor_url = reverse("published-doctor", args=[cls.doctor.slug])

    def test_home_anonymous_workspace_private(self):
        self.assertContains(self.client.get("/"), "Search doctors")
        self.assertEqual(self.client.get(reverse("portal")).status_code, 302)
        for name in ("public-specialties", "public-hospitals", "public-locations"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_html_and_api_search_same_public_rows(self):
        for term in ("pubLished", "cardio", "Garden", "Green Hospital"):
            params = {"q": term, "district": self.district.pk, "specialty": self.spec.pk}
            with self.subTest(term=term):
                self.assertContains(self.client.get(reverse("public-doctors"), params), self.doctor_url)
                data = self.client.get(reverse("public-doctor-api"), params).json()
                self.assertEqual(data["count"], 1)
                self.assertNotIn("user", data["results"][0])

    def test_scoped_landing_pages(self):
        for name, args in (("public-specialty", [self.spec.slug]), ("public-hospital", ["green"]),
                           ("public-division", ["dhaka"]), ("public-district", ["dhaka", "central"])):
            self.assertContains(self.client.get(reverse(name, args=args)), self.doctor_url)
        self.assertNotContains(self.client.get(reverse("public-district", args=["dhaka", "west"])), self.doctor_url)

    def test_detail_lists_dates_fees_and_hides_private_profile(self):
        page = self.client.get(self.doctor_url)
        for value in ("Garden Room", "650.00", "Monday", "Scheduled closures"):
            self.assertContains(page, value)
        self.assertEqual(self.client.get(reverse("published-doctor", args=[self.private.slug])).status_code, 404)
        DoctorProfile.objects.filter(pk=self.doctor.pk).update(is_published=False)
        self.assertEqual(self.client.get(self.doctor_url).status_code, 404)
        self.assertEqual(self.client.get(reverse("public-doctor-api")).json()["count"], 0)

    def test_inactive_hospital_suppresses_visits(self):
        self.hospital.is_active = False
        self.hospital.save()
        self.assertEqual(self.client.get(reverse("public-hospital", args=["green"])).status_code, 404)
        self.assertNotContains(self.client.get(self.doctor_url), "Garden Room")
        self.assertEqual(self.client.get(reverse("public-doctor-api"), {"q": "garden"}).json()["count"], 0)

    def test_date_bound_affiliations_and_consistent_geography(self):
        hospital = Hospital.objects.create(name="West Clinic", slug="west", district=self.other,
                                          hospital_type=self.hospital.hospital_type)
        today = timezone.localdate()
        job = HospitalDoctor.objects.create(doctor=self.doctor, hospital=hospital, designation="Consultant",
                                           start_date=today, end_date=today)
        url = reverse("public-doctor-api")
        self.assertEqual(self.client.get(url, {"hospital": hospital.pk}).json()["count"], 1)
        self.assertEqual(self.client.get(url, {"hospital": hospital.pk, "district": self.district.pk}).json()["count"], 0)
        job.start_date = job.end_date = today - timedelta(days=1)
        job.save()
        self.assertEqual(self.client.get(url, {"hospital": hospital.pk}).json()["count"], 0)

    def test_invalid_filters_and_pagination(self):
        url = reverse("public-doctors")
        self.assertContains(self.client.get(url, {"district": "bad"}), "Select a valid choice")
        self.assertEqual(self.client.get(reverse("public-doctor-api"), {"district": "bad"}).status_code, 400)
        for i in range(12):
            self.doctor_fixture(f"Extra{i}")
        response = self.client.get(url, {"q": "Doctor", "page": 1})
        self.assertContains(response, "q=Doctor&amp;page=2")
        self.assertContains(self.client.get(url, {"q": "Doctor", "page": 2}), "Page 2 of 2")
