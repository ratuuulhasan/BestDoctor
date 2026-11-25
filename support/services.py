from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404

from notifications.models import notify
from .models import SupportMessage, SupportTicket


def staff(user):
    return user.is_staff and user.has_perm("support.change_supportticket")


def visible(user):
    rows = SupportTicket.objects.select_related("user", "assigned_to")
    if user.is_superuser:
        return rows
    scope = Q(user=user)
    if staff(user):
        scope |= Q(assigned_to=None) | Q(assigned_to=user)
    return rows.filter(scope)


@transaction.atomic
def open_ticket(user, subject, message, priority="normal"):
    ticket = SupportTicket(user=user, subject=subject.strip(), priority=priority)
    ticket.full_clean(exclude=["assigned_to"])
    ticket.save()
    add_message(ticket, user, message)
    return ticket


def add_message(ticket, user, body):
    item = SupportMessage(ticket=ticket, sender=user, message=body.strip())
    item.full_clean()
    item.save()


@transaction.atomic
def update(user, number, action, message=""):
    ticket = get_object_or_404(visible(user).select_for_update(of=("self",)), number=number)
    if action not in ("claim", "reply", "close", "reopen"):
        raise ValidationError("Choose a ticket action.")
    if action == "claim":
        if not staff(user) or ticket.user_id == user.pk:
            raise PermissionDenied
        if ticket.closed:
            raise ValidationError("Reopen the ticket before claiming it.")
        ticket.assigned_to = user
        ticket.save(update_fields=["assigned_to"])
        return ticket
    if ticket.user_id != user.pk and ticket.assigned_to_id != user.pk and not user.is_superuser:
        raise PermissionDenied
    if action == "reply":
        if ticket.closed:
            raise ValidationError("Reopen the ticket before replying.")
        add_message(ticket, user, message)
    else:
        closed = action == "close"
        if closed == ticket.closed:
            return ticket
        ticket.closed = closed
        ticket.save(update_fields=["closed"])
    recipient = ticket.assigned_to if user.pk == ticket.user_id else ticket.user
    if recipient and recipient.pk != user.pk:
        notify(recipient, "Support ticket updated", ticket.subject)
    return ticket
