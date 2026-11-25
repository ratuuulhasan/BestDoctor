from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Notification, NotificationPreference


@login_required
def inbox(request):
    pref, _ = NotificationPreference.objects.get_or_create(user=request.user)
    if request.method == "POST":
        pref.in_app_enabled = request.POST.get("in_app_enabled") == "on"
        pref.email_enabled = request.POST.get("email_enabled") == "on"
        pref.save(update_fields=["in_app_enabled", "email_enabled"])
        return redirect("notifications")
    rows = Notification.objects.filter(user=request.user)
    return render(request, "notifications/inbox.html", {"pref": pref, "page": Paginator(rows, 30).get_page(request.GET.get("page"))})


@login_required
@require_POST
def mark_read(request, pk):
    item = get_object_or_404(Notification, user=request.user, pk=pk)
    item.is_read = True
    item.save(update_fields=["is_read"])
    return redirect("notifications")
