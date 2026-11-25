from django.core.exceptions import ValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from subscriptions.models import Subscription, SubscriptionPlan
from . import serializers as schema
from . import services
from .models import Invoice, Payment


def perform(action, *args, **kwargs):
    try:
        return action(*args, **kwargs)
    except ValidationError as error:
        raise serializers.ValidationError(error.messages) from error


class Plans(generics.ListAPIView):
    queryset = SubscriptionPlan.objects.filter(is_active=True)
    permission_classes = [AllowAny]
    serializer_class = schema.PlanSerializer


class Terms(generics.ListAPIView):
    queryset = Subscription.objects.none()
    serializer_class = schema.TermSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset
        return Subscription.objects.filter(invoice__in=services.invoices_for(self.request.user)).prefetch_related("history")


class InvoiceScope:
    queryset = Invoice.objects.none()
    serializer_class = schema.InvoiceSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset
        return services.invoices_for(self.request.user).prefetch_related(
            "subscription__history", "payments__events", "payments__refund",
        )


class Invoices(InvoiceScope, generics.ListCreateAPIView):
    @extend_schema(request=schema.CheckoutInput, responses={201: schema.InvoiceSerializer})
    def post(self, request):
        data = schema.CheckoutInput(data=request.data)
        data.is_valid(raise_exception=True)
        invoice = perform(services.checkout, request.user, **data.validated_data)
        return Response(schema.InvoiceSerializer(invoice).data, status=201)


class InvoiceDetail(InvoiceScope, generics.RetrieveAPIView):
    lookup_field = "number"


class Cancel(APIView):
    @extend_schema(request=None, responses=schema.InvoiceSerializer)
    def post(self, request, number):
        item = perform(services.cancel, request.user, number)
        return Response(schema.InvoiceSerializer(item).data)


class Submit(APIView):
    @extend_schema(request=schema.PaymentInput, responses={201: schema.PaymentSerializer})
    def post(self, request, number):
        data = schema.PaymentInput(data=request.data)
        data.is_valid(raise_exception=True)
        payment = perform(services.submit_payment, request.user, number, **data.validated_data)
        return Response(schema.PaymentSerializer(payment).data, status=201)


class Payments(generics.ListAPIView):
    queryset = Payment.objects.none()
    serializer_class = schema.PaymentSerializer
    filterset_fields = ["status"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset
        return Payment.objects.filter(invoice__in=services.invoices_for(self.request.user)).select_related(
            "invoice", "refund").prefetch_related("events")


class Decision(APIView):
    @extend_schema(request=schema.DecisionInput, responses=schema.PaymentSerializer)
    def post(self, request, pk):
        data = schema.DecisionInput(data=request.data)
        data.is_valid(raise_exception=True)
        payment = perform(services.review, request.user, pk, **data.validated_data)
        return Response(schema.PaymentSerializer(payment).data)


class RecordRefund(APIView):
    @extend_schema(request=schema.RefundInput, responses=schema.PaymentSerializer)
    def post(self, request, pk):
        data = schema.RefundInput(data=request.data)
        data.is_valid(raise_exception=True)
        payment = perform(services.refund, request.user, pk, **data.validated_data)
        return Response(schema.PaymentSerializer(payment).data)
