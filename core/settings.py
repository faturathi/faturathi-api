"""
Django settings for core project (Faturathi demo backend).
"""

from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from decouple import AutoConfig
from corsheaders.defaults import default_headers, default_methods
import os

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
config = AutoConfig(search_path=BASE_DIR)

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-change-me-for-demo-only")
DEBUG = os.getenv("DEBUG", "True").lower() in {"1", "true", "yes"}
# Host/origin policy is intentionally hardcoded for this demo/UAT deployment.
# Django does not accept CSRF_TRUSTED_ORIGINS=["*"], so universal CSRF Origin
# acceptance is implemented by TrustAllOriginsCsrfViewMiddleware below.
CSRF_TRUST_ALL_ORIGINS = True


def env_list(name: str, default: str = "") -> list[str]:
    return [value.strip() for value in os.getenv(name, default).split(",") if value.strip()]


ALLOWED_HOSTS = ["*"]

# faturathi-ui's server.ts contract uses no-trailing-slash paths (e.g. POST /api/invoices).
# APPEND_SLASH's redirect turns a POST into a GET on a slash mismatch, so every /api/ path
# in this project is deliberately defined without a trailing slash and this stays off.
APPEND_SLASH = False

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "drf_spectacular",
    "drf_spectacular_sidecar",

    "apps.user",
    "apps.company",
    "apps.config",
    "apps.documents",
    "apps.peppol",
    "apps.reports",
    "apps.utils",
]

AUTH_USER_MODEL = "user.User"

MIDDLEWARE = [
    # Must be first so CORS headers are added even to redirects and errors.
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "fathurathi"),
        "USER": os.getenv("DB_USER", "fathurathi"),
        "PASSWORD": os.getenv("DB_PASSWORD", "fathurathi"),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Muscat"
USE_I18N = True
USE_TZ = True

# Maximum request/file upload size. Nginx or a load balancer must allow at
# least the same size (the EC2 deployment guide currently uses 50 MB).
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "30"))
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024

STATIC_ROOT = BASE_DIR / "staticfiles"

# Elastic Beanstalk instances are replaceable, so static assets and uploaded files are stored in
# S3. Point AWS_CLOUDFRONT_DOMAIN at the distribution hostname to serve them through CloudFront.
AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME", default="").strip()
AWS_S3_REGION_NAME = config(
    "AWS_S3_REGION_NAME", default=config("AWS_REGION", default="")
).strip() or None
AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID", default="").strip() or None
AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY", default="").strip() or None
AWS_SESSION_TOKEN = config("AWS_SESSION_TOKEN", default="").strip() or None
AWS_S3_ENDPOINT_URL = config("AWS_S3_ENDPOINT_URL", default="").strip() or None
AWS_CLOUDFRONT_DOMAIN = config("AWS_CLOUDFRONT_DOMAIN", default="").strip().removeprefix("https://").rstrip("/")
# Do not set a direct S3 hostname as custom_domain. With a private bucket that
# would generate unsigned URLs and produce the 403 errors seen in Django Admin.
# Without CloudFront, django-storages generates temporary signed S3 URLs.
AWS_S3_CUSTOM_DOMAIN = AWS_CLOUDFRONT_DOMAIN or None
AWS_DEFAULT_ACL = None
AWS_S3_SIGNATURE_VERSION = "s3v4"
AWS_S3_ADDRESSING_STYLE = config("AWS_S3_ADDRESSING_STYLE", default="virtual")
AWS_S3_FILE_OVERWRITE = False
AWS_QUERYSTRING_AUTH = not bool(AWS_CLOUDFRONT_DOMAIN)
AWS_QUERYSTRING_EXPIRE = config("AWS_QUERYSTRING_EXPIRE", default=3600, cast=int)

if AWS_STORAGE_BUCKET_NAME:
    STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/static/" if AWS_S3_CUSTOM_DOMAIN else "/static/"
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/media/" if AWS_S3_CUSTOM_DOMAIN else "/media/"
    common_s3_options = {
        "bucket_name": AWS_STORAGE_BUCKET_NAME,
        "region_name": AWS_S3_REGION_NAME,
        "endpoint_url": AWS_S3_ENDPOINT_URL,
        "custom_domain": AWS_S3_CUSTOM_DOMAIN,
        "default_acl": None,
        "querystring_auth": AWS_QUERYSTRING_AUTH,
        "querystring_expire": AWS_QUERYSTRING_EXPIRE,
    }
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                **common_s3_options,
                "location": "media",
                "file_overwrite": False,
            },
        },
        "staticfiles": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                **common_s3_options,
                "location": "static",
                "file_overwrite": True,
                "object_parameters": {"CacheControl": "max-age=31536000, immutable"},
            },
        },
    }
else:
    STATIC_URL = "/static/"
    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.config.authentication.ApiKeyAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "apps.utils.permissions.ResolveActiveCompany",
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.utils.pagination.DefaultPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.utils.exceptions.faturathi_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Faturathi SaaS e-Invoicing API",
    "DESCRIPTION": "Tenant-isolated Oman PINT-OM billing, document ingestion, reporting and Peppol lifecycle API.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api(/v1)?",
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayOperationId": True,
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=8),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOWED_ORIGINS = []
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = list(default_headers) + [
    "x-api-key",
    "x-company-id",
    "x-business-group-id",
    "x-requested-with",
]
CORS_ALLOW_METHODS = list(default_methods)
CORS_EXPOSE_HEADERS = ["*"]
CORS_PREFLIGHT_MAX_AGE = 86400

# CSRF middleware is intentionally disabled for this demo prototype. DRF uses
# JWT/API-key authentication, not cookie-backed SessionAuthentication.
CSRF_TRUSTED_ORIGINS = []

# Elastic Beanstalk terminates TLS at its load balancer and forwards the original scheme.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = False
X_FRAME_OPTIONS = "ALLOWALL"

# Demo-only OTA/UUIDv5 namespace and simulated MFA OTP (matches faturathi-ui LoginPage.tsx)
OTA_NAMESPACE = "e0bc4ac8-b025-46e5-a76d-0c893fc3027e"
DEMO_MFA_OTP = "582910"
ALLOW_SEED_RESET = os.getenv("ALLOW_SEED_RESET", str(DEBUG)).lower() in {"1", "true", "yes"}
