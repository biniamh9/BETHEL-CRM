from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
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


class BirthdayCelebration(models.Model):
    """A consented birthday post with explicit public or members-only visibility."""

    class Visibility(models.TextChoices):
        MEMBERS = "members", "Members only"
        PUBLIC = "public", "Public celebration"

    ministry = models.ForeignKey(Ministry, on_delete=models.CASCADE, related_name="birthday_celebrations")
    child_profile = models.ForeignKey(
        "ChildProfile", null=True, blank=True, on_delete=models.PROTECT, related_name="birthday_celebrations",
        help_text="Optional private roster profile used to prefill the celebration.",
    )
    member_name = models.CharField(max_length=120)
    celebration_date = models.DateField(
        help_text="The celebration date for this post. The year is not shown to members as an age."
    )
    message = models.TextField(max_length=800, blank=True)
    image_blob = models.BinaryField(editable=False, blank=True, default=b"")
    image_content_type = models.CharField(max_length=30, editable=False, blank=True)
    image_filename = models.CharField(max_length=180, editable=False, blank=True)
    consent_confirmed = models.BooleanField(
        default=False,
        help_text="Confirm the member, or a parent/guardian for a child, approved the selected visibility and social sharing.",
    )
    visibility = models.CharField(max_length=12, choices=Visibility.choices, default=Visibility.MEMBERS, db_index=True)
    is_active = models.BooleanField("Published", default=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_birthday_celebrations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-celebration_date", "-created_at"]

    def __str__(self):
        return f"{self.member_name} — {self.celebration_date:%B %d}"

    def get_absolute_url(self):
        return reverse("ministries:birthday_detail", args=[self.pk])

    def get_public_url(self):
        return reverse("public_ministries:birthday_detail", args=[self.pk])

    def get_image_url(self):
        return reverse("ministries:birthday_image", args=[self.pk])

    def get_public_image_url(self):
        return reverse("public_ministries:birthday_image", args=[self.pk])


class BirthdayWish(models.Model):
    celebration = models.ForeignKey(BirthdayCelebration, on_delete=models.CASCADE, related_name="wishes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="birthday_wishes")
    message = models.TextField(max_length=600)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class BirthdayReaction(models.Model):
    class Kind(models.TextChoices):
        LOVE = "love", "Love"
        CELEBRATE = "celebrate", "Celebrate"
        BLESSING = "blessing", "Blessing"

    celebration = models.ForeignKey(BirthdayCelebration, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="birthday_reactions")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("celebration", "user"), name="one_birthday_reaction_per_member")]


class StudentAchievement(models.Model):
    """A guardian-approved school recognition shared without private student details."""

    class Kind(models.TextChoices):
        ACADEMIC = "academic", "Academic excellence"
        HONOR_ROLL = "honor_roll", "Honor roll"
        LEADERSHIP = "leadership", "Leadership"
        ATTENDANCE = "attendance", "Attendance"
        ARTS = "arts", "Arts / music"
        STEM = "stem", "STEM"
        SPORTS = "sports", "Sports"
        CHARACTER = "character", "Character / service"
        OTHER = "other", "Other recognition"

    class Visibility(models.TextChoices):
        MEMBERS = "members", "Members only"
        PUBLIC = "public", "Public achievement corner"

    ministry = models.ForeignKey(Ministry, on_delete=models.CASCADE, related_name="student_achievements")
    child_profile = models.ForeignKey(
        "ChildProfile", null=True, blank=True, on_delete=models.PROTECT, related_name="student_achievements",
        help_text="Optional private roster profile used to prefill the approved display name and photo.",
    )
    student_name = models.CharField(
        max_length=120,
        help_text="Use the child’s approved display name. Do not include age, grade, or school name.",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.ACADEMIC)
    recognition_title = models.CharField(max_length=180, help_text="For example: Principal’s List or Reading Award.")
    recognition_date = models.DateField()
    academic_year = models.CharField(max_length=20, blank=True, help_text="Optional, for example 2026–2027.")
    message = models.TextField(
        max_length=1000, blank=True,
        help_text="A short congratulatory message from the church or Kids & Youth Ministry.",
    )
    image_blob = models.BinaryField(editable=False, blank=True, default=b"")
    image_content_type = models.CharField(max_length=30, editable=False, blank=True)
    image_filename = models.CharField(max_length=180, editable=False, blank=True)
    consent_confirmed = models.BooleanField(
        default=False,
        help_text="Confirm a parent or legal guardian approved the name, photo, message, and selected visibility.",
    )
    visibility = models.CharField(max_length=12, choices=Visibility.choices, default=Visibility.MEMBERS, db_index=True)
    is_active = models.BooleanField("Published", default=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_student_achievements")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-recognition_date", "-created_at"]

    def __str__(self):
        return f"{self.student_name} — {self.recognition_title}"

    def get_absolute_url(self):
        return reverse("ministries:achievement_list")

    def get_image_url(self):
        return reverse("ministries:achievement_image", args=[self.pk])

    def get_public_image_url(self):
        return reverse("public_ministries:achievement_image", args=[self.pk])


class ChildProfile(models.Model):
    """Private pastoral record for a child or youth; never exposed on public pages."""

    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"

    class Grade(models.TextChoices):
        INFANT = "infant", "Infant / nursery"
        PREK = "prek", "Pre-K"
        K = "k", "Kindergarten"
        G1 = "1", "1st grade"
        G2 = "2", "2nd grade"
        G3 = "3", "3rd grade"
        G4 = "4", "4th grade"
        G5 = "5", "5th grade"
        G6 = "6", "6th grade"
        G7 = "7", "7th grade"
        G8 = "8", "8th grade"
        G9 = "9", "9th grade"
        G10 = "10", "10th grade"
        G11 = "11", "11th grade"
        G12 = "12", "12th grade"
        GRADUATED = "graduated", "Graduated"

    ministry = models.ForeignKey(Ministry, on_delete=models.PROTECT, related_name="child_profiles")
    first_name = models.CharField(max_length=80)
    middle_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80)
    birth_date = models.DateField(db_index=True)
    gender = models.CharField(max_length=8, choices=Gender.choices)
    grade = models.CharField(max_length=12, choices=Grade.choices, db_index=True)
    mother_name = models.CharField(max_length=160, blank=True)
    father_or_guardian_name = models.CharField("Father or guardian name", max_length=160, blank=True)
    primary_phone = models.CharField(max_length=30, help_text="Parent or guardian mobile number.")
    secondary_phone = models.CharField(max_length=30, blank=True)
    parent_email = models.EmailField(blank=True)
    address_line = models.CharField("Street address", max_length=220, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=40, blank=True, default="GA")
    postal_code = models.CharField(max_length=15, blank=True)
    allergy_notes = models.TextField(blank=True, help_text="Allergies, emergency considerations, or 'None known'.")
    emergency_contact = models.CharField(max_length=160, blank=True)
    emergency_phone = models.CharField(max_length=30, blank=True)
    photo_blob = models.BinaryField(editable=False, blank=True, default=b"")
    photo_content_type = models.CharField(max_length=30, editable=False, blank=True)
    photo_filename = models.CharField(max_length=180, editable=False, blank=True)
    sms_consent = models.BooleanField(
        default=False,
        help_text="Parent/guardian expressly opted in to occasional Bethel Kids & Youth SMS updates; message/data rates may apply; reply STOP to opt out or HELP for help.",
    )
    email_consent = models.BooleanField(default=False)
    photo_consent = models.BooleanField(default=False, help_text="Photo may be used for approved church purposes.")
    consent_recorded_on = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    notes = models.TextField(blank=True, help_text="Private ministry notes. Do not add unnecessary sensitive information.")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_child_profiles")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["first_name", "last_name"]
        constraints = [models.UniqueConstraint(fields=("first_name", "last_name", "birth_date"), name="unique_child_identity")]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return " ".join(part for part in (self.first_name, self.middle_name, self.last_name) if part)

    @property
    def age(self):
        today = timezone.localdate()
        return today.year - self.birth_date.year - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))

    @property
    def ministry_group(self):
        if self.grade in {self.Grade.INFANT, self.Grade.PREK}:
            return "Infant–Pre-K"
        if self.grade in {self.Grade.K, self.Grade.G1, self.Grade.G2}:
            return "K–2nd grade"
        if self.grade in {self.Grade.G3, self.Grade.G4, self.Grade.G5}:
            return "3rd–5th grade"
        if self.grade in {self.Grade.G6, self.Grade.G7, self.Grade.G8}:
            return "Middle school (6th–8th)"
        return "Youth Ministry / high school"

    def get_image_url(self):
        return reverse("ministries:child_image", args=[self.pk])


class PromotionRecognition(models.Model):
    """Annual June transfer recognition for children advancing ministry groups."""

    child = models.ForeignKey(ChildProfile, on_delete=models.PROTECT, related_name="promotion_recognitions")
    ceremony_date = models.DateField(help_text="Usually the first Sunday in June.")
    academic_year = models.CharField(max_length=20, help_text="For example 2026–2027.")
    from_group = models.CharField(max_length=80)
    to_group = models.CharField(max_length=80)
    certificate_prepared = models.BooleanField(default=False)
    gift_prepared = models.BooleanField(default=False)
    presented = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_promotion_recognitions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-ceremony_date", "child__first_name"]
        constraints = [models.UniqueConstraint(fields=("child", "ceremony_date"), name="one_promotion_per_child_ceremony")]


class ParentMessage(models.Model):
    """Consent-aware communication record; delivery requires configured SMS credentials."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        PARTIAL = "partial", "Partially sent"
        FAILED = "failed", "Failed"

    ministry = models.ForeignKey(Ministry, on_delete=models.PROTECT, related_name="parent_messages")
    subject = models.CharField(max_length=140)
    body = models.TextField(max_length=1200)
    recipients = models.ManyToManyField(ChildProfile, related_name="parent_messages", blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    delivery_summary = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_parent_messages")
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


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
