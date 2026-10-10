from datetime import date
from decimal import Decimal
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from fundraising.models import Campaign, Donation, Donor, Pledge
from ministries.models import Activity, Ministry

PW = "Bethel-Test-2026"


class SeededTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_church", password=PW, demo=True, stdout=open("/dev/null", "w"))
        cls.campaign = Campaign.objects.get()

    def login(self, username):
        self.client.logout()
        assert self.client.login(username=username, password=PW)


class PublicPagesTest(SeededTestCase):
    def test_home_and_campaign_render(self):
        for url in (reverse("core:home"), self.campaign.get_absolute_url()):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, "New Church Building Fund")

    def test_progress_includes_opening_balance(self):
        donated = sum(d.amount for d in Donation.objects.filter(status="succeeded"))
        self.assertEqual(self.campaign.raised, Decimal("200000") + donated)

    def test_public_pledge_creates_donor_and_pledge(self):
        r = self.client.post(reverse("fundraising:pledge", args=[self.campaign.slug]), {
            "first_name": "New", "last_name": "Giver", "email": "new@example.com",
            "total_amount": "6000", "frequency": "monthly",
        })
        self.assertContains(r, "Your pledge is recorded")
        self.assertTrue(Pledge.objects.filter(donor__email="new@example.com", total_amount=6000).exists())

    def test_donate_without_stripe_redirects_with_message(self):
        r = self.client.post(reverse("fundraising:donate", args=[self.campaign.slug]), {"amount": "100"})
        self.assertRedirects(r, self.campaign.get_absolute_url())

    @override_settings(STRIPE_SECRET_KEY="sk_test_x", STRIPE_WEBHOOK_SECRET="whsec_x")
    def test_stripe_checkout_and_webhook(self):
        with mock.patch("fundraising.payments.create_checkout_session", return_value="https://checkout.stripe.test/s") as m:
            r = self.client.post(reverse("fundraising:donate", args=[self.campaign.slug]), {
                "first_name": "Online", "last_name": "Giver", "email": "online@example.com", "amount": "250",
                "show_on_wall": "on",
            })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], "https://checkout.stripe.test/s")
        donation = m.call_args.args[0]
        self.assertEqual(donation.status, "pending")
        donation.stripe_session_id = "cs_test_1"
        donation.save()
        before = self.campaign.raised

        event = {"type": "checkout.session.completed",
                 "data": {"object": {"id": "cs_test_1", "payment_status": "paid", "payment_intent": "pi_1"}}}
        with mock.patch("fundraising.payments.parse_webhook", return_value=event):
            r = self.client.post(reverse("fundraising:stripe_webhook"), b"{}", content_type="application/json")
        self.assertEqual(r.status_code, 200)
        donation.refresh_from_db()
        self.assertEqual(donation.status, "succeeded")
        self.assertEqual(self.campaign.raised, before + Decimal("250"))
        # replaying the webhook must not double count
        with mock.patch("fundraising.payments.parse_webhook", return_value=event):
            self.client.post(reverse("fundraising:stripe_webhook"), b"{}", content_type="application/json")
        self.assertEqual(self.campaign.raised, before + Decimal("250"))


class PermissionTest(SeededTestCase):
    def test_finance_pages_by_role(self):
        url = reverse("fundraising:donations")
        expected = {"abraham": 200, "nahom": 200, "dawit": 403, "biniam": 403}
        for username, code in expected.items():
            self.login(username)
            self.assertEqual(self.client.get(url).status_code, code, username)

    def test_elder_sees_totals_but_not_names(self):
        self.login("dawit")
        r = self.client.get(reverse("fundraising:dashboard"))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "Latest gifts")
        self.assertContains(r, "visible only to the Pastor")

    def test_leader_only_sees_own_ministry(self):
        self.login("kibrom")
        choir = Ministry.objects.get(name="Choir Ministry")
        media = Ministry.objects.get(name="Media Ministry")
        self.assertEqual(self.client.get(choir.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(media.get_absolute_url()).status_code, 403)
        self.assertEqual(self.client.get(reverse("fundraising:dashboard")).status_code, 403)

    def test_elder_can_view_but_not_edit_ministry(self):
        self.login("girmay")
        choir = Ministry.objects.get(name="Choir Ministry")
        self.assertEqual(self.client.get(choir.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(reverse("ministries:activity_new", args=[choir.slug])).status_code, 403)

    def test_member_registration_has_no_ministry_access(self):
        r = self.client.post(reverse("accounts:register"), {
            "first_name": "A", "last_name": "B", "username": "newmember", "email": "nm@example.com",
            "password1": "Long-Enough-Pass-1", "password2": "Long-Enough-Pass-1",
        })
        self.assertRedirects(r, reverse("core:portal"))
        self.assertEqual(User.objects.get(username="newmember").role, "member")
        choir = Ministry.objects.get(name="Choir Ministry")
        self.assertEqual(self.client.get(choir.get_absolute_url()).status_code, 403)


class WorkflowTest(SeededTestCase):
    def test_leader_records_activity(self):
        self.login("kibrom")
        choir = Ministry.objects.get(name="Choir Ministry")
        r = self.client.post(reverse("ministries:activity_new", args=[choir.slug]), {
            "title": "Sunday rehearsal", "kind": "rehearsal", "date": date.today().isoformat(),
            "attendance": "18", "volunteer_hours": "4", "summary": "Learned two new songs.",
        })
        self.assertRedirects(r, choir.get_absolute_url())
        a = Activity.objects.get(title="Sunday rehearsal")
        self.assertEqual(a.created_by.username, "kibrom")

    def test_finance_records_pledge_payment_and_receipt(self):
        self.login("nahom")
        pledge = Pledge.objects.filter(status="active").first()
        remaining = pledge.remaining
        r = self.client.post(reverse("fundraising:donation_new"), {
            "campaign": self.campaign.pk, "pledge": pledge.pk, "amount": str(remaining),
            "method": "check", "status": "succeeded", "received_on": date.today().isoformat(), "reference": "1042",
        })
        self.assertRedirects(r, reverse("fundraising:donations"))
        pledge.refresh_from_db()
        self.assertEqual(pledge.status, "completed")
        d = Donation.objects.get(reference="1042")
        self.assertEqual(d.donor, pledge.donor)
        r = self.client.get(reverse("fundraising:receipt", args=[d.pk]))
        self.assertContains(r, d.receipt_number)
        r = self.client.get(reverse("fundraising:statement", args=[d.donor.pk, date.today().year]))
        self.assertEqual(r.status_code, 200)

    def test_finance_adds_new_donor_inline(self):
        self.login("nahom")
        self.client.post(reverse("fundraising:donation_new"), {
            "campaign": self.campaign.pk, "new_donor_first": "Walk", "new_donor_last": "In",
            "amount": "40", "method": "cash", "status": "succeeded", "received_on": date.today().isoformat(),
        })
        self.assertTrue(Donation.objects.filter(donor__first_name="Walk", amount=40).exists())

    def test_pastor_creates_leader_login(self):
        self.login("abraham")
        evangelism = Ministry.objects.get(name="Evangelism Ministry")
        r = self.client.post(reverse("accounts:team_new"), {
            "first_name": "New", "last_name": "Leader", "username": "evangelist", "email": "e@example.com",
            "role": "leader", "password": "Strong-Temp-Pass-9", "ministries": [evangelism.pk], "is_active": "on",
        })
        self.assertRedirects(r, reverse("accounts:team"))
        self.client.logout()
        self.assertTrue(self.client.login(username="evangelist", password="Strong-Temp-Pass-9"))
        self.assertEqual(self.client.get(evangelism.get_absolute_url()).status_code, 200)

    def test_csv_exports(self):
        self.login("nahom")
        r = self.client.get(reverse("fundraising:donations") + "?export=csv")
        self.assertEqual(r["Content-Type"], "text/csv")
        self.assertIn(b"Receipt,Date,Donor", r.content)

    def test_member_sees_own_gifts(self):
        donor = Donor.objects.first()
        u = User.objects.create_user("giver", donor.email, PW)
        donor.user = u
        donor.save()
        self.login("giver")
        r = self.client.get(reverse("accounts:profile"))
        self.assertContains(r, "My giving")
        self.assertNotContains(r, "No gifts linked")
