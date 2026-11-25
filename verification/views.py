from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.cache import patch_cache_control
from django.views.decorators.http import require_POST

from . import services
from .models import DoctorVerification, Status, VerificationDocument


class EvidenceForm(forms.Form):
    evidence = forms.FileField(
        label="BM&DC registration evidence",
        help_text="Upload a legible JPEG or PNG, up to 5 MB and 12 megapixels.",
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png"}),
    )


class DecisionForm(forms.Form):
    decision = forms.ChoiceField(choices=((Status.APPROVED, "Approve"), (Status.REJECTED, "Reject")),
                                 widget=forms.RadioSelect)
    remarks = forms.CharField(label="Feedback for the doctor", max_length=2000, required=False,
                              widget=forms.Textarea(attrs={"rows": 3}))


@login_required
def workspace(request):
    doctor = services.own_profile(request.user)
    form = EvidenceForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.submit(request.user, form.cleaned_data["evidence"])
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Evidence submitted for staff review.")
            return redirect("verification-home")
    attempts = doctor.verifications.prefetch_related("history")
    return render(request, "verification/workspace.html", {
        "doctor": doctor, "attempts": attempts, "form": form,
        "can_submit": not attempts.filter(status__in=[Status.PENDING, Status.APPROVED]).exists(),
    })


@login_required
@require_POST
def publication(request):
    if request.POST.get("action") not in ("publish", "withdraw"):
        return HttpResponse("Choose a publication action.", status=400)
    try:
        services.set_publication(request.user, request.POST.get("action") == "publish")
    except ValidationError as error:
        messages.error(request, error.messages[0])
    return redirect("verification-home")


@login_required
def queue(request):
    if not services.reviewer(request.user):
        raise PermissionDenied
    status = request.GET.get("status", Status.PENDING)
    rows = DoctorVerification.objects.filter(status=status).select_related("doctor").order_by("submitted_at")
    return render(request, "verification/queue.html", {
        "page": Paginator(rows, 30).get_page(request.GET.get("page")),
        "status": status, "choices": Status.choices,
    })


@login_required
def detail(request, pk):
    item = get_object_or_404(services.visible_to(request.user), pk=pk)
    form = DecisionForm(request.POST or None)
    if request.method == "POST":
        if not services.reviewer(request.user) or item.doctor.user_id == request.user.pk:
            raise PermissionDenied
        if form.is_valid():
            try:
                services.decide(request.user, pk, form.cleaned_data["decision"], form.cleaned_data["remarks"])
            except ValidationError as error:
                form.add_error(None, error)
                item.refresh_from_db()
            else:
                messages.success(request, "Review decision recorded.")
                return redirect("verification-queue")
    return render(request, "verification/detail.html", {
        "item": item, "documents": item.documents.only("id", "document_type"), "form": form,
        "can_decide": services.reviewer(request.user) and item.doctor.user_id != request.user.pk
                      and item.status == Status.PENDING,
    })


def document_response(user, pk):
    document = get_object_or_404(VerificationDocument, pk=pk, verification__in=services.visible_to(user))
    response = HttpResponse(bytes(document.image), content_type="image/jpeg")
    response["Content-Disposition"] = f'attachment; filename="registration-{document.pk}.jpg"'
    patch_cache_control(response, private=True, no_store=True)
    return response


@login_required
def download(request, pk):
    return document_response(request.user, pk)


