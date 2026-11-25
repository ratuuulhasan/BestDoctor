from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from frontend.views import form_page, limited_auth, save_form
from verification.services import published_profiles
from . import services
from .forms import PatientRegistration, ReviewForm
from .models import Review


@limited_auth
def register(request):
    if request.user.is_authenticated:
        return redirect("portal")
    form = PatientRegistration(request.POST if request.method == "POST" else None)
    if form.is_valid():
        user = save_form(form)
        if user:
            login(request, user)
            return redirect("patient-home")
    return form_page(request, form, "Register as a patient", "login")


@login_required
def dashboard(request):
    if not request.user.groups.filter(name="Patient").exists():
        raise PermissionDenied
    rows = Review.objects.filter(patient__user=request.user).select_related("doctor")
    return render(request, "reviews/home.html", {"page": Paginator(rows, 20).get_page(request.GET.get("page"))})


@login_required
def write(request, slug):
    doctor = get_object_or_404(published_profiles(), slug=slug)
    if not request.user.groups.filter(name="Patient").exists():
        raise PermissionDenied
    form = ReviewForm(request.POST if request.method == "POST" else None)
    if form.is_valid():
        try:
            services.submit(request.user, doctor.pk, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
        else:
            messages.success(request, "Review submitted for moderation.")
            return redirect("patient-home")
    return form_page(request, form, f"Review {doctor.full_name}", "patient-home")


@login_required
@require_POST
def report(request, pk):
    item = get_object_or_404(services.public_reviews().select_related("doctor"), pk=pk)
    try:
        services.report(request.user, pk, request.POST.get("reason", ""))
        messages.success(request, "Report received for moderation.")
    except ValidationError as error:
        messages.error(request, error.messages[0])
    return redirect("published-doctor", slug=item.doctor.slug)
