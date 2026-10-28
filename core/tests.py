import os
from unittest import mock

from django.core.management import call_command
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from core.middleware import DatabaseConfigCheck


class DeploymentTest(TestCase):
    def test_public_about_and_visit_pages(self):
        about = self.client.get(reverse("core:about"))
        self.assertEqual(about.status_code, 200)
        self.assertContains(about, "Pastor Abraham Yosief")
        self.assertContains(about, "Our mission")
        visit = self.client.get(reverse("core:visit"))
        self.assertEqual(visit.status_code, 200)
        self.assertContains(visit, "10:30 AM")
        self.assertContains(visit, "Get directions")

    def test_setup_page_when_database_missing_on_vercel(self):
        sqlite = {"default": {"ENGINE": "django.db.backends.sqlite3"}}
        with override_settings(ON_VERCEL=True, DATABASES=sqlite):
            mw = DatabaseConfigCheck(lambda r: HttpResponse("app"))
            r = mw(RequestFactory().get("/"))
            self.assertEqual(r.status_code, 503)
            self.assertIn(b"DATABASE_URL", r.content)
            self.assertEqual(mw(RequestFactory().get("/static/css/site.css")).content, b"app")
        with override_settings(ON_VERCEL=False):
            self.assertEqual(DatabaseConfigCheck(lambda r: HttpResponse("app"))(RequestFactory().get("/")).content, b"app")

    def test_initial_admin_password_only_applies_once(self):
        with mock.patch.dict(os.environ, {"INITIAL_ADMIN_PASSWORD": "First-Pass-2026"}):
            call_command("seed_church", stdout=open(os.devnull, "w"))
        self.assertTrue(self.client.login(username="abraham", password="First-Pass-2026"))
        pastor = User.objects.get(username="abraham")
        pastor.set_password("Pastor-Chosen-99")
        pastor.save()
        with mock.patch.dict(os.environ, {"INITIAL_ADMIN_PASSWORD": "First-Pass-2026"}):
            call_command("seed_church", stdout=open(os.devnull, "w"))  # e.g. the next deploy
        self.assertTrue(self.client.login(username="abraham", password="Pastor-Chosen-99"))
        # other logins never get the admin password
        self.assertFalse(User.objects.get(username="nahom").has_usable_password())

    def test_resource_form_is_links_only_when_uploads_disabled(self):
        call_command("seed_church", password="Bethel-Test-2026", stdout=open(os.devnull, "w"))
        self.client.login(username="abraham", password="Bethel-Test-2026")
        with override_settings(UPLOADS_ENABLED=False):
            r = self.client.get(reverse("resources:new"))
            self.assertNotContains(r, 'type="file"')
            r = self.client.post(reverse("resources:new"), {"title": "No link", "category": "document", "audience": "members"})
            self.assertEqual(r.status_code, 200)
            r = self.client.post(reverse("resources:new"), {"title": "Drive folder", "category": "document",
                                                            "audience": "members", "url": "https://drive.google.com/x"})
            self.assertRedirects(r, reverse("resources:list"))
        with override_settings(UPLOADS_ENABLED=True):
            self.assertContains(self.client.get(reverse("resources:new")), 'type="file"')

    def test_portal_forms_are_never_cached(self):
        call_command("seed_church", password="Bethel-Test-2026", stdout=open(os.devnull, "w"))
        self.client.login(username="abraham", password="Bethel-Test-2026")
        response = self.client.get(reverse("events:new"))
        self.assertEqual(response["Cache-Control"], "private, no-store, max-age=0")
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_csrf_failure_page_offers_safe_retry(self):
        from core.views import csrf_failure

        request = RequestFactory().post("/portal/events/new/")
        response = csrf_failure(request, "test failure")
        self.assertEqual(response.status_code, 403)
        self.assertIn(b"Reload the form", response.content)
        self.assertNotIn(b"test failure", response.content)


class SupabaseConnectionStringTest(TestCase):
    POOLER = "postgresql://postgres.abcd:secret123@aws-0-us-east-1.pooler.supabase.com:6543/postgres"

    def find(self, **env):
        from config.database import find_database_url

        with mock.patch.dict(os.environ, env, clear=True):
            return find_database_url()

    def test_pasted_transaction_pooler_uri(self):
        from config.database import database_settings

        self.assertEqual(self.find(DATABASE_URL=self.POOLER), ("DATABASE_URL", self.POOLER))
        db = database_settings(self.POOLER, serverless=True)
        self.assertEqual((db["HOST"], db["PORT"], db["USER"]), ("aws-0-us-east-1.pooler.supabase.com", 6543, "postgres.abcd"))
        self.assertEqual(db["OPTIONS"], {"sslmode": "require"})
        self.assertEqual(db["CONN_MAX_AGE"], 0)

    def test_vercel_integration_url_drops_supa_option(self):
        from config.database import database_settings

        name, url = self.find(POSTGRES_URL=self.POOLER + "?sslmode=require&supa=base-pooler.x")
        self.assertEqual(name, "POSTGRES_URL")
        self.assertEqual(database_settings(url, serverless=True)["OPTIONS"], {"sslmode": "require"})

    def test_plain_explanations_for_common_mistakes(self):
        from django.core.exceptions import ImproperlyConfigured

        from config.database import database_settings

        with self.assertRaisesMessage(ImproperlyConfigured, "Project URL"):
            self.find(DATABASE_URL="https://abcd.supabase.co")
        with self.assertRaisesMessage(ImproperlyConfigured, "[YOUR-PASSWORD]"):
            database_settings(self.POOLER.replace("secret123", "[YOUR-PASSWORD]"), serverless=True)
        with self.assertRaisesMessage(ImproperlyConfigured, "letters and numbers"):
            database_settings(self.POOLER.replace("secret123", "ab#c"), serverless=True)
        self.assertEqual(self.find(), (None, None))

    def test_forgives_copy_paste_extras(self):
        for pasted in (f'"{self.POOLER}"', f"'{self.POOLER}'", f"  {self.POOLER}\n", f"DATABASE_URL={self.POOLER}",
                       f'DATABASE_URL="{self.POOLER}"', f"[{self.POOLER}]"):
            self.assertEqual(self.find(DATABASE_URL=pasted), ("DATABASE_URL", self.POOLER), pasted)

    def test_garbled_url_is_explained_without_the_password(self):
        from django.core.exceptions import ImproperlyConfigured

        from config.database import database_settings

        garbled = "postgresql:///postgres:Secret99@db.abcd.supabase.co:6543/postgres"
        with self.assertRaises(ImproperlyConfigured) as cm:
            database_settings(garbled, serverless=True)
        self.assertIn("garbled", str(cm.exception))
        self.assertNotIn("Secret99", str(cm.exception))
