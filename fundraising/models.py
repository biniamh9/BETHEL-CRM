from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Count, Q, Sum
from django.urls import reverse
from django.utils.text import slugify

ZERO = Decimal("0")


class Campaign(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, unique=True, blank=True)
    tagline = models.CharField(max_length=200, blank=True)
    story = models.TextField(blank=True, help_text="Why this campaign matters. Paragraphs are separated by blank lines.")
    goal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    opening_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Money already saved before online tracking started (counted toward the goal).",
    )
    opening_balance_label = models.CharField(max_length=120, default="Saved by members before the campaign")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True, help_text="Show on the public giving page.")
    show_donor_wall = models.BooleanField(default=True, help_text="List names of donors who agreed to be shown.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_active", "-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("fundraising:campaign", args=[self.slug])

    # ---- progress numbers ----
    def succeeded(self):
        return self.donations.filter(status=Donation.Status.SUCCEEDED)

    @property
    def donated(self):
        return self.succeeded().aggregate(t=Sum("amount"))["t"] or ZERO

    @property
    def raised(self):
        return self.opening_balance + self.donated

    @property
    def remaining(self):
        return max(self.goal_amount - self.raised, ZERO)

    @property
    def percent(self):
        if not self.goal_amount:
            return 0
        return min(round(float(self.raised / self.goal_amount * 100), 1), 100)

    @property
    def donor_count(self):
        return self.succeeded().exclude(donor=None).values("donor").distinct().count()

    @property
    def pledged_total(self):
        return self.pledges.exclude(status=Pledge.Status.CANCELLED).aggregate(t=Sum("total_amount"))["t"] or ZERO

    @property
    def pledged_outstanding(self):
        return sum((p.remaining for p in self.pledges.filter(status=Pledge.Status.ACTIVE)), ZERO)


class Donor(models.Model):
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True)
    organization = models.CharField(max_length=150, blank=True, help_text="For business or church partners.")
    email = models.EmailField(blank=True, db_index=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=80, blank=True)
    state = models.CharField(max_length=40, blank=True, default="GA")
    postal_code = models.CharField(max_length=15, blank=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="donor_profile",
        help_text="Link to a member login so they can see their own giving history.",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["first_name", "last_name"]

    def __str__(self):
        name = f"{self.first_name} {self.last_name}".strip()
        return f"{name} ({self.organization})" if self.organization else name

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def public_name(self):
        return f"{self.first_name} {self.last_name[:1]}.".strip() if self.last_name else self.first_name

    def get_absolute_url(self):
        return reverse("fundraising:donor_detail", args=[self.pk])

    @property
    def lifetime_total(self):
        return self.donations.filter(status=Donation.Status.SUCCEEDED).aggregate(t=Sum("amount"))["t"] or ZERO

    @classmethod
    def find_or_create(cls, first_name, last_name="", email="", phone=""):
        """Reuse an existing donor with the same email so giving history stays together."""
        donor = cls.objects.filter(email__iexact=email).first() if email else None
        if donor is None:
            donor = cls.objects.create(first_name=first_name, last_name=last_name, email=email, phone=phone)
            if email:
                from accounts.models import User

                user = User.objects.filter(email__iexact=email, donor_profile=None).first()
                if user:
                    donor.user = user
                    donor.save(update_fields=["user"])
        elif phone and not donor.phone:
            donor.phone = phone
            donor.save(update_fields=["phone"])
        return donor

    @classmethod
    def with_totals(cls):
        ok = Q(donations__status=Donation.Status.SUCCEEDED)
        return cls.objects.annotate(total=Sum("donations__amount", filter=ok), gifts=Count("donations", filter=ok))


class Pledge(models.Model):
    class Frequency(models.TextChoices):
        ONE_TIME = "one_time", "One-time gift"
        MONTHLY = "monthly", "Monthly"
        QUARTERLY = "quarterly", "Quarterly"
        ANNUALLY = "annually", "Annually"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    donor = models.ForeignKey(Donor, on_delete=models.CASCADE, related_name="pledges")
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="pledges")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, help_text="Total committed over the pledge period.")
    frequency = models.CharField(max_length=10, choices=Frequency.choices, default=Frequency.ONE_TIME)
    start_date = models.DateField()
    target_date = models.DateField(null=True, blank=True, help_text="When the pledge should be fully paid.")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.donor} — ${self.total_amount:,.0f} ({self.get_frequency_display()})"

    @property
    def fulfilled(self):
        return self.donations.filter(status=Donation.Status.SUCCEEDED).aggregate(t=Sum("amount"))["t"] or ZERO

    @property
    def remaining(self):
        return max(self.total_amount - self.fulfilled, ZERO)

    @property
    def percent(self):
        return min(round(float(self.fulfilled / self.total_amount * 100)), 100) if self.total_amount else 0

    def refresh_status(self):
        if self.status == self.Status.ACTIVE and self.remaining == 0:
            self.status = self.Status.COMPLETED
            self.save(update_fields=["status"])


class Donation(models.Model):
    class Method(models.TextChoices):
        ONLINE = "online", "Online (Stripe)"
        CASH = "cash", "Cash"
        CHECK = "check", "Check"
        ZELLE = "zelle", "Zelle"
        TRANSFER = "transfer", "Bank transfer / ACH"
        CASHAPP = "cashapp", "Cash App / Venmo / PayPal"
        STOCK = "stock", "Stock / in-kind"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Received"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    campaign = models.ForeignKey(Campaign, on_delete=models.PROTECT, related_name="donations")
    donor = models.ForeignKey(
        Donor, null=True, blank=True, on_delete=models.SET_NULL, related_name="donations",
        help_text="Leave empty for an anonymous cash gift.",
    )
    pledge = models.ForeignKey(Pledge, null=True, blank=True, on_delete=models.SET_NULL, related_name="donations")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=10, choices=Method.choices, default=Method.CASH)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SUCCEEDED)
    received_on = models.DateField()
    reference = models.CharField(max_length=120, blank=True, help_text="Check number, Zelle confirmation, etc.")
    show_on_wall = models.BooleanField("Show name on donor wall", default=False, help_text="Donor agreed to have their name shown publicly.")
    public_message = models.CharField(max_length=280, blank=True)
    stripe_session_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    stripe_payment_intent = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_on", "-created_at"]

    def __str__(self):
        return f"${self.amount:,.2f} from {self.donor or 'Anonymous'} on {self.received_on}"

    @property
    def receipt_number(self):
        return f"BEC-{self.received_on:%Y}-{self.pk:05d}"

    def mark_succeeded(self, payment_intent=""):
        if self.status != self.Status.SUCCEEDED:
            self.status = self.Status.SUCCEEDED
            if payment_intent:
                self.stripe_payment_intent = payment_intent
            self.save(update_fields=["status", "stripe_payment_intent"])
            if self.pledge:
                self.pledge.refresh_status()
