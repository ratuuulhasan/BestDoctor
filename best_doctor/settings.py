import os
from pathlib import Path

from dotenv import load_dotenv
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "drf_spectacular",
    "accounts.apps.AccountsConfig",
    "core",
    "api",
    "locations",
    "specialties",
    "doctors",
    "hospitals",
    "chambers",
    "frontend",
    "verification",
    "subscriptions",
    "payments",
    "search",
    "reviews",
    "cms",
    "support",
    "notifications",
    "referrals",
    "analytics",
    "audit",
    "appointments",
    "assistant",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "audit.middleware.ActivityMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "best_doctor.urls"
WSGI_APPLICATION = "best_doctor.wsgi.application"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": os.getenv("POSTGRES_DB", "best_doctor"),
    "USER": os.getenv("POSTGRES_USER", "best_doctor"),
    "PASSWORD": os.environ["POSTGRES_PASSWORD"],
    "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
    "PORT": os.getenv("POSTGRES_PORT", "55432"),
}}
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": f"django.contrib.auth.password_validation.{validator}"}
    for validator in (
        "UserAttributeSimilarityValidator",
        "MinimumLengthValidator",
        "CommonPasswordValidator",
        "NumericPasswordValidator",
    )
]
LANGUAGE_CODE = "en"
TIME_ZONE = "Asia/Dhaka"
USE_TZ = True
STATIC_URL = "static/"
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "portal"
LOGOUT_REDIRECT_URL = "login"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
EMAIL_BACKEND = os.getenv("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "127.0.0.1")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "1025"))
EMAIL_TIMEOUT = 10
CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "deliver-notifications": {"task": "notifications.tasks.deliver_email", "schedule": 30.0},
    "expiry-reminders": {"task": "notifications.tasks.expiry_reminders", "schedule": crontab(minute=5)},
    "daily-report": {"task": "analytics.tasks.generate_report", "schedule": crontab(hour=0, minute=10)},
}
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "audit.authentication.AuditedTokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_RATES": {"login": "10/min"},
}
SPECTACULAR_SETTINGS = {
    "ENUM_NAME_OVERRIDES": {
        "RegistrationDecision": ["approved", "rejected"],
        "SettlementDecision": ["verified", "rejected"],
        "ReviewStatus": "reviews.models.Review.Status",
        "VerificationStatus": "verification.models.Status",
        "PaymentStatus": "payments.models.Payment.State",
        "InvoiceStatus": "payments.models.Invoice.State",
        "TermStatus": "subscriptions.models.Subscription.State",
    },
    "TITLE": "Best Doctor API", "VERSION": "1.0", "SERVE_INCLUDE_SCHEMA": False,
}
