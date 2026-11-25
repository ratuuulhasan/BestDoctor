from rest_framework import routers, serializers, viewsets

from chambers.models import Chamber
from doctors.models import DoctorProfile
from hospitals.models import Hospital
from locations.models import Area, District, Division, Upazila
from specialties.models import Specialty


class DoctorSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorProfile
        fields = ("id", "slug", "full_name", "designation", "biography", "experience_years",
                  "specialties", "hospitals", "chambers", "is_verified", "is_published")


class MyDoctorViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DoctorSerializer
    queryset = DoctorProfile.objects.none()

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or not user.groups.filter(name="Doctor").exists():
            return self.queryset
        return DoctorProfile.objects.filter(user=user, is_active=True).order_by("pk")


def lookup_view(model, fields, filters, queryset):
    """Build read-only, authenticated reference endpoints with explicit field lists."""
    meta = type("Meta", (), {"model": model, "fields": fields})
    serializer = type(f"{model.__name__}Serializer", (serializers.ModelSerializer,), {"Meta": meta})
    return type(f"{model.__name__}ViewSet", (viewsets.ReadOnlyModelViewSet,), {
        "serializer_class": serializer, "queryset": queryset.order_by("name", "pk"),
        "filterset_fields": filters,
    })


router = routers.SimpleRouter()
router.register("doctors", MyDoctorViewSet, basename="doctor")
for route, model, fields, filters, queryset in (
    ("divisions", Division, (), (), Division.objects.all()),
    ("districts", District, ("division",), ("division",), District.objects.all()),
    ("upazilas", Upazila, ("district",), ("district",), Upazila.objects.all()),
    ("areas", Area, ("upazila",), ("upazila",), Area.objects.all()),
    ("specialties", Specialty, ("parent", "description"), ("parent",), Specialty.objects.filter(is_active=True)),
    ("hospitals", Hospital, ("hospital_type", "address", "district", "area"), ("district", "hospital_type"),
     Hospital.objects.filter(is_active=True)),
    ("chambers", Chamber, ("hospital", "district", "area", "address"), ("district", "hospital"),
     Chamber.objects.filter(is_active=True)),
):
    router.register(route, lookup_view(model, ("id", "name", "slug", *fields), filters, queryset))
urlpatterns = router.urls
