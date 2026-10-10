"""Vercel build step (see vercel.json "buildCommand").

1. Prints a setup checklist, so the build log says exactly what's missing.
2. Collects the CSS and images.
3. On production deployments only: checks the Supabase connection, creates/updates the
   database tables and loads the church structure. Preview deployments never touch the
   database.
"""
import os
import subprocess
import sys

PRODUCTION = os.environ.get("VERCEL_ENV", "local") == "production"


def run(*args):
    print("+ python manage.py", " ".join(args), flush=True)
    subprocess.run([sys.executable, "manage.py", *args], check=True)


def fail(message):
    print("\n" + "=" * 70 + "\nSETUP PROBLEM\n" + message + "\n" + "=" * 70 + "\n", flush=True)
    sys.exit(1)


def checklist():
    has_db = any(os.environ.get(v, "").strip() for v in ("DATABASE_URL", "POSTGRES_URL"))
    items = [
        ("DATABASE_URL", has_db, "Supabase -> Connect -> Transaction pooler URI"),
        ("SECRET_KEY", bool(os.environ.get("SECRET_KEY")), "any long random text"),
        ("INITIAL_ADMIN_PASSWORD", bool(os.environ.get("INITIAL_ADMIN_PASSWORD")),
         "optional: Pastor Abraham's first password"),
    ]
    print("\nSetup checklist (Vercel -> Settings -> Environment Variables):", flush=True)
    for name, ok, hint in items:
        print(f"  [{'x' if ok else ' '}] {name:<24} {hint}", flush=True)
    print(flush=True)
    return has_db


def load_settings():
    """Load the settings now, so a wrong DATABASE_URL gives a plain message, not a traceback."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    from django.core.exceptions import ImproperlyConfigured

    try:
        django.setup()
    except ImproperlyConfigured as e:
        fail(str(e))


def redact(text, settings_dict):
    """Never let the database password reach the build log."""
    password = settings_dict.get("PASSWORD") or ""
    return text.replace(password, "<password hidden>") if password else text


def check_connection():
    """Connect once and translate the usual Supabase mistakes into plain words."""
    from django.db import connection

    host = connection.settings_dict.get("HOST", "")
    if host.startswith("db.") and host.endswith(".supabase.co"):
        fail(f"DATABASE_URL uses Supabase's direct address ({host}), which Vercel can't reach. "
             "In Supabase click Connect, choose 'Transaction pooler' (shared pooler) and copy that URI instead: "
             "its host ends in pooler.supabase.com and its user name looks like postgres.<project-id>.")
    try:
        connection.ensure_connection()
    except Exception as e:  # noqa: BLE001 - every failure gets a plain, password-free message
        text = redact(str(e), connection.settings_dict)
        if "password authentication failed" in text:
            fail("Supabase rejected the database password. Check the password in DATABASE_URL, or reset it in "
                 "Supabase -> Project Settings -> Database and paste the new connection string.")
        if "tenant" in text.lower() and "not found" in text:
            fail("Supabase can't find this project. Copy the whole Transaction pooler URI again from Supabase -> "
                 "Connect: the user name must look like postgres.<your-project-id> and the host's region "
                 "(e.g. aws-0-us-east-1) must match your project.")
        if "Network is unreachable" in text or "could not translate host name" in text or "timeout" in text:
            fail("Can't reach the database. Make sure you copied the 'Transaction pooler' URI (host ends in "
                 "pooler.supabase.com, port 6543), not the 'Direct connection', and that the Supabase project "
                 "isn't paused.")
        fail(f"Couldn't connect to the database:\n{text}")
    print(f"Connected to the database ({connection.settings_dict['HOST']}).", flush=True)


def main():
    has_db = checklist()
    missing = [name for name, ok in (("DATABASE_URL", has_db), ("SECRET_KEY", os.environ.get("SECRET_KEY"))) if not ok]
    if PRODUCTION and missing:
        fail(f"Not set yet: {' and '.join(missing)}. Add them in Vercel -> Settings -> Environment Variables "
             "(see DEPLOY.md, step 3), then redeploy.")

    load_settings()
    run("collectstatic", "--noinput")

    if not PRODUCTION:
        print("Preview deployment: not touching the database (only production deployments do).")
        return
    check_connection()
    run("migrate", "--noinput")
    run("seed_church")  # safe to repeat: only adds what's missing


if __name__ == "__main__":
    main()
