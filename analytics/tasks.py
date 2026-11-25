from datetime import date, timedelta
from decimal import Decimal

from celery import shared_task
from django.db.models import Sum
from django.utils import timezone

from audit.models import ActivityLog
from payments.models import Payment, Refund
from reviews.models import Review
from support.models import SupportTicket
from verification.models import DoctorVerification
from .models import DailyReport


def metrics(day):
    payments = Payment.objects.filter(paid_at__date=day)
    refunds = Refund.objects.filter(created_at__date=day)
    received = payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    returned = refunds.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    return {
        "payments_verified": payments.count(), "received_bdt": str(received),
        "refunded_bdt": str(returned), "net_bdt": str(received - returned),
        "verification_submissions": DoctorVerification.objects.filter(submitted_at__date=day).count(),
        "reviews_submitted": Review.objects.filter(created_at__date=day).count(),
        "tickets_opened": SupportTicket.objects.filter(created_at__date=day).count(),
        "directory_searches": ActivityLog.objects.filter(created_at__date=day, route__in=["public-doctors", "public-doctor-api"]).count(),
    }


@shared_task
def generate_report(day=None):
    day = date.fromisoformat(day) if day else timezone.localdate() - timedelta(days=1)
    DailyReport.objects.update_or_create(date=day, defaults={"metrics": metrics(day)})
    return str(day)
