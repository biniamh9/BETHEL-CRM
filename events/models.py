import calendar as pycal
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


@dataclass
class Occurrence:
    """One date on which an event happens (repeating events have many)."""

    event: "Event"
    start: datetime
    end: datetime | None

    @property
    def date(self):
        return self.start.date()

    @property
    def google_url(self):
        return self.event.google_calendar_url(self)


class Event(models.Model):
    class Kind(models.TextChoices):
        SERVICE = "service", "Worship service"
        PRAYER = "prayer", "Prayer"
        BIBLE = "bible", "Bible study"
        REHEARSAL = "rehearsal", "Rehearsal"
        YOUTH = "youth", "Youth & kids"
        MEETING = "meeting", "Meeting"
        FELLOWSHIP = "fellowship", "Fellowship"
        OUTREACH = "outreach", "Outreach"
        CONFERENCE = "conference", "Conference / retreat"
        FUNDRAISER = "fundraiser", "Fundraiser"
        HOLIDAY = "holiday", "Holiday / special day"
        OTHER = "other", "Other"

    class Repeat(models.TextChoices):
        NONE = "none", "Does not repeat"
        WEEKLY = "weekly", "Every week"
        BIWEEKLY = "biweekly", "Every 2 weeks"
        MONTHLY = "monthly", "Every month (same date)"

    title = models.CharField(max_length=150)
    kind = models.CharField("Type", max_length=12, choices=Kind.choices, default=Kind.MEETING)
    ministry = models.ForeignKey(
        "ministries.Ministry", null=True, blank=True, on_delete=models.CASCADE, related_name="events",
        help_text="Leave empty for a church-wide event.",
    )
    start = models.DateTimeField()
    end = models.DateTimeField(null=True, blank=True)
    all_day = models.BooleanField(default=False)
    location = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    banner = models.FileField(
        upload_to="events/%Y/%m/", blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
        help_text="Event flyer or landscape banner (JPG, PNG, or WebP).",
    )
    banner_url = models.URLField(
        blank=True, help_text="Alternatively, link to an approved externally hosted flyer image.",
    )
    repeat = models.CharField(max_length=10, choices=Repeat.choices, default=Repeat.NONE)
    repeat_until = models.DateField(null=True, blank=True, help_text="Last date it repeats. Leave empty to repeat indefinitely.")
    is_public = models.BooleanField("Show on the public website", default=False, help_text="Visitors will see it on the Events page and home page.")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("events:detail", args=[self.pk])

    def clean(self):
        if self.end and self.start and self.end < self.start:
            raise ValidationError("The end must be after the start.")
        if self.banner and self.banner.size > 4 * 1024 * 1024:
            raise ValidationError({"banner": "Event images must be 4 MB or smaller."})

    @property
    def banner_image_url(self):
        if self.banner:
            try:
                return self.banner.url
            except (NotImplementedError, ValueError):
                pass
        return self.banner_url

    @property
    def color(self):
        return self.ministry.color if self.ministry else "maroon"

    @property
    def duration(self):
        return (self.end - self.start) if self.end else None

    def occurrences(self, first: date, last: date):
        """Every occurrence with a start date between `first` and `last` (inclusive)."""
        start = timezone.localtime(self.start)
        out = []
        if self.repeat == self.Repeat.NONE:
            if first <= start.date() <= last:
                out.append(Occurrence(self, start, timezone.localtime(self.end) if self.end else None))
            return out
        stop = min(last, self.repeat_until) if self.repeat_until else last
        dur = self.duration
        current = start
        if self.repeat in (self.Repeat.WEEKLY, self.Repeat.BIWEEKLY):
            step = timedelta(weeks=1 if self.repeat == self.Repeat.WEEKLY else 2)
            if current.date() < first:  # jump close to the window instead of looping from the beginning
                skips = (first - current.date()).days // step.days
                current = current + step * skips
            while current.date() <= stop:
                if current.date() >= first:
                    out.append(Occurrence(self, current, current + dur if dur else None))
                current += step
        else:  # monthly on the same day number
            y, m = start.year, start.month
            if date(y, m, 1) < date(first.year, first.month, 1):
                y, m = first.year, first.month
            while date(y, m, 1) <= stop:
                if start.day <= pycal.monthrange(y, m)[1]:
                    occ = start.replace(year=y, month=m)
                    if first <= occ.date() <= stop and occ >= start:
                        out.append(Occurrence(self, occ, occ + dur if dur else None))
                y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        return out

    @classmethod
    def occurrences_between(cls, first: date, last: date, queryset=None):
        qs = (queryset if queryset is not None else cls.objects.all()).select_related("ministry")
        tz = timezone.get_current_timezone()
        last_dt = timezone.make_aware(datetime.combine(last, datetime.max.time()), tz)
        first_d = first
        qs = qs.filter(start__lte=last_dt).filter(
            models.Q(repeat=cls.Repeat.NONE, start__gte=timezone.make_aware(datetime.combine(first_d, datetime.min.time()), tz))
            | (~models.Q(repeat=cls.Repeat.NONE) & (models.Q(repeat_until__isnull=True) | models.Q(repeat_until__gte=first_d)))
        )
        occ = [o for e in qs for o in e.occurrences(first, last)]
        return sorted(occ, key=lambda o: o.start)

    def google_calendar_url(self, occurrence=None):
        from urllib.parse import urlencode

        s = occurrence.start if occurrence else timezone.localtime(self.start)
        e = (occurrence.end if occurrence else (timezone.localtime(self.end) if self.end else None)) or s + timedelta(hours=1)
        fmt = "%Y%m%d" if self.all_day else "%Y%m%dT%H%M%S"
        params = {
            "action": "TEMPLATE", "text": self.title,
            "dates": f"{s:{fmt}}/{(e + timedelta(days=1) if self.all_day else e):{fmt}}",
            "details": self.description, "location": self.location, "ctz": settings.TIME_ZONE,
        }
        return "https://calendar.google.com/calendar/render?" + urlencode(params)
