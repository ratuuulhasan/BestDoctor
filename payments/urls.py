from django.urls import path

from . import api, views

urlpatterns = [
    path("doctor/billing/", views.billing, name="billing"),
    path("billing/invoices/<uuid:number>/", views.detail, name="invoice-detail"),
    path("billing/invoices/<uuid:number>/payment/", views.submit, name="invoice-payment"),
    path("billing/invoices/<uuid:number>/cancel/", views.cancel, name="invoice-cancel"),
    path("review/payments/", views.queue, name="payment-queue"),
    path("review/payments/<int:pk>/decision/", views.decision, name="payment-decision"),
    path("review/payments/<int:pk>/refund/", views.refund, name="payment-refund"),
    path("api/v1/subscription-plans/", api.Plans.as_view(), name="api-plans"),
    path("api/v1/subscriptions/", api.Terms.as_view(), name="api-subscriptions"),
    path("api/v1/invoices/", api.Invoices.as_view(), name="api-invoices"),
    path("api/v1/invoices/<uuid:number>/", api.InvoiceDetail.as_view()),
    path("api/v1/invoices/<uuid:number>/cancel/", api.Cancel.as_view()),
    path("api/v1/invoices/<uuid:number>/payments/", api.Submit.as_view()),
    path("api/v1/payments/", api.Payments.as_view()),
    path("api/v1/payments/<int:pk>/decision/", api.Decision.as_view()),
    path("api/v1/payments/<int:pk>/refund/", api.RecordRefund.as_view()),
]
