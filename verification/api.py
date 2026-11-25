from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import generics, serializers
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import DoctorVerification, Status, VerificationDocument, VerificationHistory
from .views import document_response


class HistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = VerificationHistory
        fields = ("old_status", "new_status", "remarks", "created_at")


class VerificationSerializer(serializers.ModelSerializer):
    history = HistorySerializer(many=True, read_only=True)
    documents = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = DoctorVerification
        fields = ("id", "doctor", "registration_number", "status", "submitted_at", "reviewed_at",
                  "remarks", "documents", "history")


class EvidenceSerializer(serializers.Serializer):
    evidence = serializers.FileField()


class DecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=[Status.APPROVED, Status.REJECTED])
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=2000, default="")


class PublicationSerializer(serializers.Serializer):
    published = serializers.BooleanField(required=True)


def run_action(action, *args):
    try:
        return action(*args)
    except ValidationError as error:
        raise serializers.ValidationError(error.messages) from error


class Attempts(generics.ListCreateAPIView):
    serializer_class = VerificationSerializer
    parser_classes = (MultiPartParser,)
    queryset = DoctorVerification.objects.none()
    filterset_fields = ("status",)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset
        documents = VerificationDocument.objects.only("id", "verification_id")
        return services.visible_to(self.request.user).prefetch_related(
            "history", Prefetch("documents", queryset=documents),
        )

    @extend_schema(request=EvidenceSerializer, responses={201: VerificationSerializer})
    def post(self, request):
        data = EvidenceSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        item = run_action(services.submit, request.user, data.validated_data["evidence"])
        return Response(VerificationSerializer(item).data, status=201)


class AttemptDetail(generics.RetrieveAPIView):
    serializer_class = VerificationSerializer
    queryset = DoctorVerification.objects.none()

    def get_queryset(self):
        return services.visible_to(self.request.user)


class Decision(APIView):
    @extend_schema(request=DecisionSerializer, responses=VerificationSerializer)
    def post(self, request, pk: int):
        data = DecisionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        item = run_action(services.decide, request.user, pk, data.validated_data["decision"],
                          data.validated_data["remarks"])
        return Response(VerificationSerializer(item).data)


class Publication(APIView):
    @extend_schema(request=PublicationSerializer, responses=PublicationSerializer)
    def post(self, request):
        data = PublicationSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = run_action(services.set_publication, request.user, data.validated_data["published"])
        return Response({"published": result})


class Document(APIView):
    @extend_schema(responses={(200, "image/jpeg"): OpenApiTypes.BINARY})
    def get(self, request, pk: int):
        return document_response(request.user, pk)
