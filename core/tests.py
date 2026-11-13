import os
from io import BytesIO
from unittest import mock

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from core.middleware import DatabaseConfigCheck
from core.models import HeroImage


class DeploymentTest(TestCase):
    def test_public_about_and_visit_pages(self):
        about = self.client.get(reverse("core:about"))
        self.assertEqual(about.status_code, 200)
        self.assertContains(about, "<title>About · Bethel Eritrean Church</title>", html=True)
        self.assertContains(about, "Pastor Abraham Yosief")
        self.assertContains(about, "Our mission")
        visit = self.client.get(reverse("core:visit"))
        self.assertEqual(visit.status_code, 200)
        self.assertContains(visit, "<title>Plan Your Visit · Bethel Eritrean Church</title>", html=True)
        self.assertContains(visit, "10:30 AM")
        self.assertContains(visit, "Get directions")

    def test_public_auth_pages_have_one_primary_heading(self):
        login = self.client.get(reverse("accounts:login"))
        self.assertContains(login, "<h1>Sign In</h1>", html=True)
        register = self.client.get(reverse("accounts:register"))
        self.assertContains(register, "<h1>Create a member account</h1>", html=True)

    def test_public_pages_offer_sharing_and_shared_links_prompt_support(self):
        home = self.client.get(reverse("core:home"))
        self.assertContains(home, "Share the story")
        self.assertContains(home, "data-share-facebook")
        self.assertNotContains(home, "Someone shared this with you")
        shared = self.client.get(reverse("core:home"), {"shared": "1"})
        self.assertContains(shared, "Someone shared this with you")
        self.assertContains(shared, reverse("fundraising:give"))
        self.assertContains(shared, 'property="og:image"')

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

    def test_leadership_dashboard_has_central_content_management(self):
        call_command("seed_church", password="Bethel-Test-2026", stdout=open(os.devnull, "w"))
        self.client.login(username="abraham", password="Bethel-Test-2026")
        response = self.client.get(reverse("core:portal"))
        self.assertContains(response, "Manage church content")
        self.assertContains(response, reverse("events:upcoming"))
        self.assertContains(response, reverse("activities"))
        self.assertContains(response, reverse("ministries:gallery_hub"))
        self.assertContains(response, reverse("ministries:birthday_list"))
        self.assertContains(response, reverse("resources:list"))
        self.assertContains(response, reverse("core:hero_manager"))

    def test_csrf_failure_page_offers_safe_retry(self):
        from core.views import csrf_failure

        request = RequestFactory().post("/portal/events/new/")
        response = csrf_failure(request, "test failure")
        self.assertEqual(response.status_code, 403)
        self.assertIn(b"Reload the form", response.content)
        self.assertNotIn(b"test failure", response.content)


class HeroImageManagementTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="site-admin", password="Strong-Test-2026", role=User.Role.ADMIN
        )
        self.member = User.objects.create_user(
            username="ordinary-member", password="Strong-Test-2026", role=User.Role.MEMBER
        )

    @staticmethod
    def image_upload(name="hero.png"):
        output = BytesIO()
        Image.new("RGB", (1800, 1200), "#31504c").save(output, "PNG")
        return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")

    def test_only_administrators_can_manage_hero_images(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(reverse("core:hero_manager")).status_code, 403)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("core:hero_manager"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Homepage — first slideshow image")

    def test_admin_uploads_optimized_hero_and_public_page_uses_it(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("core:hero_edit", args=["about"]), {
            "image": self.image_upload(), "alt_text": "Church family worshipping", "position": "center top",
        })
        self.assertRedirects(response, reverse("core:hero_manager"))
        hero = HeroImage.objects.get(placement="about")
        self.assertLess(len(hero.image_blob), 1024 * 1024)
        self.assertEqual(hero.content_type, "image/jpeg")
        public = self.client.get(reverse("core:about"))
        self.assertContains(public, hero.image_url)
        image = self.client.get(hero.image_url)
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image["Content-Type"], "image/jpeg")

    def test_removing_upload_restores_original_design(self):
        HeroImage.objects.create(
            placement="visit", image_blob=b"image", filename="visit.jpg", content_type="image/jpeg"
        )
        self.client.force_login(self.admin)
        self.client.post(reverse("core:hero_edit", args=["visit"]), {
            "position": "center center", "remove_image": "on",
        })
        self.assertFalse(HeroImage.objects.filter(placement="visit").exists())


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
