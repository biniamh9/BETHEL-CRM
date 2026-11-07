from datetime import datetime
from zoneinfo import ZoneInfo

from django.db import migrations


SOURCE_NOTE = "Imported from the 2027 Kids & Youth Annual Program."
TZ = ZoneInfo("America/New_York")


PROGRAM = [
    ("2027-01-10", None, "Ministry kickoff, vision sharing & prayer; launch mentorship enrollment", "meeting", False),
    ("2027-02-07", None, "Family meeting: parents, children, teachers & ministry leadership", "meeting", False),
    ("2027-02-13", None, "Kids & youth fellowship; mentorship matching & orientation", "fellowship", False),
    ("2027-03-06", None, "Spring activity 1: nature walk & devotional", "youth", False),
    ("2027-03-14", None, "Quarterly youth-led main church service 1", "service", False),
    ("2027-03-20", None, "Bible quiz & Scripture memorization", "bible", False),
    ("2027-03-27", None, "Spring activity 2: Bible treasure hunt", "youth", False),
    ("2027-03-28", None, "Easter Sunday celebration", "holiday", False),
    ("2027-04-17", None, "Spring activity 3: arts, crafts & fellowship", "fellowship", False),
    ("2027-05-08", None, "Spring activity 4: family picnic & outdoor games", "youth", False),
    ("2027-05-15", None, "Youth community outreach & service day", "outreach", False),
    ("2027-05-22", None, "Family-Children Activity Day: joint games, worship & fellowship", "youth", True),
    ("2027-06-12", None, "Summer activity 1: field day", "youth", False),
    ("2027-06-13", None, "Quarterly youth-led main church service 2", "service", False),
    ("2027-06-20", None, "Graduation Sunday & student recognition", "holiday", False),
    ("2027-06-25", "2027-06-26", "Annual kids & youth camping retreat", "conference", True),
    ("2027-07-10", None, "Summer activity 2: sports & teamwork; conference preparation", "youth", False),
    ("2027-07-29", "2027-07-31", "North America Conference - Dallas, Texas", "conference", True),
    ("2027-08-07", None, "Summer activity 3: water games & outdoor fellowship", "youth", False),
    ("2027-08-14", None, "Back-to-school prayer & youth fellowship", "prayer", False),
    ("2027-08-21", None, "Summer activity 4: back-to-school fun day", "youth", False),
    ("2027-09-05", None, "Sunday School academic year kickoff", "bible", False),
    ("2027-09-12", None, "Quarterly youth-led main church service 3", "service", False),
    ("2027-09-18", None, "Fall activity 1: kids fellowship & games", "fellowship", False),
    ("2027-09-26", None, "Parents & teachers meeting", "meeting", False),
    ("2027-10-09", None, "Fall activity 2: Bible trivia & team competition", "bible", False),
    ("2027-10-16", None, "Youth leadership & spiritual growth workshop", "youth", False),
    ("2027-10-23", None, "Fall activity 3: family fall festival", "fellowship", False),
    ("2027-11-06", None, "Fall activity 4: gratitude & service day", "outreach", False),
    ("2027-11-14", None, "Youth thanksgiving fellowship & reflection", "fellowship", False),
    ("2027-12-12", None, "Quarterly youth-led main church service 4", "service", False),
    ("2027-12-19", None, "Christmas skit & kids celebration", "holiday", False),
    ("2027-12-26", None, "Year-end thanksgiving, recognition & 2028 planning", "meeting", False),
]


def at_midnight(value):
    return datetime.fromisoformat(f"{value}T00:00:00").replace(tzinfo=TZ)


def seed_program(apps, schema_editor):
    Event = apps.get_model("events", "Event")
    Ministry = apps.get_model("ministries", "Ministry")
    ministry = Ministry.objects.filter(slug="youth-kids-ministry").first()
    if not ministry:
        ministry = Ministry.objects.filter(name__icontains="youth").first()
    if not ministry:
        return

    for start_date, end_date, title, kind, proposed in PROGRAM:
        description = SOURCE_NOTE
        if proposed:
            description += " This date is proposed/tentative and requires leadership confirmation."
        Event.objects.get_or_create(
            ministry=ministry,
            title=title,
            start=at_midnight(start_date),
            defaults={
                "end": at_midnight(end_date) if end_date else None,
                "all_day": True,
                "kind": kind,
                "description": description,
                "repeat": "none",
                "is_public": False,
            },
        )

    weekly = [
        ("Sunday School", "2027-01-03T10:30:00", "2027-01-03T12:30:00", "bible"),
        ("Kids & Youth Bible Study", "2027-01-02T18:00:00", "2027-01-02T20:00:00", "bible"),
    ]
    for title, start_value, end_value, kind in weekly:
        start = datetime.fromisoformat(start_value).replace(tzinfo=TZ)
        Event.objects.get_or_create(
            ministry=ministry,
            title=title,
            start=start,
            defaults={
                "end": datetime.fromisoformat(end_value).replace(tzinfo=TZ),
                "kind": kind,
                "description": SOURCE_NOTE,
                "repeat": "weekly",
                "repeat_until": datetime(2027, 12, 31, tzinfo=TZ).date(),
                "is_public": False,
            },
        )


def remove_program(apps, schema_editor):
    Event = apps.get_model("events", "Event")
    Event.objects.filter(description__startswith=SOURCE_NOTE).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0003_event_banner_blob_event_banner_content_type_and_more"),
        ("ministries", "0015_remove_childprofile_sms_consent_delete_parentmessage"),
    ]

    operations = [migrations.RunPython(seed_program, remove_program)]
