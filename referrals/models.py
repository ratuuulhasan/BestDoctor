from django.db import models


class Referral(models.Model):
    representative = models.ForeignKey("accounts.RepresentativeProfile", on_delete=models.PROTECT)
    referred_doctor = models.OneToOneField("doctors.DoctorProfile", on_delete=models.PROTECT)
    status = models.CharField(max_length=12, choices=[("recorded", "Recorded"), ("accepted", "Accepted"),
                                                      ("declined", "Declined")], default="recorded")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
