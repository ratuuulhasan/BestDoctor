from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, routers, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from cms.models import BlogPost, FAQ, Page
from cms.views import blog_posts, published
from notifications.models import Notification, NotificationPreference
from referrals.models import Referral
from referrals.views import representative
from reviews import services as reviews
from reviews.models import Review
from support import services as support
from support.models import SupportMessage, SupportTicket


def validated(schema, request):
    data = schema(data=request.data)
    data.is_valid(raise_exception=True)
    return data.validated_data


def perform(service, *args, **kwargs):
    try:
        return service(*args, **kwargs)
    except ValidationError as error:
        raise serializers.ValidationError(error.messages) from error


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ("id", "doctor", "rating", "comment", "status", "created_at")


class ReviewInput(serializers.Serializer):
    doctor_id = serializers.IntegerField(min_value=1)
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(max_length=2000)


class ReportInput(serializers.Serializer):
    reason = serializers.CharField(max_length=500)


class DecisionInput(serializers.Serializer):
    status = serializers.ChoiceField(choices=("approved", "rejected"))


class Reviews(viewsets.ReadOnlyModelViewSet):
    queryset = Review.objects.none()
    serializer_class = ReviewSerializer
    filterset_fields = ["doctor"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        return reviews.public_reviews()

    @extend_schema(request=ReviewInput, responses={201: ReviewSerializer})
    def create(self, request):
        item = perform(reviews.submit, request.user, **validated(ReviewInput, request))
        return Response(self.get_serializer(item).data, status=201)

    @extend_schema(request=ReportInput, responses={204: None})
    @action(detail=True, methods=["post"])
    def report(self, request, pk=None):
        perform(reviews.report, request.user, pk, **validated(ReportInput, request))
        return Response(status=204)

    @extend_schema(request=DecisionInput, responses=ReviewSerializer)
    @action(detail=True, methods=["post"])
    def moderate(self, request, pk=None):
        item = perform(reviews.moderate, request.user, pk, **validated(DecisionInput, request))
        return Response(self.get_serializer(item).data)


class PostSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogPost
        fields = ("title", "slug", "content", "category", "tags", "published_at")


class PageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Page
        fields = ("title", "slug", "content", "published_at")


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ("id", "category", "question", "answer")


class Posts(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    serializer_class = PostSerializer
    queryset = BlogPost.objects.none()
    lookup_field = "slug"

    def get_queryset(self):
        return blog_posts(self.request.query_params)


class Pages(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    serializer_class = PageSerializer
    queryset = Page.objects.none()
    lookup_field = "slug"

    def get_queryset(self):
        return published(Page)


class FAQs(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    serializer_class = FAQSerializer
    queryset = FAQ.objects.filter(active=True).order_by("category", "pk")


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportMessage
        fields = ("message", "sender", "created_at")


class TicketSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = SupportTicket
        fields = ("number", "subject", "priority", "closed", "created_at", "messages")


class TicketInput(serializers.Serializer):
    subject = serializers.CharField(max_length=160)
    message = serializers.CharField(max_length=3000)
    priority = serializers.ChoiceField(choices=["normal", "high"], default="normal")


class TicketAction(serializers.Serializer):
    action = serializers.ChoiceField(choices=["reply", "claim", "close", "reopen"])
    message = serializers.CharField(max_length=3000, required=False, default="")


class Tickets(viewsets.ReadOnlyModelViewSet):
    serializer_class = TicketSerializer
    queryset = SupportTicket.objects.none()
    lookup_field = "number"
    lookup_value_regex = "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset
        return support.visible(self.request.user).prefetch_related("messages")

    @extend_schema(request=TicketInput, responses={201: TicketSerializer})
    def create(self, request):
        ticket = perform(support.open_ticket, request.user, **validated(TicketInput, request))
        return Response(self.get_serializer(ticket).data, status=201)

    @extend_schema(request=TicketAction, responses=TicketSerializer)
    @action(detail=True, methods=["post"])
    def respond(self, request, number=None):
        ticket = perform(support.update, request.user, number, **validated(TicketAction, request))
        return Response(self.get_serializer(ticket).data)


class NoticeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ("id", "title", "message", "is_read", "created_at")


class PreferenceInput(serializers.Serializer):
    in_app_enabled = serializers.BooleanField()


class Notices(viewsets.ReadOnlyModelViewSet):
    serializer_class = NoticeSerializer
    queryset = Notification.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset
        return Notification.objects.filter(user=self.request.user)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        item = self.get_object()
        item.is_read = True
        item.save(update_fields=["is_read"])
        return Response(status=204)

    @extend_schema(request=PreferenceInput, responses=PreferenceInput)
    @action(detail=False, methods=["post"])
    def preferences(self, request):
        values = validated(PreferenceInput, request)
        NotificationPreference.objects.update_or_create(user=request.user, defaults=values)
        return Response(values)


class ReferralSerializer(serializers.ModelSerializer):
    class Meta:
        model = Referral
        fields = ("id", "referred_doctor", "status", "created_at")


class Referrals(viewsets.ReadOnlyModelViewSet):
    serializer_class = ReferralSerializer
    queryset = Referral.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset
        return Referral.objects.filter(representative=representative(self.request.user))


router = routers.SimpleRouter()
for prefix, view, name in [
    ("reviews", Reviews, "community-review"), ("cms/posts", Posts, "cms-post"),
    ("cms/pages", Pages, "cms-page"), ("cms/faqs", FAQs, "cms-faq"),
    ("support/tickets", Tickets, "support-api"), ("notifications", Notices, "notification-api"),
    ("referrals", Referrals, "referral-api"),
]:
    router.register(prefix, view, basename=name)

urlpatterns = router.urls
