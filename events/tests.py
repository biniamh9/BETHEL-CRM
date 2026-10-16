import shutil
import tempfile
from datetime import date, datetime, time, timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from events.models import Event
from fundraising.tests import SeededTestCase
from ministries.models import Ministry
from resources.models import Resource


def aware(d, h=10):
    return timezone.make_aware(datetime.combine(d, time(h)), timezone.get_current_timezone())


class RepeatTest(SeededTestCase):
    def test_weekly_repeat_expands_and_stops(self):
        start = date(2026, 1, 4)  # a Sunday
        e = Event.objects.create(title="W", start=aware(start), repeat="weekly", repeat_until=date(2026, 2, 1))
        dates = [o.date for o in e.occurrences(date(2026, 1, 1), date(2026, 3, 1))]
        self.assertEqual(dates, [date(2026, 1, 4), date(2026, 1, 11), date(2026, 1, 18), date(2026, 1, 25), date(2026, 2, 1)])

    def test_biweekly_and_monthly(self):
        e = Event.objects.create(title="B", start=aware(date(2026, 1, 1)), repeat="biweekly")
        self.assertEqual([o.date for o in e.occurrences(date(2026, 1, 10), date(2026, 2, 1))], [date(2026, 1, 15), date(2026, 1, 29)])
        m = Event.objects.create(title="M", start=aware(date(2026, 1, 31)), repeat="monthly")
        # months without a 31st are skipped
        self.assertEqual([o.date for o in m.occurrences(date(2026, 1, 1), date(2026, 5, 31))],
                         [date(2026, 1, 31), date(2026, 3, 31), date(2026, 5, 31)])

    def test_occurrences_between_includes_old_repeating_events(self):
        today = date.today()
        old = Event.objects.create(title="Old weekly", start=aware(today - timedelta(days=400)), repeat="weekly")
        found = [o.event for o in Event.occurrences_between(today, today + timedelta(days=7))]
        self.assertIn(old, found)


class EventPagesTest(SeededTestCase):
    def test_pages_render_for_each_role(self):
        e = Event.objects.first()
        urls = [reverse("events:calendar"), reverse("events:calendar") + "?activities=1",
                reverse("events:calendar_month", args=[2026, 12]), reverse("events:upcoming"),
                reverse("events:upcoming") + "?ministry=church", e.get_absolute_url(),
                reverse("activities"), reverse("activities") + "?period=all&followups=1",
                reverse("resources:list"), reverse("core:portal")]
        for u in ("abraham", "nahom", "dawit", "kibrom"):
            self.login(u)
            for url in urls:
                self.assertEqual(self.client.get(url).status_code, 200, f"{u} {url}")
        self.client.logout()
        r = self.client.get(reverse("events:public"))
        self.assertContains(r, "Sunday Worship Service")
        self.assertNotContains(r, "Choir Rehearsal")  # not public
        self.assertContains(self.client.get(reverse("core:home")), "Upcoming events")

    def test_leader_creates_event_only_for_own_ministry(self):
        self.login("kibrom")
        choir = Ministry.objects.get(name="Choir Ministry")
        media = Ministry.objects.get(name="Media Ministry")
        d = (date.today() + timedelta(days=3)).isoformat()
        base = {"title": "Extra rehearsal", "kind": "rehearsal", "date": d, "start_time": "17:00",
                "end_time": "19:00", "repeat": "none"}
        r = self.client.post(reverse("events:new"), {**base, "ministry": media.pk})
        self.assertEqual(r.status_code, 200)  # rejected: not their ministry
        self.assertFalse(Event.objects.filter(title="Extra rehearsal").exists())
        r = self.client.post(reverse("events:new"), {**base, "ministry": choir.pk})
        ev = Event.objects.get(title="Extra rehearsal")
        self.assertRedirects(r, ev.get_absolute_url())
        self.assertEqual(timezone.localtime(ev.start).hour, 17)
        # can't edit a church-wide event
        sunday = Event.objects.get(title="Sunday Worship Service")
        self.assertEqual(self.client.get(reverse("events:edit", args=[sunday.pk])).status_code, 403)

    def test_member_cannot_create_events(self):
        from accounts.models import User

        User.objects.create_user("plain", "p@example.com", "Bethel-Test-2026")
        self.login("plain")
        self.assertEqual(self.client.get(reverse("events:new")).status_code, 403)
        self.assertEqual(self.client.get(reverse("events:calendar")).status_code, 200)

    def test_event_validation(self):
        self.login("abraham")
        r = self.client.post(reverse("events:new"), {"title": "Bad", "kind": "meeting", "date": "2026-11-01",
                                                      "start_time": "18:00", "end_time": "17:00", "repeat": "none"})
        self.assertContains(r, "end must be after")

    def test_public_event_banner_appears_on_home_and_detail_page(self):
        event = Event.objects.create(
            title="Kids Outdoor Activity",
            kind=Event.Kind.YOUTH,
            start=aware(date.today() + timedelta(days=5), 14),
            location="To be confirmed",
            description="A family outdoor gathering.",
            banner_url="https://images.example.org/kids-outdoor-flyer.jpg",
            is_public=True,
        )
        home = self.client.get(reverse("core:home"))
        self.assertContains(home, "Kids Outdoor Activity")
        self.assertContains(home, event.banner_url)
        detail_url = reverse("events:public_detail", args=[event.pk])
        detail = self.client.get(detail_url)
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Add to calendar")

    def test_private_event_has_no_public_detail(self):
        event = Event.objects.create(
            title="Private planning meeting", start=aware(date.today() + timedelta(days=4)), is_public=False
        )
        self.assertEqual(self.client.get(reverse("events:public_detail", args=[event.pk])).status_code, 404)


class ActivitiesPageTest(SeededTestCase):
    def test_leader_sees_only_own_ministry_activities(self):
        self.login("kibrom")
        r = self.client.get(reverse("activities") + "?period=all")
        names = {a.ministry.name for a in r.context["activities"]}
        self.assertEqual(names, {"Choir Ministry"})
        self.login("dawit")
        r = self.client.get(reverse("activities") + "?period=all")
        self.assertGreater(len({a.ministry.name for a in r.context["activities"]}), 1)

    def test_csv(self):
        self.login("abraham")
        r = self.client.get(reverse("activities") + "?export=csv")
        self.assertIn(b"Date,Ministry,Title", r.content)


class ResourceTest(SeededTestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def titles(self, username):
        self.login(username)
        return {r.title for r in self.client.get(reverse("resources:list")).context["resources"]}

    def test_audience_rules(self):
        from accounts.models import User

        User.objects.create_user("plain", "p@example.com", "Bethel-Test-2026")
        member = self.titles("plain")
        self.assertIn("Building fund one-page summary", member)
        self.assertNotIn("Elders' meeting minutes folder", member)
        choir_leader = self.titles("kibrom")
        self.assertIn("Elders' meeting minutes folder", choir_leader)  # leadership-wide
        self.assertNotIn("Sunday school lesson plans — Fall", choir_leader)  # youth ministry only
        self.assertIn("Sunday school lesson plans — Fall", self.titles("biniam"))
        self.assertIn("Sunday school lesson plans — Fall", self.titles("dawit"))  # elders see all

    def test_upload_and_protected_download(self):
        self.login("biniam")
        youth = Ministry.objects.get(name="Youth & Kids Ministry")
        f = SimpleUploadedFile("permission-slip.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        r = self.client.post(reverse("resources:new"), {"title": "Retreat permission slip", "category": "form",
                                                         "ministry": youth.pk, "audience": "ministry", "file": f})
        self.assertRedirects(r, reverse("resources:list"))
        res = Resource.objects.get(title="Retreat permission slip")
        r = self.client.get(reverse("resources:download", args=[res.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b"".join(r.streaming_content), b"%PDF-1.4 test")
        self.login("kibrom")  # different ministry: cannot download
        self.assertEqual(self.client.get(reverse("resources:download", args=[res.pk])).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("resources:download", args=[res.pk])).status_code, 302)  # to login

    def test_rejects_bad_files_and_empty(self):
        self.login("abraham")
        r = self.client.post(reverse("resources:new"), {"title": "Nothing", "category": "document", "audience": "members"})
        self.assertContains(r, "Attach a file or add a link")
        f = SimpleUploadedFile("evil.exe", b"MZ", content_type="application/octet-stream")
        r = self.client.post(reverse("resources:new"), {"title": "Exe", "category": "document", "audience": "members", "file": f})
        self.assertContains(r, "not allowed")

    def test_member_cannot_add(self):
        from accounts.models import User

        User.objects.create_user("plain", "p@example.com", "Bethel-Test-2026")
        self.login("plain")
        self.assertEqual(self.client.get(reverse("resources:new")).status_code, 403)
