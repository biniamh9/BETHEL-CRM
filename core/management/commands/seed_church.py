"""Load Bethel's real structure from the org chart.

    python manage.py seed_church                          # ministries, leaders, building fund
    python manage.py seed_church --password Temp-Pass-2026 # give every seeded login this temporary password
    python manage.py seed_church --demo                   # also add sample gifts and activities (for testing only)

Safe to run more than once: existing records are left as they are.
"""
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

STORY = """Since 2011, Bethel Eritrean Alliance Church has been a home for Eritrean and East African families across Metro Atlanta — in Atlanta, Tucker, Stone Mountain, Clarkston, Lilburn and Decatur. Today more than 100 members and 74 children, youth and young adults gather with us every week.

We have outgrown our rented space. Limited classrooms, tight scheduling and no room for counseling or youth programs mean we turn families away from programs they need. We currently pay about $2,000 a month in rent and own nothing we can build on.

Our members have already saved about $200,000 toward a permanent home. With your help we will buy a building with a main sanctuary, classrooms for children, a youth center, family counseling rooms and space for community workshops — a place that will serve the next generation.

Every gift, large or small, brings us closer. Thank you for standing with us."""


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

        for i, (name, color, shown, logins, desc) in enumerate(MINISTRIES):
            m, _ = Ministry.objects.get_or_create(
                name=name, defaults={"color": color, "leader_display": shown, "description": desc, "sort_order": i})
            for u in logins:
                m.leaders.add(users[u])

        campaign, created = Campaign.objects.get_or_create(
            slug="new-church-building",
            defaults={
                "name": "New Church Building Fund",
                "tagline": "A permanent home for our families and the next generation.",
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
        self.stdout.write(self.style.WARNING("Added demo donors, gifts and activities. Don't use --demo on the live site."))
