import csv

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from payments.models import Payment
from reviews.models import Review
from support.models import SupportTicket
from verification.models import DoctorVerification
from verification.services import published_profiles
from .models import DailyReport
from .tasks import metrics


def require_reports(user):
    if not user.is_staff or not user.has_perm("analytics.view_dailyreport"):
        raise PermissionDenied


@login_required
def dashboard(request):
    require_reports(request.user)
    return render(request, "analytics/dashboard.html", {
        "published": published_profiles().count(),
        "verifications": DoctorVerification.objects.filter(status="pending").count(),
        "payments": Payment.objects.filter(status="pending").count(),
        "reviews": Review.objects.filter(status="pending").count(),
        "tickets": SupportTicket.objects.filter(closed=False).count(),
        "today": metrics(timezone.localdate()),
        "page": Paginator(DailyReport.objects.all(), 30).get_page(request.GET.get("page")),
    })


@login_required
def export(request, pk):
    require_reports(request.user)
    report = get_object_or_404(DailyReport, pk=pk)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="best-doctor-{report.date}.csv"'
    writer = csv.writer(response)
    writer.writerow(["Date", *report.metrics.keys()])
    writer.writerow([report.date, *report.metrics.values()])
    return response
