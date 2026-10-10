from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """A person who can log in. The role decides what they can see.

    - admin:   Pastor / church administrator. Sees and manages everything.
    - finance: CFO / treasurer. Manages the building fund and donor records.
    - elder:   Eldership board. Sees every ministry and fundraising totals.
    - leader:  Ministry leader. Manages only the ministries they are assigned to.
    - member:  Church member. Sees their own profile and giving history.
    """

    class Role(models.TextChoices):
        ADMIN = "admin", "Pastor / Administrator"
        FINANCE = "finance", "Finance (CFO / Treasurer)"
        ELDER = "elder", "Elder"
        LEADER = "leader", "Ministry Leader"
        MEMBER = "member", "Member"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    title = models.CharField(max_length=80, blank=True, help_text="Shown on the team page, e.g. 'Elder / Secretary'.")
    phone = models.CharField(max_length=30, blank=True)

    class Meta:
        ordering = ["first_name", "last_name"]

    def __str__(self):
        return self.get_full_name() or self.username

    # ---- permission helpers used across the site ----
    @property
    def is_church_admin(self):
        return self.is_superuser or self.role == self.Role.ADMIN

    @property
    def can_manage_users(self):
        return self.is_church_admin

    @property
    def can_manage_finance(self):
        """Record donations and see individual donor names and amounts."""
        return self.is_church_admin or self.role == self.Role.FINANCE

    @property
    def can_view_fund_totals(self):
        return self.can_manage_finance or self.role == self.Role.ELDER

    @property
    def can_see_all_ministries(self):
        return self.is_church_admin or self.role == self.Role.ELDER

    def can_edit_ministry(self, ministry):
        return self.is_church_admin or ministry.leaders.filter(pk=self.pk).exists()

    def can_view_ministry(self, ministry):
        return self.can_see_all_ministries or self.can_edit_ministry(ministry)

    def visible_ministries(self):
        from ministries.models import Ministry

        if self.can_see_all_ministries:
            return Ministry.objects.all()
        return Ministry.objects.filter(leaders=self)
