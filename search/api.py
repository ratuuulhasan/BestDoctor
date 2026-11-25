from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, serializers
from rest_framework.permissions import AllowAny

from doctors.models import DoctorProfile
from .forms import DoctorSearchForm
from .queries import directory


class PublicDoctorSerializer(serializers.ModelSerializer):
    specialties = serializers.ListField(
        source="listed_specialties", child=serializers.CharField(), read_only=True,
    )

    class Meta:
        model = DoctorProfile
        fields = ("slug", "full_name", "designation", "specialties", "profile_image")


@extend_schema(parameters=[
    OpenApiParameter("q", str),
    *[OpenApiParameter(name, int) for name in ("specialty", "division", "district", "hospital")],
])
class PublicDoctorList(generics.ListAPIView):
    serializer_class = PublicDoctorSerializer
    queryset = DoctorProfile.objects.none()
    permission_classes = [AllowAny]

    def get_queryset(self):
        form = DoctorSearchForm(self.request.query_params)
        if not form.is_valid():
            raise serializers.ValidationError(form.errors)
        return directory(**form.cleaned_data)
