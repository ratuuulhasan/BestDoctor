from rest_framework import serializers

from subscriptions.models import Subscription, SubscriptionHistory, SubscriptionPlan
from .models import Invoice, InvoiceItem, Payment, PaymentEvent, Refund


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = ("id", "name", "description", "billing_cycle", "price")


class SubscriptionHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionHistory
        fields = ("old_status", "new_status", "remarks", "created_at")


class TermSerializer(serializers.ModelSerializer):
    history = SubscriptionHistorySerializer(many=True, read_only=True)
    coverage = serializers.CharField(read_only=True)

    class Meta:
        model = Subscription
        fields = ("id", "plan", "billing_cycle", "status", "coverage", "start_date", "end_date", "history")


class ItemSerializer(serializers.ModelSerializer):
    total_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = InvoiceItem
        fields = ("description", "quantity", "unit_price", "total_price")


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentEvent
        fields = ("kind", "notes", "created_at")


class RefundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = ("amount", "reference", "reason", "created_at")


class PaymentSerializer(serializers.ModelSerializer):
    events = EventSerializer(many=True, read_only=True)
    refund = RefundSerializer(read_only=True)
    invoice_number = serializers.UUIDField(source="invoice.number", read_only=True)

    class Meta:
        model = Payment
        fields = ("id", "invoice_number", "provider", "reference", "amount", "currency",
                  "status", "submitted_at", "paid_at", "events", "refund")


class InvoiceSerializer(serializers.ModelSerializer):
    items = ItemSerializer(many=True, read_only=True)
    subscription = TermSerializer(read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = ("number", "issued_at", "status", "currency", "total_amount", "items", "subscription", "payments")


class CheckoutInput(serializers.Serializer):
    plan_id = serializers.IntegerField(min_value=1)
    key = serializers.UUIDField()


class PaymentInput(serializers.Serializer):
    reference = serializers.CharField(max_length=100)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField(max_length=3)


class DecisionInput(serializers.Serializer):
    decision = serializers.ChoiceField(choices=[Payment.State.VERIFIED, Payment.State.REJECTED])
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=None)
    currency = serializers.CharField(max_length=3, required=False, default="")
    notes = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class RefundInput(serializers.Serializer):
    reference = serializers.CharField(max_length=100)
    reason = serializers.CharField(max_length=300)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    currency = serializers.CharField(max_length=3, required=False)
