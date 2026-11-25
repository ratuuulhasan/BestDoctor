from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from doctors.models import DoctorProfile
from notifications.models import notify
from subscriptions.models import Cycle, Subscription, SubscriptionHistory, SubscriptionPlan
from verification.services import own_profile
from .models import Invoice, InvoiceItem, Payment, PaymentEvent, Refund


def finance_staff(user):
    return user.is_active and user.is_staff and user.has_perm("payments.review_payment")


def invoices_for(user):
    rows = Invoice.objects.select_related("subscription", "doctor").prefetch_related("items")
    if finance_staff(user):
        return rows
    return rows.filter(doctor=own_profile(user))


def lock_doctor(pk):
    return DoctorProfile.objects.select_for_update().get(pk=pk)


def change_term(term, status, actor, notes=""):
    previous = term.status
    term.status = status
    term.save(update_fields=["status", "start_date", "end_date"])
    SubscriptionHistory.objects.create(subscription=term, actor=actor, old_status=previous,
                                       new_status=status, remarks=notes)


@transaction.atomic
def checkout(user, plan_id, key):
    doctor = lock_doctor(own_profile(user).pk)
    previous = Invoice.objects.filter(doctor=doctor, checkout_key=key).first()
    if previous:
        if previous.subscription.plan_id != plan_id:
            raise ValidationError("This checkout key was already used for another plan.")
        return previous
    if not doctor.is_active:
        raise PermissionDenied
    plan = get_object_or_404(SubscriptionPlan.objects.select_for_update(), pk=plan_id, is_active=True)
    if Invoice.objects.filter(doctor=doctor, status=Invoice.State.OPEN).exists():
        raise ValidationError("Finish or cancel your open invoice before starting another order.")
    if Subscription.objects.filter(doctor=doctor, status=Subscription.State.PAID, billing_cycle=Cycle.LIFETIME).exists():
        raise ValidationError("A lifetime subscription is already paid.")
    term = Subscription.objects.create(doctor=doctor, plan=plan, billing_cycle=plan.billing_cycle)
    invoice = Invoice.objects.create(subscription=term, doctor=doctor, checkout_key=key, total_amount=plan.price)
    InvoiceItem.objects.create(invoice=invoice, description=plan.name, unit_price=plan.price)
    SubscriptionHistory.objects.create(subscription=term, actor=user, new_status=term.status)
    return invoice


def locked_owner_invoice(user, number):
    doctor = lock_doctor(own_profile(user).pk)
    if not doctor.is_active:
        raise PermissionDenied
    return get_object_or_404(Invoice, doctor=doctor, number=number)


@transaction.atomic
def cancel(user, number):
    invoice = locked_owner_invoice(user, number)
    if invoice.status == Invoice.State.VOID:
        return invoice
    if invoice.status != Invoice.State.OPEN or invoice.payments.filter(status=Payment.State.PENDING).exists():
        raise ValidationError("Only open invoices without a pending payment can be cancelled.")
    invoice.status = Invoice.State.VOID
    invoice.save(update_fields=["status"])
    change_term(invoice.subscription, Subscription.State.CANCELLED, user)
    return invoice


def log_event(payment, user, kind, key, notes=""):
    return PaymentEvent.objects.create(payment=payment, actor=user, provider=payment.provider,
                                       kind=kind, event_key=key, notes=notes)


def match_amount(invoice, amount, currency):
    if amount != invoice.total_amount or currency != invoice.currency:
        raise ValidationError("The amount and currency must match the issued invoice.")


@transaction.atomic
def submit_payment(user, number, reference, amount, currency, provider="manual"):
    invoice = locked_owner_invoice(user, number)
    reference = reference.strip().upper()
    if not reference or len(reference) > 100 or provider not in ("manual", "simulator"):
        raise ValidationError("Enter a valid transaction reference and provider.")
    match_amount(invoice, amount, currency)
    previous = Payment.objects.filter(provider=provider, reference=reference).first()
    if previous:
        if previous.invoice_id == invoice.pk:
            return previous
        raise ValidationError("This transaction reference cannot be used.")
    if invoice.status != Invoice.State.OPEN or invoice.payments.filter(status=Payment.State.PENDING).exists():
        raise ValidationError("This invoice cannot accept another payment attempt.")
    try:
        with transaction.atomic():
            payment = Payment.objects.create(invoice=invoice, provider=provider, reference=reference,
                                             amount=amount, currency=currency)
    except IntegrityError as error:
        raise ValidationError("This transaction reference cannot be used.") from error
    log_event(payment, user, "submitted", f"submitted:{payment.pk}")
    return payment


def locked_staff_payment(user, payment_id):
    if not finance_staff(user):
        raise PermissionDenied
    doctor_id = get_object_or_404(Payment.objects.select_related("invoice"), pk=payment_id).invoice.doctor_id
    doctor = lock_doctor(doctor_id)
    if doctor.user_id == user.pk:
        raise PermissionDenied
    return Payment.objects.select_related("invoice__subscription").get(pk=payment_id)


def activate(invoice, user):
    term = invoice.subscription
    today = timezone.localdate()
    latest = Subscription.objects.filter(doctor_id=invoice.doctor_id, status=Subscription.State.PAID,
                                         end_date__gt=today).order_by("-end_date").first()
    term.start_date = latest.end_date if latest else today
    if term.billing_cycle == Cycle.ANNUAL:
        start = term.start_date
        try:
            term.end_date = start.replace(year=start.year + 1)
        except ValueError:  # February 29 in a non-leap renewal year.
            term.end_date = start.replace(year=start.year + 1, day=28)
    change_term(term, Subscription.State.PAID, user)


@transaction.atomic
def review(user, payment_id, decision, amount, currency, notes="", event_id=None):
    payment = locked_staff_payment(user, payment_id)
    invoice = payment.invoice
    if decision not in (Payment.State.VERIFIED, Payment.State.REJECTED):
        raise ValidationError("Choose verify or reject.")
    notes = notes.strip()
    if decision == Payment.State.REJECTED and not notes:
        raise ValidationError("Give the doctor a reason for rejection.")
    if decision == Payment.State.VERIFIED:
        match_amount(invoice, amount, currency)
    key = f"external:{event_id}" if event_id else f"{decision}:{payment.pk}"
    event = PaymentEvent.objects.filter(provider=payment.provider, event_key=key).first()
    if event:
        if event.payment_id != payment.pk or event.kind != decision or event.notes != notes:
            raise ValidationError("The event key belongs to a different decision.")
        return payment
    if payment.status != Payment.State.PENDING or invoice.status != Invoice.State.OPEN:
        raise ValidationError("This payment has already been decided.")
    try:
        with transaction.atomic():
            log_event(payment, user, decision, key, notes)
    except IntegrityError as error:
        raise ValidationError("This event key has already been used.") from error
    payment.status = decision
    if decision == Payment.State.VERIFIED:
        payment.paid_at = timezone.now()
        invoice.status = Invoice.State.PAID
        invoice.save(update_fields=["status"])
        activate(invoice, user)
    payment.save(update_fields=["status", "paid_at"])
    notify(invoice.doctor.user, "Payment review", f"Payment on invoice {invoice.number} was {decision}.")
    return payment


@transaction.atomic
def refund(user, payment_id, reference, reason, amount=None, currency=None):
    payment = locked_staff_payment(user, payment_id)
    if (amount is not None and amount != payment.amount) or (currency is not None and currency != payment.currency):
        raise ValidationError("Record the full refund in the payment's original currency.")
    reference, reason = reference.strip().upper(), reason.strip()
    if not reference or not reason:
        raise ValidationError("Enter the refund reference and reason.")
    previous = Refund.objects.filter(payment=payment).first()
    if previous and previous.reference == reference and previous.reason == reason:
        return payment
    if payment.status != Payment.State.VERIFIED:
        raise ValidationError("Only a verified payment can be refunded.")
    try:
        with transaction.atomic():
            Refund.objects.create(payment=payment, amount=payment.amount, reference=reference,
                                  reason=reason, recorded_by=user)
    except IntegrityError as error:
        raise ValidationError("This refund reference has already been recorded.") from error
    payment.status = Payment.State.REFUNDED
    payment.save(update_fields=["status"])
    invoice = payment.invoice
    invoice.status = Invoice.State.REFUNDED
    invoice.save(update_fields=["status"])
    change_term(invoice.subscription, Subscription.State.REFUNDED, user, reason)
    log_event(payment, user, "refunded", f"refunded:{payment.pk}", reason)
    notify(invoice.doctor.user, "Refund recorded", f"A full refund was recorded for invoice {invoice.number}.")
    return payment
