"""Load Bethel's real structure from the org chart.

    python manage.py seed_church                          # ministries, leaders, building fund
    python manage.py seed_church --password Temp-Pass-2026 # give every seeded login this temporary password
    python manage.py seed_church --demo                   # also add sample gifts and activities (for testing only)

Safe to run more than once: existing records are left as they are.
"""
import os
import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from fundraising.models import Campaign, Donation, Donor, Pledge
from ministries.models import Activity, Ministry, Participant

R = User.Role

PEOPLE = [
    # username, first, last, role, title
    ("abraham", "Abraham", "", R.ADMIN, "Senior Pastor"),
    ("girmay", "Girmay", "", R.ELDER, "Elder / Secretary"),
    ("dawit", "Dawit", "", R.ELDER, "Elder"),
    ("robel", "Robel", "", R.ELDER, "Elder"),
    ("tsegazeab", "Tsegazeab", "", R.ELDER, "Elder"),
    ("nahom", "Nahom", "", R.FINANCE, "Chief Financial Officer"),
    ("meron", "Meron", "", R.LEADER, "Diocese Ministry Leader"),
    ("biniam", "Biniam", "", R.LEADER, "Youth & Kids Ministry Director"),
    ("miki", "Miki", "", R.LEADER, "Media Ministry Leader"),
    ("kibrom", "Kibrom", "", R.LEADER, "Choir Ministry Leader"),
    ("azieb", "Azieb", "", R.LEADER, "Women Service Leader"),
    ("solomon", "Solomon", "G/meskel", R.LEADER, "Men's Ministry Leader"),
    ("pitias", "Pitias", "", R.LEADER, "Adult Bible Study Leader"),
]

MINISTRIES = [
    # name, color, leader shown publicly, login usernames, description
    ("Diocese Ministry", "blue", "Meron", ["meron"], "Coordinates deacons, church order and care for the congregation."),
    ("Youth & Kids Ministry", "green", "Biniam", ["biniam"],
     "Weekly programs for 32 children and 42 middle school, high school and college students: character, leadership and discipleship."),
    ("Media Ministry", "purple", "Miki", ["miki"], "Livestreams, sound, slides, photography and the church's online presence."),
    ("Choir Ministry", "gold", "Kibrom", ["kibrom"], "Leads worship through song in Tigrinya and English."),
    ("Women Service", "red", "Azieb", ["azieb"], "Fellowship, care and service led by the women of the church."),
    ("Prayer Ministry", "teal", "Pastor Abraham", ["abraham"], "Prayer gatherings and the church's prayer support network."),
    ("Evangelism Ministry", "orange", "Leader TBD", [], "Outreach to new immigrant families and the wider Atlanta community."),
    ("Men's Ministry", "navy", "Solomon G/meskel", ["solomon"], "Brotherhood, mentoring and family leadership for men."),
    ("Bible Study", "green", "Pastor Abraham", ["abraham"], "Weekly teaching and discussion of Scripture."),
    ("Adult Bible Study", "purple", "Pitias", ["pitias"], "In-depth Bible study for adults."),
]

STORY = """Since 2011, Bethel Eritrean Alliance Church has faithfully served Eritrean families and the broader community in the Atlanta, Georgia area.

For more than 15 years, our church has been more than a place of Sunday worship. It has been a spiritual home where families gather in faith, children learn biblical values, young people receive encouragement and mentorship, and generations come together in fellowship and service.

As our congregation continues to grow, so does our need for a permanent place to worship and serve our community.

Today, we are taking an important step of faith toward purchasing our own church building in Stone Mountain, Georgia.

## Why We Need Your Support

Our vision is to establish a permanent church home that will allow us to:

- Provide a welcoming sanctuary for worship and prayer.
- Create dedicated classrooms for children's Bible education.
- Expand youth discipleship and mentorship programs.
- Offer space for family fellowship and community gatherings.
- Preserve our Eritrean Christian heritage while serving future generations.
- Build a lasting foundation for our church's mission.

## Our Building Fund Campaign

We are raising funds to support the purchase of our new church property and the essential expenses needed to prepare the building for worship and ministry activities.

Every contribution, regardless of size, brings us closer to securing a permanent home for our congregation.

Your donation is more than a contribution toward a building. It is an investment in faith, family, community, and future generations.

## How You Can Help

1. Make a donation of any amount.
2. Share this campaign with friends, family, and your community.
3. Invite others who believe in our mission to support this effort.
4. Keep our church in your prayers as we move forward.

We are deeply grateful for every prayer, donation, and act of encouragement.

Together, let us build a home where faith grows, families are strengthened, and future generations are inspired.

With gratitude,
Bethel Eritrean Alliance Church
Atlanta, Georgia"""


class Command(BaseCommand):
    help = "Create Bethel's ministries, leader logins and building fund campaign."

    def add_arguments(self, parser):
        parser.add_argument("--password", help="Temporary password for every seeded login (they should change it).")
        parser.add_argument("--goal", type=Decimal, default=Decimal("1500000"), help="Building fund goal in dollars.")
        parser.add_argument("--demo", action="store_true", help="Add sample donations and activities for testing.")

    @transaction.atomic
    def handle(self, *args, password=None, goal=None, demo=False, **opts):
        users = {}
        for username, first, last, role, title in PEOPLE:
            user, created = User.objects.get_or_create(
                username=username, defaults={"first_name": first, "last_name": last, "role": role, "title": title})
            if created:
                if password:
                    user.set_password(password)
                else:
                    user.set_unusable_password()
                if role == R.ADMIN:
                    user.is_staff = user.is_superuser = True
                user.save()
            users[username] = user

        # First Pastor password from the INITIAL_ADMIN_PASSWORD environment variable (e.g. set in Vercel).
        # Only applied while the account has no usable password, so it never overwrites a password
        # the Pastor has chosen. Remove the variable after the first login.
        initial = os.environ.get("INITIAL_ADMIN_PASSWORD", "").strip()
        pastor = users["abraham"]
        if initial and not pastor.has_usable_password():
            pastor.set_password(initial)
            pastor.save(update_fields=["password"])
            self.stdout.write(self.style.SUCCESS("Set Pastor Abraham's first password from INITIAL_ADMIN_PASSWORD."))

        for i, (name, color, shown, logins, desc) in enumerate(MINISTRIES):
            m, _ = Ministry.objects.get_or_create(
                name=name, defaults={"color": color, "leader_display": shown, "description": desc, "sort_order": i})
            for u in logins:
                m.leaders.add(users[u])

        campaign, created = Campaign.objects.get_or_create(
            slug="new-church-building",
            defaults={
                "name": "Help Bethel Eritrean Church Build a Permanent Home",
                "tagline": "A Home for Worship. A Place for Families. A Future for Our Children.",
                "story": STORY,
                "goal_amount": goal,
                "opening_balance": Decimal("200000"),
                "opening_balance_label": "Saved by our members since 2011",
                "start_date": date.today(),
            },
        )
        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(PEOPLE)} logins, {len(MINISTRIES)} ministries and the '{campaign.name}' campaign."))
        if not password:
            self.stdout.write("Logins were created without passwords. Set them on the Team page (/accounts/team/) "
                              "or rerun with --password for a shared temporary password.")
        if demo:
            self._demo(campaign, users)

    def _demo(self, campaign, users):
        rng = random.Random(7)
        names = [("Selam", "Tesfay"), ("Yonas", "Haile"), ("Helen", "Kidane"), ("Samuel", "Ghebre"),
                 ("Ruth", "Berhane"), ("Daniel", "Asmerom"), ("Hanna", "Woldu"), ("Filmon", "Tekle"),
                 ("Lidia", "Mehari"), ("Aron", "Yemane"), ("Senait", "Habte"), ("Michael", "Andemariam")]
        donors = [Donor.find_or_create(f, l, f"{f.lower()}.{l.lower()}@example.com", "404-555-01%02d" % i)
                  for i, (f, l) in enumerate(names)]
        methods = [Donation.Method.ZELLE, Donation.Method.CHECK, Donation.Method.CASH, Donation.Method.ONLINE]
        for _ in range(45):
            Donation.objects.create(
                campaign=campaign, donor=rng.choice(donors), amount=Decimal(rng.choice([50, 100, 200, 250, 500, 1000, 2500])),
                method=rng.choice(methods), received_on=date.today() - timedelta(days=rng.randint(0, 300)),
                show_on_wall=rng.random() < 0.7, recorded_by=users["nahom"])
        for d in donors[:5]:
            p = Pledge.objects.create(donor=d, campaign=campaign, total_amount=Decimal(rng.choice([5000, 10000, 12000])),
                                      frequency=Pledge.Frequency.MONTHLY, start_date=date.today() - timedelta(days=120))
            Donation.objects.create(campaign=campaign, donor=d, pledge=p, amount=Decimal("1000"),
                                    method=Donation.Method.ZELLE, received_on=date.today() - timedelta(days=10))
        for m in Ministry.objects.all():
            for f, l in rng.sample(names, 5):
                Participant.objects.get_or_create(ministry=m, first_name=f, last_name=l)
            for w in range(6):
                Activity.objects.create(
                    ministry=m, title=f"Weekly {m.name.split()[0]} gathering", kind=Activity.Kind.MEETING,
                    date=date.today() - timedelta(days=7 * w), attendance=rng.randint(8, 40),
                    summary="Sample record created by seed_church --demo.", created_by=m.leaders.first())
        self._demo_events_and_resources(users)
        self.stdout.write(self.style.WARNING("Added demo donors, gifts, activities, events and resources. Don't use --demo on the live site."))

    def _demo_events_and_resources(self, users):
        from datetime import datetime, time

        from django.utils import timezone

        from events.models import Event
        from resources.models import Resource

        tz = timezone.get_current_timezone()
        today = date.today()

        def next_weekday(wd):  # Monday=0 ... Sunday=6
            return today + timedelta(days=(wd - today.weekday()) % 7)

        def at(d, h, m=0):
            return timezone.make_aware(datetime.combine(d, time(h, m)), tz)

        M = {m.name: m for m in Ministry.objects.all()}
        weekly = [
            ("Sunday Worship Service", Event.Kind.SERVICE, None, 6, 11, 0, 13, 30, True),
            ("Wednesday Prayer Night", Event.Kind.PRAYER, "Prayer Ministry", 2, 19, 0, 20, 30, True),
            ("Youth Gathering", Event.Kind.YOUTH, "Youth & Kids Ministry", 4, 18, 30, 20, 30, False),
            ("Choir Rehearsal", Event.Kind.REHEARSAL, "Choir Ministry", 5, 16, 0, 18, 0, False),
            ("Bible Study", Event.Kind.BIBLE, "Bible Study", 1, 19, 0, 20, 30, True),
        ]
        for title, kind, mname, wd, sh, sm, eh, em, public in weekly:
            d = next_weekday(wd) - timedelta(weeks=8)
            Event.objects.get_or_create(title=title, defaults={
                "kind": kind, "ministry": M.get(mname), "start": at(d, sh, sm), "end": at(d, eh, em),
                "repeat": Event.Repeat.WEEKLY, "is_public": public, "location": "Church hall",
                "created_by": users["abraham"]})
        d = next_weekday(5) + timedelta(weeks=3)
        Event.objects.get_or_create(title="Building Fund Fellowship Dinner", defaults={
            "kind": Event.Kind.FUNDRAISER, "start": at(d, 18), "end": at(d, 21), "is_public": True,
            "location": "Church hall", "created_by": users["nahom"],
            "description": "An evening of food, worship and testimonies to support our new church building."})
        Event.objects.get_or_create(title="Elders' Monthly Meeting", defaults={
            "kind": Event.Kind.MEETING, "start": at(today.replace(day=min(today.day, 28)) - timedelta(days=30), 19),
            "repeat": Event.Repeat.MONTHLY, "created_by": users["girmay"]})
        d = next_weekday(4) + timedelta(weeks=5)
        Event.objects.get_or_create(title="Youth Winter Retreat", defaults={
            "kind": Event.Kind.CONFERENCE, "ministry": M["Youth & Kids Ministry"], "all_day": True,
            "start": at(d, 0), "end": at(d + timedelta(days=2), 23, 59), "created_by": users["biniam"]})

        demo_resources = [
            ("Building fund one-page summary", Resource.Category.DOCUMENT, None, Resource.Audience.MEMBERS),
            ("Child safety & check-in policy", Resource.Category.POLICY, "Youth & Kids Ministry", Resource.Audience.LEADERS),
            ("Sunday school lesson plans — Fall", Resource.Category.CURRICULUM, "Youth & Kids Ministry", Resource.Audience.MINISTRY),
            ("Worship song list (Tigrinya & English)", Resource.Category.SONG, "Choir Ministry", Resource.Audience.MEMBERS),
            ("Livestream setup checklist", Resource.Category.FORM, "Media Ministry", Resource.Audience.MINISTRY),
            ("Elders' meeting minutes folder", Resource.Category.POLICY, None, Resource.Audience.LEADERS),
        ]
        for title, cat, mname, aud in demo_resources:
            Resource.objects.get_or_create(title=title, defaults={
                "category": cat, "ministry": M.get(mname), "audience": aud,
                "url": "https://drive.google.com/", "uploaded_by": users["abraham"],
                "description": "Sample resource created by seed_church --demo."})
