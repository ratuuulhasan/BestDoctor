from django.db import connection
from rest_framework.authentication import TokenAuthentication


class AuditedTokenAuthentication(TokenAuthentication):
    def authenticate(self, request):
        identity = super().authenticate(request)
        if identity and connection.in_atomic_block and request.method in ("POST", "PATCH", "PUT", "DELETE"):
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('best_doctor.actor', %s, true)", [str(identity[0].pk)])
        return identity
