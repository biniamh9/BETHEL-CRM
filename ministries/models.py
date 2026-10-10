from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Ministry(models.Model):
    COLORS = [
        ("blue", "Blue"), ("green", "Green"), ("purple", "Purple"), ("gold", "Gold"),
        ("red", "Red"), ("teal", "Teal"), ("orange", "Orange"), ("navy", "Navy"),
    ]

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True, blank=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=10, choices=COLORS, default="navy")
    leader_display = models.CharField(
        max_length=100, blank=True, help_text="Leader name as shown publicly (e.g. 'Leader TBD')."
    )
    leaders = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="led_ministries", blank=True,
        help_text="People who can log in and manage this ministry's portal.",
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "ministries"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("ministries:detail", args=[self.slug])


class Participant(models.Model):
    """Someone a ministry serves or works with: a choir singer, a youth, a family."""

    class Kind(models.TextChoices):
        MEMBER = "member", "Team member / volunteer"
        CHILD = "child", "Child"
        YOUTH = "youth", "Youth / student"
        ADULT = "adult", "Adult participant"
        FAMILY = "family", "Family"
        VISITOR = "visitor", "Visitor / contact"

    ministry = models.ForeignKey(Ministry, on_delete=models.CASCADE, related_name="participants")
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.MEMBER)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    guardian_name = models.CharField(max_length=120, blank=True, help_text="For children and youth.")
    guardian_phone = models.CharField(max_length=30, blank=True)
    birth_year = models.PositiveSmallIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    joined_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["first_name", "last_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()


class Activity(models.Model):
    """One record of what a ministry did: a rehearsal, a class, a visit, an outreach."""

    class Kind(models.TextChoices):
        SERVICE = "service", "Worship service"
        MEETING = "meeting", "Meeting"
        CLASS = "class", "Class / Bible study"
        REHEARSAL = "rehearsal", "Rehearsal / practice"
        EVENT = "event", "Event / program"
        OUTREACH = "outreach", "Outreach / evangelism"
        VISIT = "visit", "Home or hospital visit"
        COUNSELING = "counseling", "Counseling / support"
        PRAYER = "prayer", "Prayer gathering"
        MEDIA = "media", "Media production"
        FUNDRAISER = "fundraiser", "Fundraiser"
        OTHER = "other", "Other"

    ministry = models.ForeignKey(Ministry, on_delete=models.CASCADE, related_name="activities")
    title = models.CharField(max_length=150)
    kind = models.CharField("Type", max_length=12, choices=Kind.choices, default=Kind.MEETING)
    date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=150, blank=True)
    attendance = models.PositiveIntegerField(default=0, help_text="Head count.")
    attendees = models.ManyToManyField(Participant, blank=True, related_name="activities")
    volunteer_hours = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    summary = models.TextField(blank=True, help_text="What happened, decisions, prayer requests, follow-ups.")
    follow_up = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name_plural = "activities"

    def __str__(self):
        return f"{self.ministry}: {self.title} ({self.date})"

    @property
    def head_count(self):
        return max(self.attendance, self.attendees.count()) if self.pk else self.attendance
