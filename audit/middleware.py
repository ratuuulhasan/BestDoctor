from django.db import connection, transaction

from .models import ActivityLog


class ActivityMiddleware:
    public_routes = {"home", "public-doctors", "published-doctor", "public-hospital", "public-specialty",
                     "public-district", "public-division", "public-doctor-api"}
    sensitive_reads = {"verification-document", "verification-api-document", "invoice-detail", "report-export"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            with transaction.atomic():
                if request.user.is_authenticated:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT set_config('best_doctor.actor', %s, true)", [str(request.user.pk)])
                response = self.get_response(request)
                if response.status_code >= 500:
                    transaction.set_rollback(True)
                return response
        response = self.get_response(request)
        match = request.resolver_match
        if request.method == "GET" and response.status_code == 200 and match:
            route = match.url_name
            if route in self.public_routes or route in self.sensitive_reads:
                actor = request.user.pk if route in self.sensitive_reads else None
                ActivityLog.objects.create(user_id=actor, route=route)
        return response
