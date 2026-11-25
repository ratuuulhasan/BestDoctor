from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from . import services


class TicketForm(forms.Form):
    subject = forms.CharField(max_length=160)
    message = forms.CharField(max_length=3000, widget=forms.Textarea(attrs={"rows": 4}))
    priority = forms.ChoiceField(choices=[("normal", "Normal"), ("high", "High")])


@login_required
def inbox(request):
    form = TicketForm(request.POST if request.method == "POST" else None)
    if form.is_valid():
        item = services.open_ticket(request.user, **form.cleaned_data)
        return redirect("support-detail", number=item.number)
    rows = services.visible(request.user)
    return render(request, "support/inbox.html", {"form": form, "page": Paginator(rows, 20).get_page(request.GET.get("page"))})


@login_required
def detail(request, number):
    item = get_object_or_404(services.visible(request.user), number=number)
    if request.method == "POST":
        try:
            services.update(request.user, number, request.POST.get("action"), request.POST.get("message", ""))
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        return redirect("support-detail", number=number)
    owner = item.user_id == request.user.pk
    return render(request, "support/detail.html", {
        "ticket": item, "can_reply": owner or item.assigned_to_id == request.user.pk or request.user.is_superuser,
        "can_claim": services.staff(request.user) and not owner and not item.assigned_to_id and not item.closed,
    })
