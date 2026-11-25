from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.http import Http404

from accounts.models import User
from payments.models import Invoice
from payments.services import review, submit_payment


class Command(BaseCommand):
    help = "Simulate a local provider event against an existing development invoice."

    def add_arguments(self, parser):
        parser.add_argument("invoice", type=UUID)
        parser.add_argument("--reviewer", required=True, help="Existing finance staff email")
        parser.add_argument("--reference", required=True)
        parser.add_argument("--event", required=True, type=UUID)
        parser.add_argument("--result", choices=("verified", "rejected"), default="verified")

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            invoice = Invoice.objects.select_related("doctor__user").get(number=options["invoice"])
            staff = User.objects.get(email__iexact=options["reviewer"])
            payment = submit_payment(invoice.doctor.user, invoice.number, options["reference"],
                                     invoice.total_amount, invoice.currency, provider="simulator")
            result = review(staff, payment.pk, options["result"], invoice.total_amount, invoice.currency,
                            "Local simulated provider event", event_id=options["event"])
        except (Invoice.DoesNotExist, User.DoesNotExist, PermissionDenied, ValidationError, Http404) as error:
            raise CommandError(f"Simulation could not be recorded: {error}") from error
        self.stdout.write(f"Simulated payment {result.pk}: {result.status}")
