"""Turn the Supabase connection string from the environment into Django's DATABASES setting.

Reads DATABASE_URL (what you paste in by hand) or, failing that, POSTGRES_URL (what
Vercel's Supabase integration adds). Problems are reported in plain words, because they
show up in the Vercel build log.
"""
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.core.exceptions import ImproperlyConfigured

URL_VARIABLES = ("DATABASE_URL", "POSTGRES_URL")

# Query options the Postgres driver understands. Others, like the "supa=base-pooler.x"
# that Vercel's Supabase integration appends, make every connection fail, so drop them.
DRIVER_OPTIONS = {"sslmode", "sslrootcert", "sslcert", "sslkey", "connect_timeout",
                  "application_name", "options", "target_session_attrs", "channel_binding"}

HOW_TO_GET_IT = (
    "In Supabase open your project, click Connect, choose 'Transaction pooler' and copy the URI "
    "(it starts with postgresql:// and ends with :6543/postgres)."
)


def find_database_url():
    """Return (variable name, URL) for the first usable connection string, or (None, None)."""
    wrong = []
    for name in URL_VARIABLES:
        value = tidy(os.environ.get(name, ""), name)
        if not value:
            continue
        if value.startswith(("postgres://", "postgresql://")):
            return name, value
        if value.startswith("http"):
            wrong.append(f"{name} starts with {value.split('//')[0]}// (that's the Supabase Project URL, "
                         "not the database connection string)")
        else:
            wrong.append(f"{name} starts with {value[:12]!r}")
    if wrong:
        raise ImproperlyConfigured(
            f"The database setting is wrong: {'; '.join(wrong)}. It must start with postgresql:// "
            f"and have nothing before it. {HOW_TO_GET_IT}"
        )
    return None, None


def tidy(value, name):
    """Forgive common copy-paste extras: spaces, surrounding quotes or brackets, and a NAME= prefix."""
    value = value.strip()
    if value.upper().startswith(f"{name}="):
        value = value[len(name) + 1:].strip()
    while len(value) > 1 and value[0] + value[-1] in ('""', "''", "[]", "<>", "``"):
        value = value[1:-1].strip()
    return value


def clean_url(url):
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k in DRIVER_OPTIONS]
    return urlunsplit(parts._replace(query=urlencode(query)))


def database_settings(url, serverless):
    import dj_database_url

    if "[YOUR-PASSWORD]" in url:
        raise ImproperlyConfigured(
            "The database connection string still contains [YOUR-PASSWORD]. Replace it, including the "
            "square brackets, with your Supabase database password."
        )
    try:
        config = dj_database_url.parse(
            clean_url(url),
            conn_max_age=0 if serverless else 600,  # serverless: don't hold connections between requests
            conn_health_checks=True,
            ssl_require="localhost" not in url and "127.0.0.1" not in url,
        )
    except ValueError:
        raise ImproperlyConfigured(
            "The database connection string can't be read. This usually means the database password "
            "contains characters like # / ? or %. In Supabase go to Project Settings -> Database -> "
            "Reset database password, choose one with only letters and numbers, then paste the new "
            "connection string into Vercel."
        ) from None
    # Supabase's Transaction pooler can't keep server-side cursors open between queries.
    config["DISABLE_SERVER_SIDE_CURSORS"] = True
    return config
