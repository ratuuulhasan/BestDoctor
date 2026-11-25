from django.urls import path

from . import api, views

urlpatterns = [
    path("doctor/verification/", views.workspace, name="verification-home"),
    path("doctor/verification/publication/", views.publication, name="publication"),
    path("review/verification/", views.queue, name="verification-queue"),
    path("verification/<int:pk>/", views.detail, name="verification-detail"),
    path("verification/documents/<int:pk>/", views.download, name="verification-document"),
    path("api/v1/verifications/", api.Attempts.as_view(), name="verification-api"),
    path("api/v1/verifications/<int:pk>/", api.AttemptDetail.as_view(), name="verification-api-detail"),
    path("api/v1/verifications/<int:pk>/decision/", api.Decision.as_view(), name="verification-api-decision"),
    path("api/v1/verifications/documents/<int:pk>/", api.Document.as_view(), name="verification-api-document"),
    path("api/v1/verifications/publication/", api.Publication.as_view(), name="verification-api-publication"),
]
