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
    mission = models.TextField(blank=True)
    serves = models.TextField(blank=True, help_text="Who this ministry serves.")
    regular_activities = models.TextField(blank=True)
    participation = models.TextField(blank=True, help_text="How visitors can participate.")
    cash_app = models.CharField(
        "Cash App ID", max_length=100, blank=True,
        help_text="Public $Cashtag only (for example, $BethelYouth). Never enter a password or bank information.",
    )
    zelle = models.CharField(
        "Zelle ID", max_length=100, blank=True,
        help_text="Public Zelle email address or phone number only. Never enter a password or bank information.",
    )
    is_public = models.BooleanField(default=True, db_index=True)
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

    def get_public_url(self):
        return reverse("public_ministries:detail", args=[self.slug])

    @property
    def accepts_external_payments(self):
        return bool(self.cash_app or self.zelle)


class MinistryAnnouncement(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW = "review", "Pending review"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    ministry = models.ForeignKey(Ministry, on_delete=models.CASCADE, related_name="announcements")
    title = models.CharField(max_length=160)
    body = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class MinistryInquiry(models.Model):
    class Kind(models.TextChoices):
        CONTACT = "contact", "Contact ministry"
        JOIN = "join", "Join ministry"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONTACTED = "contacted", "Contacted"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"

    ministry = models.ForeignKey(Ministry, on_delete=models.CASCADE, related_name="inquiries")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    name = models.CharField(max_length=160)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    area_interest = models.CharField(max_length=160, blank=True)
    message = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["ministry", "kind", "status"])]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.name} — {self.ministry}"


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


class MinistryMemberSpotlight(models.Model):
    """An explicitly approved public introduction, separate from the private roster."""

    ministry = models.ForeignKey(Ministry, on_delete=models.CASCADE, related_name="member_spotlights")
    display_name = models.CharField(max_length=120)
    role = models.CharField(max_length=120, blank=True, help_text="For example: Choir member or Youth volunteer.")
    short_message = models.TextField(max_length=500, help_text="A short welcome, testimony, or ministry message.")
    image_blob = models.BinaryField(editable=False, blank=True, default=b"")
    image_content_type = models.CharField(max_length=30, editable=False, blank=True)
    image_filename = models.CharField(max_length=180, editable=False, blank=True)
    is_public = models.BooleanField(
        default=False, db_index=True,
        help_text="Publish this profile on the ministry page. Confirm the member or guardian has approved it.",
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "display_name"]

    def __str__(self):
        return f"{self.display_name} — {self.ministry}"

    def get_image_url(self):
        return reverse("public_ministries:member_image", args=[self.ministry.slug, self.pk])


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
    is_public = models.BooleanField(
        default=False, db_index=True,
        help_text="Show this activity on the public website. Never publish private follow-up notes.",
    )
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


class GalleryAlbum(models.Model):
    ministry = models.ForeignKey(Ministry, on_delete=models.CASCADE, related_name="gallery_albums")
    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    event_date = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=160, blank=True)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-event_date", "title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title) or "album"
            slug = base
            counter = 2
            while GalleryAlbum.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class GalleryPhoto(models.Model):
    class Occasion(models.TextChoices):
        CONFERENCE = "conference", "Conference"
        OUTDOOR = "outdoor", "Outdoor activity"
        WORSHIP = "worship", "Worship"
        FELLOWSHIP = "fellowship", "Fellowship"
        YOUTH = "youth", "Kids & youth"
        MINISTRY = "ministry", "Ministry activity"
        OTHER = "other", "Other"

    ministry = models.ForeignKey(Ministry, on_delete=models.CASCADE, related_name="gallery_photos")
    album = models.ForeignKey(
        GalleryAlbum, null=True, blank=True, on_delete=models.CASCADE, related_name="photos",
    )
    activity = models.ForeignKey(
        Activity, null=True, blank=True, on_delete=models.CASCADE, related_name="gallery_photos",
        help_text="Optional activity this photo belongs to.",
    )
    caption = models.CharField(max_length=220)
    occasion = models.CharField(max_length=20, choices=Occasion.choices)
    year = models.PositiveSmallIntegerField(db_index=True)
    image_blob = models.BinaryField(editable=False, blank=True, default=b"")
    static_path = models.CharField(max_length=255, blank=True, editable=False)
    content_type = models.CharField(max_length=30, editable=False)
    filename = models.CharField(max_length=180, editable=False)
    is_public = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["occasion", "-year", "-created_at"]

    def __str__(self):
        return f"{self.caption} ({self.year})"

    def get_image_url(self):
        if self.static_path:
            from django.contrib.staticfiles.storage import staticfiles_storage
            return staticfiles_storage.url(self.static_path)
        return reverse("core:gallery_image", args=[self.pk])
