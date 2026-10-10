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


SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

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
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
except ImportError:
    pass

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
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    import dj_database_url

    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=not DEBUG)}
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

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Uploaded resource files. They're never served publicly: downloads go through a
# permission-checked view. Locally they live in ./media. In production, hosts like
# Render wipe the disk on each deploy, so set the SUPABASE_S3_* variables to store
# files in a private Supabase Storage bucket instead (needs `pip install django-storages boto3`).
MEDIA_ROOT = BASE_DIR / "media"
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
    "address": os.environ.get("CHURCH_ADDRESS", "Metro Atlanta, Georgia"),
    "email": os.environ.get("CHURCH_EMAIL", ""),
    "phone": os.environ.get("CHURCH_PHONE", ""),
    "ein": os.environ.get("CHURCH_EIN", ""),
    "zelle": os.environ.get("CHURCH_ZELLE", ""),
    "check_payable_to": os.environ.get("CHURCH_CHECK_PAYABLE", "Bethel Eritrean Alliance Church"),
    "mailing_address": os.environ.get("CHURCH_MAILING_ADDRESS", ""),
    "founded": 2011,
}

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_CONTENT_TYPE_NOSNIFF = True
