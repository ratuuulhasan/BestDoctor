from datetime import timedelta

from django.contrib.auth.models import Group
from django.core import mail
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from audit.models import ActivityLog, AuditLog
from doctors.models import DoctorProfile
from notifications.models import EmailLog, Notification, NotificationPreference, notify
from notifications.tasks import deliver_email, expiry_reminders
from subscriptions.models import Subscription, SubscriptionPlan
from support.models import SupportTicket
from .models import DailyReport
from .tasks import generate_report


class OperationsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("operations@example.test")

    def test_audit_actor_redaction_and_report_permissions(self):
        self.client.force_login(self.user)
        self.client.post("/support/", {"subject": "Private subject", "message": "Sensitive text", "priority": "normal"})
        row = AuditLog.objects.get(table_name=SupportTicket._meta.db_table, operation="INSERT")
        self.assertEqual(row.actor_id, self.user.pk)
        self.assertNotIn("Private", str(row.changes))
        with self.assertRaises(IntegrityError), transaction.atomic():
            AuditLog.objects.filter(pk=row.pk).delete()
        self.client.get("/doctors/?q=private")
        self.assertTrue(ActivityLog.objects.filter(route="public-doctors", user_id=None).exists())
        today = str(timezone.localdate())
        generate_report(today)
        generate_report(today)
        report = DailyReport.objects.get()
        self.assertEqual(report.metrics["tickets_opened"], 1)
        self.assertEqual(self.client.get("/operations/").status_code, 403)
        self.user.groups.add(Group.objects.get(name="Admin"))
        self.user.is_staff = True
        self.user.save()
        self.assertContains(self.client.get("/operations/"), "Directory operations")
        self.assertContains(self.client.get(f"/operations/reports/{report.pk}/"), "tickets_opened")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_opt_in_mail_outbox_and_idempotent_reminder(self):
        pref = NotificationPreference.objects.create(user=self.user, email_enabled=True)
        doctor = DoctorProfile.objects.create(user=self.user, full_name="Doctor", bmdc_number="OPS")
        plan = SubscriptionPlan.objects.create(name="Annual", price=100, billing_cycle="annual")
        today = timezone.localdate()
        Subscription.objects.create(doctor=doctor, plan=plan, billing_cycle="annual", status="paid",
                                    start_date=today-timedelta(days=360), end_date=today+timedelta(days=5))
        self.assertEqual(expiry_reminders(), 1)
        self.assertEqual(expiry_reminders(), 0)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)
        self.assertEqual(deliver_email(), 1)
        self.assertEqual(deliver_email(), 0)
        self.assertEqual(len(mail.outbox), 1)
        notify(self.user, "Test", "Private update")
        pref.email_enabled = False
        pref.save()
        self.assertEqual(deliver_email(), 0)
        self.assertTrue(EmailLog.objects.filter(skipped=True).exists())
