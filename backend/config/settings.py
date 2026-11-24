"""
Django settings for the Fingerprint Access Control backend.

Every deployment-specific value is read from environment variables (loaded
from backend/.env in development). PostgreSQL is the only supported database.
"""

from datetime import timedelta
from pathlib import Path
import os
import re
from urllib.parse import urlparse

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load backend/.env (if present). Existing environment variables win.
load_dotenv(BASE_DIR / ".env")


def env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise ImproperlyConfigured(f"Missing required environment variable: {name}")
    return value


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

# Canonical deployment URLs. A leftover localhost value on Render would produce
# reset links and email media URLs that only work on the developer's machine,
# so production falls back to the known deployed services instead.
PRODUCTION_FRONTEND_URL = env(
    "PRODUCTION_FRONTEND_URL", "https://fingerprintt.vercel.app"
).rstrip("/")
PRODUCTION_BACKEND_URL = env(
    "PRODUCTION_BACKEND_URL", "https://fingerprint-backend-7032.onrender.com"
).rstrip("/")


def _public_url(name: str, local_default: str, production_default: str) -> str:
    value = env(name, local_default).rstrip("/")
    if not DEBUG and re.match(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$", value):
        return production_default
    return value


PUBLIC_BASE_URL = _public_url(
    "PUBLIC_BASE_URL", "http://localhost:8000", PRODUCTION_BACKEND_URL
)
FRONTEND_URL = _public_url(
    "FRONTEND_URL", "http://localhost:5173", PRODUCTION_FRONTEND_URL
)

# WebSocket origin checks compare scheme + host. Trust the frontend host for
# HTTP Host validation as well, so the Vercel dashboard can reach Django.
_frontend_host = urlparse(FRONTEND_URL).hostname
if _frontend_host and _frontend_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_frontend_host)

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "corsheaders",
    "rest_framework",
    "channels",
    # Local apps
    "accounts",
    "members",
    "devices",
    "logs",
    "notifications",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",          # serve static files in prod
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Database - PostgreSQL only
# ---------------------------------------------------------------------------
DATABASES = {
    "default": dj_database_url.config(
        default=(
            f"postgres://{env('DB_USER', 'postgres')}:{env('DB_PASSWORD', '')}"
            f"@{env('DB_HOST', 'localhost')}:{env('DB_PORT', '5432')}"
            f"/{env('DB_NAME', 'fingerprint_db')}"
        ),
        conn_max_age=int(env("DB_CONN_MAX_AGE", "60")),
    )
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", "Africa/Kigali")
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & media
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------------------
# Media storage - Cloudinary when configured, local disk otherwise
# ---------------------------------------------------------------------------
# Render's filesystem is ephemeral, so member photos must live in an external
# CDN. Set CLOUDINARY_URL=cloudinary://api_key:api_secret@cloud_name (in .env
# and on Render) and every Member.photo is uploaded to Cloudinary and served
# from its CDN instantly in the dashboard, emails and WebSocket payloads.
# Locally the local filesystem is used when the variable is empty.
CLOUDINARY_URL = env("CLOUDINARY_URL", "").strip()

if CLOUDINARY_URL:
    import cloudinary
    from urllib.parse import unquote, urlparse

    _cloudinary = urlparse(CLOUDINARY_URL)
    cloudinary.config(
        cloud_name=_cloudinary.hostname,
        api_key=unquote(_cloudinary.username or ""),
        api_secret=unquote(_cloudinary.password or ""),
        secure=True,
    )
    del _cloudinary  # only needed for configuration

    STORAGES = {
        "default": {"BACKEND": "config.storages.CloudinaryMediaStorage"},
        "staticfiles": {"BACKEND": STATICFILES_STORAGE},
    }

DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "config.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 20,
    "DATETIME_FORMAT": "iso-8601",
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        *(
            ("rest_framework.renderers.BrowsableAPIRenderer",)
            if DEBUG
            else ()
        ),
    ),
    "EXCEPTION_HANDLER": "config.exceptions.api_exception_handler",
    # Scoped limits keep the public password-reset endpoints from being used to
    # spam the owner's inbox or to brute-force reset tokens.
    "DEFAULT_THROTTLE_RATES": {
        "password_reset": env("PASSWORD_RESET_REQUEST_RATE", "5/hour"),
        "password_reset_confirm": env("PASSWORD_RESET_CONFIRM_RATE", "10/hour"),
        "register": env("REGISTER_RATE", "5/hour"),
    },
}

# Password reset links stay valid for one hour by default. Tokens are also
# single-use: Django invalidates them as soon as the password changes.
PASSWORD_RESET_TIMEOUT = int(env("PASSWORD_RESET_TIMEOUT_SECONDS", "3600"))

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(env("JWT_ACCESS_MINUTES", "60"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(env("JWT_REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "SIGNING_KEY": SECRET_KEY,
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# ---------------------------------------------------------------------------
# Django Channels
# ---------------------------------------------------------------------------
REDIS_URL = env("REDIS_URL", "").strip()

if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }

# ---------------------------------------------------------------------------
# CORS / CSRF
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
)
CORS_ALLOW_CREDENTIALS = False
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-device-api-key",
]

# Added your Render backend URL to the default trusted origins
CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS", 
    "http://localhost:5173,http://127.0.0.1:5173,https://fingerprint-backend-7032.onrender.com"
)

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
# Brevo (Sendinblue) SMTP relay is the production transport - it is not blocked
# on Render and delivers straight to the owner's inbox:
#     EMAIL_HOST=smtp-relay.brevo.com
#     EMAIL_PORT=587
#     EMAIL_USE_TLS=True
#     EMAIL_HOST_USER=<your Brevo login email or SMTP key id>
#     EMAIL_HOST_PASSWORD=<your Brevo SMTP key>
# DEFAULT_FROM_EMAIL must be a sender verified in the Brevo dashboard.
# Development keeps the console backend when EMAIL_BACKEND is not set.
# Brevo (v3) API key. When present the notifications.brevo_api backend sends a
# signed HTTPS POST instead of an SMTP session - the most reliable transport on
# Render. Obtain it at https://app.brevo.com/settings/keys/api
def _clean_secret(name: str, default: str = "") -> str:
    """Read a secret while removing copy/paste damage.

    Render environment values are often pasted with surrounding quotes, a
    trailing newline, a BOM or stray spaces. All of these produce the same
    misleading ``401 Key not found`` response from Brevo, so normalise them.
    """
    raw = env(name, default) or ""
    raw = raw.replace("\ufeff", "").replace("\u200b", "")
    raw = "".join(raw.split())
    return raw.strip('"').strip("'")


BREVO_API_KEY = _clean_secret("BREVO_API_KEY")

# A deployment that has a Brevo key must never silently fall back to the
# console backend (which prints emails to the server log instead of sending
# them). The Brevo API backend therefore becomes the default whenever a key is
# configured; an explicit EMAIL_BACKEND always wins.
_DEFAULT_EMAIL_BACKEND = (
    "notifications.brevo_api.BrevoAPIEmailBackend"
    if BREVO_API_KEY
    else "django.core.mail.backends.console.EmailBackend"
)
EMAIL_BACKEND = (
    env("EMAIL_BACKEND", "").strip() or _DEFAULT_EMAIL_BACKEND
)
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT = int(env("EMAIL_TIMEOUT", "15"))
DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL", "Fingerprint Access <noreply@example.com>"
)
OWNER_EMAIL = env("OWNER_EMAIL", "")
# A deployment that only sets OWNER_EMAIL still gets a usable, verified sender
# instead of the inert example.com placeholder.
if (
    not DEFAULT_FROM_EMAIL
    or "example.com" in DEFAULT_FROM_EMAIL.lower()
) and OWNER_EMAIL:
    DEFAULT_FROM_EMAIL = f"Fingerprint Access <{OWNER_EMAIL}>"
# Only events at most this old trigger an owner alert. Importing or back-filling
# history must never flood the inbox; live device events are always within it.
EMAIL_MAX_EVENT_AGE_MINUTES = int(env("EMAIL_MAX_EVENT_AGE_MINUTES", "15"))

# ---------------------------------------------------------------------------
# Project-specific security / device settings
# ---------------------------------------------------------------------------
DEVICE_API_KEY = env("DEVICE_API_KEY", "").strip()
if not DEVICE_API_KEY:
    raise ImproperlyConfigured(
        "DEVICE_API_KEY must be set. Generate one with: "
        "python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )

TEMPLATE_ENCRYPTION_KEY = env("TEMPLATE_ENCRYPTION_KEY", "").strip()
if not TEMPLATE_ENCRYPTION_KEY:
    raise ImproperlyConfigured(
        "TEMPLATE_ENCRYPTION_KEY must be set. Generate one with: "
        "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    )

DEVICE_OFFLINE_AFTER_SECONDS = int(env("DEVICE_OFFLINE_AFTER_SECONDS", "120"))
MAX_TEMPLATE_BYTES = int(env("MAX_TEMPLATE_BYTES", str(64 * 1024)))
MAX_PHOTO_BYTES = int(env("MAX_PHOTO_BYTES", str(5 * 1024 * 1024)))

# ---------------------------------------------------------------------------
# Production hardening (enable behind HTTPS)
# ---------------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# 🔥 ADDED THIS: Tells Django to trust Render's proxy for HTTPS
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
    SESSION_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", False)
    CSRF_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", False)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        }
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "members": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "devices": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "logs": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "notifications": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}