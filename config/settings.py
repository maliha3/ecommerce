"""
Django settings for the Thread & Co storefront.

Everything environment-specific comes from env vars so the same code runs
locally on SQLite and on Render against Neon Postgres + Cloudinary.
"""
import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes"}


# --------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-in-production")
DEBUG = env_bool("DEBUG", True)

ALLOWED_HOSTS = [h for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h]
if DEBUG:
    ALLOWED_HOSTS += ["localhost", "127.0.0.1", "[::1]"]

# Render injects this; it is the app's public hostname.
RENDER_HOST = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if RENDER_HOST:
    ALLOWED_HOSTS.append(RENDER_HOST)

CSRF_TRUSTED_ORIGINS = [
    f"https://{h}" for h in ALLOWED_HOSTS if h not in {"localhost", "127.0.0.1", "[::1]"}
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "store",
    "cart",
    "orders",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise serves static files straight from the app; no CDN, no S3.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

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
                "store.context_processors.storefront",
                "cart.context_processors.cart",
            ],
        },
    },
]

# --------------------------------------------------------------------------
# Database — Neon Postgres in production, SQLite when DATABASE_URL is unset
# --------------------------------------------------------------------------
# Neon's connection string looks like:
#   postgresql://user:pass@ep-xxx-pooler.region.aws.neon.tech/neondb?sslmode=require
# Use the *pooled* host on a free plan: Render's free dynos open and drop
# connections often, and Neon's pooler absorbs that.

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=True,
        )
    }
elif DEBUG or env_bool("ALLOW_SQLITE_IN_PRODUCTION", False):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    # Falling back to SQLite in production is never what anyone wants: the
    # host's disk is wiped on every deploy, so the shop comes up green but
    # empty and the cause is invisible from the outside. Refuse to boot and
    # say why instead.
    raise ImproperlyConfigured(
        "DATABASE_URL is not set and DEBUG is False.\n"
        "\n"
        "This deployment has no database. Set DATABASE_URL to your Postgres\n"
        "connection string (use the *pooled* host on Neon), then redeploy.\n"
        "\n"
        "On Render: your service -> Environment -> add DATABASE_URL -> and be\n"
        "sure to use the button that rebuilds and deploys, not a plain save.\n"
        "\n"
        "To run on SQLite in production anyway, set\n"
        "ALLOW_SQLITE_IN_PRODUCTION=true (data will not survive a deploy)."
    )

# --------------------------------------------------------------------------
# Static files (WhiteNoise) and media (Cloudinary)
# --------------------------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Cloudinary takes over media uploads as soon as a CLOUDINARY_URL exists, so
# local development needs no account and production needs no code change.
CLOUDINARY_URL = os.environ.get("CLOUDINARY_URL")
USE_CLOUDINARY = bool(CLOUDINARY_URL)

if USE_CLOUDINARY:
    INSTALLED_APPS += ["cloudinary_storage", "cloudinary"]
    MEDIA_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"
    CLOUDINARY_STORAGE = {"PREFIX": os.environ.get("CLOUDINARY_FOLDER", "hellomalaysia")}
else:
    MEDIA_STORAGE = "django.core.files.storage.FileSystemStorage"

STORAGES = {
    "default": {"BACKEND": MEDIA_STORAGE},
    "staticfiles": {
        # Hashed + compressed, served by WhiteNoise with long-lived cache headers.
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

WHITENOISE_MAX_AGE = 31536000  # one year; filenames are hashed
# In development, read files from disk per request instead of indexing
# STATIC_ROOT at startup (which may not exist before collectstatic runs).
WHITENOISE_AUTOREFRESH = DEBUG

# --------------------------------------------------------------------------
# Auth / i18n
# --------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("TIME_ZONE", "Asia/Dhaka")
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

# --------------------------------------------------------------------------
# Storefront settings — the client edits these via env vars, not code
# --------------------------------------------------------------------------

SHOP_NAME = os.environ.get("SHOP_NAME", "Hello Malaysia")
SHOP_TAGLINE = os.environ.get(
    "SHOP_TAGLINE", "Branded bags, shoes and jewellery, brought in from KL."
)
# Prices are in Bangladeshi taka.
CURRENCY_SYMBOL = os.environ.get("CURRENCY_SYMBOL", "৳")

# Shown on the checkout page for manual mobile-wallet transfers.
BKASH_NUMBER = os.environ.get("BKASH_NUMBER", "01700-000000")
NAGAD_NUMBER = os.environ.get("NAGAD_NUMBER", "01800-000000")
SHOP_PHONE = os.environ.get("SHOP_PHONE", "01700-000000")

DELIVERY_CHARGE_DHAKA = int(os.environ.get("DELIVERY_CHARGE_DHAKA", "60"))
DELIVERY_CHARGE_OUTSIDE = int(os.environ.get("DELIVERY_CHARGE_OUTSIDE", "120"))

CART_SESSION_ID = "cart"

# --------------------------------------------------------------------------
# Production hardening (no-ops while DEBUG is on)
# --------------------------------------------------------------------------

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 2592000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    X_FRAME_OPTIONS = "DENY"
