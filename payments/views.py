import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from subscriptions.models import SubscriptionPlan
from verification.services import own_profile
from . import serializers as schema
from . import services
from .models import Invoice, Payment


def validated(request, serializer, action, *args):
    form = serializer(data=request.POST)
    if form.is_valid():
        try:
            return action(request.user, *args, **form.validated_data)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
    else:
        for field, errors in form.errors.items():
            messages.error(request, f"{field}: {' '.join(errors)}")


@login_required
@require_http_methods(["GET", "POST"])
def billing(request):
    doctor = own_profile(request.user)
    if request.method == "POST":
        invoice = validated(request, schema.CheckoutInput, services.checkout)
        if invoice:
            return redirect("invoice-detail", number=invoice.number)
    rows = Invoice.objects.filter(doctor=doctor).select_related("subscription").prefetch_related("items")
    return render(request, "payments/billing.html", {
        "plans": SubscriptionPlan.objects.filter(is_active=True), "key": uuid.uuid4(),
        "page": Paginator(rows, 20).get_page(request.GET.get("page")),
    })


@login_required
def detail(request, number):
    invoice = get_object_or_404(services.invoices_for(request.user), number=number)
    payments = invoice.payments.prefetch_related("events").select_related("refund")
    is_owner = invoice.doctor.user_id == request.user.pk
    return render(request, "payments/invoice.html", {
        "invoice": invoice, "payments": payments,
        "can_submit": is_owner and invoice.status == Invoice.State.OPEN
                      and not payments.filter(status=Payment.State.PENDING).exists(),
        "can_review": services.finance_staff(request.user) and not is_owner,
    })


@login_required
@require_POST
def submit(request, number):
    validated(request, schema.PaymentInput, services.submit_payment, number)
    return redirect("invoice-detail", number=number)


@login_required
@require_POST
def cancel(request, number):
    try:
        services.cancel(request.user, number)
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    return redirect("invoice-detail", number=number)


@login_required
def queue(request):
    if not services.finance_staff(request.user):
        raise PermissionDenied
    status = request.GET.get("status", Payment.State.PENDING)
    rows = Payment.objects.filter(status=status).select_related("invoice__doctor")
    return render(request, "payments/queue.html", {
        "page": Paginator(rows, 30).get_page(request.GET.get("page")),
        "status": status, "choices": Payment.State.choices,
    })


@login_required
@require_POST
def decision(request, pk):
    payment = validated(request, schema.DecisionInput, services.review, pk)
    return redirect("invoice-detail", number=payment.invoice.number) if payment else redirect("payment-queue")


@login_required
@require_POST
def refund(request, pk):
    payment = validated(request, schema.RefundInput, services.refund, pk)
    return redirect("invoice-detail", number=payment.invoice.number) if payment else redirect("payment-queue")
