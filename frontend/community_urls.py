from django.urls import path

from cms import views as cms
from cms.models import Page
from notifications import views as notifications
from referrals import views as referrals
from reviews import views as reviews
from support import views as support

urlpatterns = [
    path("patient/register/", reviews.register, name="patient-register"),
    path("patient/dashboard/", reviews.dashboard, name="patient-home"),
    path("doctors/<slug:slug>/review/", reviews.write, name="write-review"),
    path("reviews/<int:pk>/report/", reviews.report, name="report-review"),
    path("support/", support.inbox, name="support-home"),
    path("support/<uuid:number>/", support.detail, name="support-detail"),
    path("notifications/", notifications.inbox, name="notifications"),
    path("notifications/<int:pk>/read/", notifications.mark_read, name="read-notice"),
    path("representative/", referrals.dashboard, name="referrals"),
    path("blog/", cms.blog, name="blog"),
    path("blog/<str:slug>/", cms.article, name="blog-post"),
    path("pages/<str:slug>/", cms.article, {"model": Page}, name="content-page"),
    path("faq/", cms.faq, name="faq"),
    path("contact/", cms.contact, name="contact"),
]
