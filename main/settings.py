# type: ignore[reportAttributeAccessIssue]
import socket
import sys
import typing
from pathlib import Path
from urllib.parse import ParseResult
from urllib.parse import urlparse as _urlparse

import environ

from main.logging import log_render_extra_context
from main.sentry import SentryConfig

# Build paths inside the project like this: BASE_DIR / 'subdir'.
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
    # Django
    DEBUG=(bool, False),
    ENABLE_DEBUG_TOOLBAR=(bool, False),
    DJANGO_SECRET_KEY=str,
    ADDITIONAL_ALLOWED_HOSTS=(list, []),  # Eg: api.example.org
    APP_ENVIRONMENT=str,  # DEV, STAGE, PROD
    APP_RELEASE=(str, None),
    APP_TYPE=str,  # WEB, WORKER, WORKER-BEAT
    APP_LOG_LEVEL=(str, "INFO"),
    MEDIA_STORAGE_DOMAIN=(str, None),
    SESSION_COOKIE_DOMAIN=str,  # .example.com
    CSRF_COOKIE_DOMAIN=str,  # .example.com
    ADDITIONAL_TRUSTED_ORIGINS=(list, []),
    # NOTE: Changing TIME_ZONE will break celery periodic tasks https://django-celery-beat.readthedocs.io/en/latest/#important-warning-about-time-zones
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
    TEMP_DIR=(str, "/tmp/"),  # noqa: S108
    # -- S3 storage
    AWS_S3_ENABLED=(bool, False),
    AWS_S3_ENDPOINT_URL=(str, None),
    AWS_S3_ACCESS_KEY_ID=str,
    AWS_S3_SECRET_ACCESS_KEY=str,
    AWS_S3_REGION_NAME=str,
    AWS_S3_MEDIA_BUCKET_NAME=str,
    AWS_S3_STATIC_BUCKET_NAME=str,
    # -- Filesystem (default) XXX: Don't use in production?
    MEDIA_ROOT=(str, BASE_DIR / ".data/media"),
    STATIC_ROOT=(str, BASE_DIR / ".data/static"),
    INTERNAL_ROOT=(str, BASE_DIR / ".data/internal"),
    # Celery
    CELERY_REDIS_URL=str,  # redis://redis:6379/0
    # Cache
    CACHE_REDIS_URL=str,  # redis://redis:6379/1
    TEST_CACHE_REDIS_URL=(str, None),
    # Sentry
    SENTRY_ENABLED=(bool, False),
    SENTRY_DEBUG=(bool, False),
    SENTRY_DSN=(str, None),
    SENTRY_MONITOR_CELERY_BEAT_TASKS=(bool, True),
    SENTRY_TRACES_SAMPLE_RATE=(float, 0.2),
    SENTRY_PROFILE_SAMPLE_RATE=(float, 0.2),
    # Pytest
    PYTEST_XDIST_WORKER=(str, None),
    # Test
    ENABLE_DANGER_MODE=(bool, False),
    # Email
    EMAIL_BACKEND=(str, "django.core.mail.backends.console.EmailBackend"),
    DEFAULT_FROM_EMAIL=(str, "mrcs-drm@example.com"),
    EMAIL_API_URL=(str, None),
    EMAIL_API_KEY=(str, None),
    EMAIL_API_TIMEOUT=(int, None),
    # Dev smtp
    EMAIL_HOST=(str, None),
    EMAIL_PORT=(str, None),
    EMAIL_HOST_USER=(str, None),
    EMAIL_HOST_PASSWORD=(str, None),
    EMAIL_USE_TLS=(bool, False),
    # JBA
    JBA_SFTP_ENABLED=(bool, False),
    JBA_SFTP_USERNAME=(str, "mrcs"),
    JBA_SFTP_PASSWORD=str,
    JBA_SFTP_URL=str,
    JBA_SFTP_PORT=(int, 22),
    # ARC
    ARC_S3_BUCKET=(str, "jbarisk-analytics"),
    ARC_S3_PREFIX=(str, "malawi/2026"),
    AWS_ACCESS_KEY_ID=str,
    AWS_SECRET_ACCESS_KEY=str,
    AWS_REGION=(str, "eu-west-2"),
)

ENABLE_DANGER_MODE = env("ENABLE_DANGER_MODE")

# GIT_HELPER = GitHelper(BASE_DIR)

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

APP_LOG_LEVEL = env("APP_LOG_LEVEL")
APP_DOMAIN = urlparse(env("APP_DOMAIN"))
MEDIA_STORAGE_DOMAIN = urlparse(env("MEDIA_STORAGE_DOMAIN")) or APP_DOMAIN
APP_ENVIRONMENT = env("APP_ENVIRONMENT").upper()
APP_TYPE = env("APP_TYPE").upper()
SECRET_KEY = env("DJANGO_SECRET_KEY")
APP_RELEASE = env("APP_RELEASE")
DEBUG = env("DEBUG")

ALLOWED_HOSTS = [
    APP_DOMAIN.hostname,
    *env("ADDITIONAL_ALLOWED_HOSTS"),
]

# JBA
JBA_SFTP_ENABLED = env("JBA_SFTP_ENABLED")
if JBA_SFTP_ENABLED:
    JBA_SFTP_USERNAME = env("JBA_SFTP_USERNAME")
    JBA_SFTP_PASSWORD = env("JBA_SFTP_PASSWORD")
    JBA_SFTP_URL = env("JBA_SFTP_URL")
    JBA_SFTP_PORT = env("JBA_SFTP_PORT")

ARC_PIPELINE = {
    "S3_BUCKET": env("ARC_S3_BUCKET"),
    "S3_PREFIX": env("ARC_S3_PREFIX"),
    "AWS_ACCESS_KEY_ID": env("ARC_AWS_ACCESS_KEY_ID"),
    "AWS_SECRET_ACCESS_KEY": env("ARC_AWS_SECRET_ACCESS_KEY"),
    "AWS_REGION": env("ARC_AWS_REGION"),
}

# See if we are inside a test environment (pytest)
IS_TESTING = (
    any(
        [
            arg in sys.argv
            for arg in [
                "test",
                "pytest",
                "/usr/local/bin/pytest",
                "py.test",
                "/usr/local/bin/py.test",
                "/usr/local/lib/python3.6/dist-packages/py/test.py",
            ]
            # Provided by pytest-xdist
        ],
    )
    or env("PYTEST_XDIST_WORKER") is not None
)

# Application definition

INSTALLED_APPS = [
    # Core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "django.contrib.postgres",
    # External
    "strawberry_django",
    "corsheaders",
    "djangoql",
    "rest_framework",
    "drf_spectacular",
    # - Health-check
    "health_check",  # required
    # Internal
    "apps.common",
    "apps.users",
    "apps.admin_areas",
    "apps.pipeline",
    "apps.notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
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

# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": env("POSTGRES_DB"),
        "USER": env("POSTGRES_USER"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST"),
        "PORT": env("POSTGRES_PORT"),
    },
}


AUTH_USER_MODEL = "users.User"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = env("TIME_ZONE")

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

TEMP_DIR = Path(env("TEMP_DIR"))
MEDIA_URL = env("MEDIA_URL")
STATIC_URL = env("STATIC_URL")

STORAGE_OVERWRITE_KEY = "default-overwrite"
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
                "location": "media/",
                "querystring_auth": False,
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

    STORAGES[STORAGE_OVERWRITE_KEY] = {
        **STORAGES["default"],
        "OPTIONS": {
            **STORAGES["default"]["OPTIONS"],
            "file_overwrite": True,
        },
    }

else:
    # Filesystem
    MEDIA_ROOT = env("MEDIA_ROOT")
    STATIC_ROOT = env("STATIC_ROOT")

    # Django's default https://docs.djangoproject.com/en/5.2/ref/settings/#storages
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

    STORAGES[STORAGE_OVERWRITE_KEY] = {
        **STORAGES["default"],
        "OPTIONS": {
            "allow_overwrite": True,
        },
    }

INTERNAL_ROOT = env("INTERNAL_ROOT")

assert STORAGE_OVERWRITE_KEY in STORAGES, f"{STORAGE_OVERWRITE_KEY} should be defined in STORAGES"

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

# Redis lock
DEFAULT_REDIS_LOCK_EXPIRE = 60 * 10  # Lock expires in 10min (in seconds)

# Cache
CACHE_REDIS_URL = env("CACHE_REDIS_URL")
TEST_CACHE_REDIS_URL = env("TEST_CACHE_REDIS_URL")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": CACHE_REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "djc-",
    },
    "local-memory": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    },
}

# Celery
CELERY_RESULT_BACKEND = CELERY_BROKER_URL = env("CELERY_REDIS_URL")
CELERY_TASK_SOFT_TIME_LIMIT = 30 * 60
CELERY_TASK_TIME_LIMIT = 35 * 60
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = False

# HEALTH-CHECK
REDIS_URL = CACHE_REDIS_URL
HEALTHCHECK_CACHE_KEY = "mrcs_healthcheck_key"

# NOTE: For non-alpha instances, look at 50 as we have other resources like db/media on the same host
# We will need to add additional disk if usages are high on the main disk
HEALTH_CHECK = {
    "DISK_USAGE_MAX": 50,  # percent
}

if "alpha" in APP_ENVIRONMENT.lower():
    HEALTH_CHECK = {
        "DISK_USAGE_MAX": 90,
    }

TRUSTED_ORIGINS = [
    APP_DOMAIN.geturl(),
    *env("ADDITIONAL_TRUSTED_ORIGINS"),
]
# Security Header configuration

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
    SECURE_HSTS_SECONDS = 30  # TODO(thenav56): Increase this slowly
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

CSRF_TRUSTED_ORIGINS = TRUSTED_ORIGINS

# -- https://docs.djangoproject.com/en/3.2/ref/settings/#std:setting-SESSION_COOKIE_DOMAIN
SESSION_COOKIE_DOMAIN = env("SESSION_COOKIE_DOMAIN")
# https://docs.djangoproject.com/en/3.2/ref/settings/#csrf-cookie-domain
CSRF_COOKIE_DOMAIN = env("CSRF_COOKIE_DOMAIN")


# CORS

CORS_ALLOWED_ORIGINS = TRUSTED_ORIGINS
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True  # file:// origin (null) needs this for dev tools
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
    "range",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    # Required by sentry
    "sentry-trace",
    "baggage",
)

# Expose range-request response headers so browser workers can read them (needed
# by maplibre-cog-protocol fetching COG tiles from within a worker thread).
CORS_EXPOSE_HEADERS = ["Accept-Ranges", "Content-Encoding", "Content-Length", "Content-Range"]


# Sentry Config
SENTRY_ENABLED = env("SENTRY_ENABLED")

if SENTRY_ENABLED:
    SENTRY_CONFIG = SentryConfig(
        dsn=env("SENTRY_DSN"),
        debug=env("SENTRY_DEBUG"),
        app_type=APP_TYPE,
        release=APP_RELEASE,
        environment=APP_ENVIRONMENT,
        send_default_pii=True,
        traces_sample_rate=env("SENTRY_TRACES_SAMPLE_RATE"),
        profiles_sample_rate=env("SENTRY_PROFILE_SAMPLE_RATE"),
        # Custom configs
        tags={"site": APP_DOMAIN.geturl()},
        monitor_celery_beat_tasks=env("SENTRY_MONITOR_CELERY_BEAT_TASKS"),
    )
    SENTRY_CONFIG.init_sentry()

# Strawberry
STRAWBERRY_DJANGO = {
    "FIELD_DESCRIPTION_FROM_HELP_TEXT": True,
    "TYPE_DESCRIPTION_FROM_MODEL_DOCSTRING": True,
    "MUTATIONS_DEFAULT_HANDLE_ERRORS": True,
    "PAGINATION_DEFAULT_LIMIT": 20,
    "DEFAULT_PK_FIELD_NAME": "id",
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "render_extra_context": {
            "()": "django.utils.log.CallbackFilter",
            "callback": log_render_extra_context,
        },
    },
    "formatters": {
        "simple": {
            "format": ("%(asctime)s: - %(customThreadName)s/%(levelname)s - %(name)s - %(message)s %(context)s"),
            "datefmt": "%Y-%m-%dT%H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "filters": ["render_extra_context"],
        },
    },
    "loggers": {
        **{
            app: {
                "level": env("APP_LOG_LEVEL"),
                "handlers": ["console"],
                "propagate": False,
            }
            for app in ["apps", "main", "utils", "celery", "django"]
        },
    },
    "root": {
        "level": env("APP_LOG_LEVEL"),
        "handlers": ["console"],
    },
}

if DEBUG:
    LOGGING = {
        **LOGGING,
        "formatters": {
            **LOGGING["formatters"],
            "colored_verbose": {
                "()": "colorlog.ColoredFormatter",
                "format": (
                    "%(log_color)s%(asctime)s: %(customThreadName)s - %(levelname)-s%(red)s %(name)-s%(reset)s "
                    "%(blue)s%(message)s %(context)s"
                ),
            },
        },
        "handlers": {
            **LOGGING["handlers"],
            "colored_console": {
                "class": "logging.StreamHandler",
                "formatter": "colored_verbose",
                "filters": ["render_extra_context"],
            },
        },
        "loggers": {
            **{
                key: {
                    **logger,
                    "handlers": ["colored_console"],
                }
                for key, logger in LOGGING["loggers"].items()
            },
        },
        "root": {
            "level": env("APP_LOG_LEVEL"),
            "handlers": ["colored_console"],
        },
    }


# Django toolbar
ENABLE_DEBUG_TOOLBAR = env("ENABLE_DEBUG_TOOLBAR")

if DEBUG:
    MIDDLEWARE.insert(0, "utils.middleware.RangeRequestMiddleware")

if ENABLE_DEBUG_TOOLBAR and not IS_TESTING:
    INSTALLED_APPS.append("debug_toolbar")
    MIDDLEWARE.append("strawberry_django.middlewares.debug_toolbar.DebugToolbarMiddleware")
    INTERNAL_IPS = [
        "127.0.0.1",
        ".".join(socket.gethostbyname(socket.gethostname()).rsplit(".")[:-1]) + ".1",
    ]


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
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_API_URL = env("EMAIL_API_URL")
EMAIL_API_KEY = env("EMAIL_API_KEY")
EMAIL_API_TIMEOUT = env("EMAIL_API_TIMEOUT", default=30)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")
# for smtp Email Backend
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env("EMAIL_PORT")
EMAIL_USE_TLS = env("EMAIL_USE_TLS")
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
