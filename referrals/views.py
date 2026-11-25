from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from accounts.models import RepresentativeProfile
from .models import Referral


def representative(user):
    if not user.groups.filter(name="Representative").exists():
        raise PermissionDenied
    return get_object_or_404(RepresentativeProfile, user=user, is_active=True)


@login_required
def dashboard(request):
    profile = representative(request.user)
    rows = Referral.objects.filter(representative=profile).select_related("referred_doctor")
    return render(request, "referrals/home.html", {"profile": profile, "page": Paginator(rows, 30).get_page(request.GET.get("page"))})
