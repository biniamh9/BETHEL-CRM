"""Settings for the Bethel Eritrean Alliance Church CRM.

All secrets come from environment variables (see .env.example).
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

try:  # load .env in local development
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


# Vercel sets VERCEL=1 (and VERCEL_ENV, VERCEL_URL, ...) both while building and at runtime.
ON_VERCEL = bool(os.environ.get("VERCEL"))

DEBUG = env_bool("DEBUG", not ON_VERCEL)  # never debug on Vercel unless DEBUG=True is set on purpose
SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-only-insecure-key-change-me"
if ON_VERCEL and os.environ.get("VERCEL_ENV") == "production" and not os.environ.get("SECRET_KEY"):
    import warnings

    warnings.warn("SECRET_KEY is not set in Vercel. Add it under Project Settings -> Environment Variables.")


def env_list(name, default=""):
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
if ON_VERCEL:
    # every *.vercel.app address (production, previews) plus any custom domain from VERCEL_* vars
    ALLOWED_HOSTS += [".vercel.app"]
    CSRF_TRUSTED_ORIGINS += ["https://*.vercel.app"]
    for var in ("VERCEL_URL", "VERCEL_BRANCH_URL", "VERCEL_PROJECT_PRODUCTION_URL"):
        host = os.environ.get(var)
        if host:
            ALLOWED_HOSTS.append(host)
            CSRF_TRUSTED_ORIGINS.append(f"https://{host}")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "accounts",
    "ministries",
    "fundraising",
    "events",
    "resources",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.DatabaseConfigCheck",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

try:  # serve static files in production without a separate server
    import whitenoise  # noqa: F401

    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "core.storage.FallbackStaticFilesStorage"},
    }
except ImportError:
    pass

import sys  # noqa: E402

if "test" in sys.argv[1:2]:  # tests don't run collectstatic, so skip the hashed-filename manifest
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }

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
                "core.context_processors.church",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database: SQLite locally; set DATABASE_URL (e.g. your Supabase Postgres
# connection string) in production.
# On Vercel use Supabase's *Transaction pooler* URL (port 6543): serverless functions open
# many short-lived connections, and Supabase's direct connection is IPv6-only.
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
if DATABASE_URL and not DATABASE_URL.startswith(("postgres://", "postgresql://")):
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        f"DATABASE_URL must be a Postgres connection string starting with postgresql://, "
        f"but it starts with {DATABASE_URL.split('//')[0]}//. "
        "In Supabase click Connect -> Transaction pooler and copy that URI "
        "(not the https://...supabase.co Project URL)."
    )
if DATABASE_URL:
    import dj_database_url

    DATABASES = {"default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=0 if ON_VERCEL else 600,  # don't hold connections open between serverless requests
        conn_health_checks=True,
        ssl_require="localhost" not in DATABASE_URL and "127.0.0.1" not in DATABASE_URL,
    )}
    # Transaction-mode poolers (pgbouncer / Supavisor) can't keep server-side cursors.
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:portal"
LOGOUT_REDIRECT_URL = "core:home"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/New_York"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
# If the collected files/manifest aren't bundled into the Vercel function, fall back to
# serving straight from ./static with plain names instead of failing every page with a 500.
WHITENOISE_USE_FINDERS = ON_VERCEL

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Uploaded resource files. They're never served publicly: downloads go through a
# permission-checked view. Locally they live in ./media. Vercel's disk is read-only,
# so set the SUPABASE_S3_* variables to store files in a private Supabase Storage
# bucket. Until then, uploads are switched off on Vercel and people add links instead.
MEDIA_ROOT = BASE_DIR / "media"
UPLOADS_ENABLED = bool(os.environ.get("SUPABASE_S3_BUCKET")) or not ON_VERCEL
# Vercel Functions accept request bodies up to 4.5 MB, so keep uploads under that there.
MAX_UPLOAD_MB = 4 if ON_VERCEL else 25
MEDIA_URL = "/media/"
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 30 * 1024 * 1024

if os.environ.get("SUPABASE_S3_BUCKET"):
    _storages = globals().get("STORAGES", {"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
    _storages["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": os.environ["SUPABASE_S3_BUCKET"],
            "endpoint_url": os.environ["SUPABASE_S3_ENDPOINT"],  # https://<project>.supabase.co/storage/v1/s3
            "region_name": os.environ.get("SUPABASE_S3_REGION", "us-east-1"),
            "access_key": os.environ["SUPABASE_S3_ACCESS_KEY"],
            "secret_key": os.environ["SUPABASE_S3_SECRET_KEY"],
            "default_acl": None,
            "querystring_auth": True,  # private bucket, short-lived signed links
            "querystring_expire": 300,
            "file_overwrite": False,
        },
    }
    STORAGES = _storages

# Email (password resets, receipts). Console backend prints to the terminal locally.
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Bethel Eritrean Church <no-reply@example.org>")

# Stripe online giving. Leave blank to show only offline giving options.
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# Church details shown on receipts and the public giving page.
CHURCH = {
    "name": os.environ.get("CHURCH_NAME", "Bethel Eritrean Alliance Church Atlanta"),
    "short_name": "Bethel Eritrean Church",
    "tigrinya_name": "ቤትኤል ቤተክርስትያን ኤርትራውያን ኣትላንታ",
    "address": os.environ.get("CHURCH_ADDRESS", "5915 Lawrenceville Hwy, Tucker, GA 30084"),
    "email": os.environ.get("CHURCH_EMAIL", "bethelatlanta26@gmail.com"),
    "phone": os.environ.get("CHURCH_PHONE", "404-723-4407"),
    "ein": os.environ.get("CHURCH_EIN", "20-0604532"),
    "zelle": os.environ.get("CHURCH_ZELLE", "678-974-6608"),
    "check_payable_to": os.environ.get("CHURCH_CHECK_PAYABLE", "Bethel Eritrean Alliance Church"),
    "mailing_address": os.environ.get("CHURCH_MAILING_ADDRESS", "5915 Lawrenceville Hwy, Tucker, GA 30084"),
    "founded": 2011,
}

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_CONTENT_TYPE_NOSNIFF = True

# Send errors to the console so they appear in Vercel's Runtime Logs.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {"django": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"), "propagate": False}},
}
