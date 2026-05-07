# type: ignore[reportAttributeAccessIssue]
import typing
from pathlib import Path
from urllib.parse import ParseResult
from urllib.parse import urlparse as _urlparse

import environ

BASE_DIR = Path(__file__).resolve().parent.parent


@typing.overload
def urlparse(value: None) -> None: ...


@typing.overload
def urlparse(value: str) -> ParseResult: ...


def urlparse(value) -> ParseResult:
    if not value:
        return None
    return _urlparse(value.strip("/"))


env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=str,
    ADDITIONAL_ALLOWED_HOSTS=(list, []),
    APP_ENVIRONMENT=str,
    APP_TYPE=str,
    APP_RELEASE=(str, None),
    # Domain configs
    APP_DOMAIN=str,
    FRONTEND_DOMAIN=str,
    SESSION_COOKIE_DOMAIN=str,
    CSRF_COOKIE_DOMAIN=str,
    ADDITIONAL_TRUSTED_ORIGINS=(list, []),
    TIME_ZONE=(str, "UTC"),
    # Database
    POSTGRES_DB=str,
    POSTGRES_USER=str,
    POSTGRES_PASSWORD=str,
    POSTGRES_HOST=str,
    POSTGRES_PORT=(int, 5432),
    # Storage
    MEDIA_URL=(str, "media/"),
    STATIC_URL=(str, "static/"),
    TEMP_DIR=(str, "/temp/"),
    # -- S3 storage
    AWS_S3_ENABLED=(bool, False),
    AWS_S3_ENDPOINT_URL=(str, None),
    AWS_S3_ACCESS_KEY_ID=str,
    AWS_S3_SECRET_ACCESS_KEY=str,
    AWS_S3_REGION_NAME=str,
    AWS_S3_MEDIA_BUCKET_NAME=str,
    AWS_S3_STATIC_BUCKET_NAME=str,
    # -- Filesystem (default)
    MEDIA_ROOT=(str, BASE_DIR / "data/media"),
    STATIC_ROOT=(str, BASE_DIR / "data/static"),
    # Email
    EMAIL_BACKEND=(str, "django.core.mail.backends.console.EmailBackend"),
    DEFAULT_FROM_EMAIL=(str),
    EMAIL_API_URL=(str, None),
    EMAIL_API_KEY=(str, None),
    EMAIL_API_TIMEOUT=(int, 30),
    # Celery / Redis
    CELERY_REDIS_URL=str,
    CACHE_REDIS_URL=str,
)

APP_DOMAIN = urlparse(env("APP_DOMAIN"))
FRONTEND_DOMAIN = urlparse(env("FRONTEND_DOMAIN"))
APP_ENVIRONMENT = env("APP_ENVIRONMENT").upper()
APP_TYPE = env("APP_TYPE").upper()
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DEBUG")

ALLOWED_HOSTS = [
    APP_DOMAIN.hostname,
    *env("ADDITIONAL_ALLOWED_HOSTS"),
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # Third-party
    "corsheaders",
    "rest_framework",
    "strawberry_django",
    # Health-check
    "health_check",
    # Local apps
    "apps.common",
    "apps.users",
    "apps.admin_areas",
    "apps.pipeline",
    "apps.notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "main.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "main.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB"),
        "USER": env("POSTGRES_USER"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST"),
        "PORT": env("POSTGRES_PORT"),
    },
}

AUTH_USER_MODEL = "users.User"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE")
USE_I18N = True
USE_TZ = True

TEMP_DIR = Path(env("TEMP_DIR"))
MEDIA_URL = env("MEDIA_URL")
STATIC_URL = env("STATIC_URL")

if env("AWS_S3_ENABLED"):
    AWS_S3_CONFIG_OPTIONS = {
        "endpoint_url": env("AWS_S3_ENDPOINT_URL"),
        "access_key": env("AWS_S3_ACCESS_KEY_ID"),
        "secret_key": env("AWS_S3_SECRET_ACCESS_KEY"),
        "region_name": env("AWS_S3_REGION_NAME"),
    }

    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                **AWS_S3_CONFIG_OPTIONS,
                "bucket_name": env("AWS_S3_MEDIA_BUCKET_NAME"),
                "querystring_auth": False,
                "location": "media/",
                "file_overwrite": False,
            },
        },
        "staticfiles": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                **AWS_S3_CONFIG_OPTIONS,
                "bucket_name": env("AWS_S3_STATIC_BUCKET_NAME"),
                "querystring_auth": False,
                "location": "static/",
                "file_overwrite": True,
            },
        },
    }
else:
    MEDIA_ROOT = env("MEDIA_ROOT")
    STATIC_ROOT = env("STATIC_ROOT")

TRUSTED_ORIGINS = [
    APP_DOMAIN.geturl(),
    FRONTEND_DOMAIN.geturl(),
    *env("ADDITIONAL_TRUSTED_ORIGINS"),
]

SESSION_COOKIE_NAME = f"MRCS-{APP_ENVIRONMENT}-SESSIONID"
CSRF_COOKIE_NAME = f"MRCS-{APP_ENVIRONMENT}-CSRFTOKEN"
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
CSP_DEFAULT_SRC = ["'self'"]
SECURE_REFERRER_POLICY = "same-origin"
if APP_DOMAIN.scheme == "https":
    SESSION_COOKIE_NAME = f"__Secure-{SESSION_COOKIE_NAME}"
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SECURE_HSTS_SECONDS = 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    CSRF_TRUSTED_ORIGINS = TRUSTED_ORIGINS

SESSION_COOKIE_DOMAIN = env("SESSION_COOKIE_DOMAIN")
CSRF_COOKIE_DOMAIN = env("CSRF_COOKIE_DOMAIN")

CORS_ALLOWED_ORIGINS = TRUSTED_ORIGINS
CSRF_TRUSTED_ORIGINS = TRUSTED_ORIGINS
CORS_ALLOW_CREDENTIALS = True
CORS_URLS_REGEX = r"(^/media/.*$)|(^/graphql/$)|(^/health-check/$)"
CORS_ALLOW_METHODS = (
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
)
CORS_ALLOW_HEADERS = (
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
)

STRAWBERRY_DJANGO = {
    "FIELD_DESCRIPTION_FROM_HELP_TEXT": True,
    "TYPE_DESCRIPTION_FROM_MODEL_DOCSTRING": True,
    "MUTATIONS_DEFAULT_HANDLE_ERRORS": True,
    "PAGINATION_DEFAULT_LIMIT": 20,
    "DEFAULT_PK_FIELD_NAME": "id",
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework.authentication.SessionAuthentication",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_FILTER_BACKENDS": (
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
}

if DEBUG:
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = (
        *REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"],
        "rest_framework.renderers.BrowsableAPIRenderer",
    )

# Email
EMAIL_BACKEND = env("EMAIL_BACKEND")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")
EMAIL_API_URL = env("EMAIL_API_URL")
EMAIL_API_KEY = env("EMAIL_API_KEY")
EMAIL_API_TIMEOUT = env("EMAIL_API_TIMEOUT")

# Celery
CELERY_REDIS_URL = env("CELERY_REDIS_URL")
CACHE_REDIS_URL = env("CACHE_REDIS_URL")
CELERY_BROKER_URL = CELERY_REDIS_URL
CELERY_RESULT_BACKEND = CELERY_REDIS_URL
