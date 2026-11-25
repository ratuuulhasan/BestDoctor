from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from api.views import Identity, Login, RevokeToken
from core.views import health
from analytics import views as reporting

admin.site.site_header = "Best Doctor administration"
admin.site.site_title = "Best Doctor"
admin.site.index_template = "verification/admin_index.html"
urlpatterns = [
    path("operations/", reporting.dashboard, name="operations"),
    path("operations/reports/<int:pk>/", reporting.export, name="report-export"),
    path("", include("frontend.community_urls")),
    path("api/v1/", include("api.community")),
    path("", include("payments.urls")),
    path("", include("search.urls")),
    path("", include("verification.urls")),
    path("", include("frontend.urls")),
    path("api/v1/", include("api.directory")),
    path("health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("api/v1/auth/token/", Login.as_view(), name="token"),
    path("api/v1/auth/revoke/", RevokeToken.as_view(), name="revoke"),
    path("api/v1/me/", Identity.as_view(), name="identity"),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
