"""Vercel build step: create/update database tables and load the church structure.

Vercel runs this after installing requirements (see vercel.json "buildCommand").
It collects static files, then touches the database only for production
deployments, so preview deployments can't change live data.
"""
import os
import subprocess
import sys


def run(*args):
    print("+ python manage.py", " ".join(args), flush=True)
    subprocess.run([sys.executable, "manage.py", *args], check=True)


def main():
    run("collectstatic", "--noinput")
    env = os.environ.get("VERCEL_ENV", "local")
    if not (os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")):
        print("DATABASE_URL is not set: skipping migrations. Add it in Vercel -> Settings -> Environment Variables, then redeploy.")
        return
    if env != "production" and os.environ.get("MIGRATE_ON_PREVIEW") != "1":
        print(f"VERCEL_ENV={env}: skipping migrations (only production deployments change the database).")
        return
    run("migrate", "--noinput")
    run("seed_church")  # safe to repeat: only adds what's missing


if __name__ == "__main__":
    main()
