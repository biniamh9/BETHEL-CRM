import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Q

ALLOWED_EXTENSIONS = [
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv", "rtf", "odt",
    "jpg", "jpeg", "png", "gif", "webp", "heic", "mp3", "m4a", "wav", "mp4", "mov", "zip",
]


def validate_size(f):
    limit = getattr(settings, "MAX_UPLOAD_MB", 25)
    if f.size > limit * 1024 * 1024:
        raise ValidationError(f"Files must be {limit} MB or smaller. For larger files, upload to Google Drive or YouTube and add the link instead.")


class Resource(models.Model):
    class Category(models.TextChoices):
        DOCUMENT = "document", "Document"
        FORM = "form", "Form / template"
        CURRICULUM = "curriculum", "Lesson / curriculum"
        SERMON = "sermon", "Sermon / teaching"
        SONG = "song", "Song / lyrics / sheet music"
        POLICY = "policy", "Policy / governance"
        MEDIA = "media", "Photos / video"
        LINK = "link", "Website / link"
        OTHER = "other", "Other"

    class Audience(models.TextChoices):
        MEMBERS = "members", "Everyone with a login"
        LEADERS = "leaders", "Leadership only (pastor, elders, finance, ministry leaders)"
        MINISTRY = "ministry", "Only this ministry's leaders (plus pastor and elders)"

    title = models.CharField(max_length=150)
    category = models.CharField(max_length=12, choices=Category.choices, default=Category.DOCUMENT)
    ministry = models.ForeignKey("ministries.Ministry", null=True, blank=True, on_delete=models.CASCADE,
                                 related_name="resources", help_text="Leave empty for church-wide resources.")
    audience = models.CharField(max_length=10, choices=Audience.choices, default=Audience.MEMBERS)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to="resources/%Y/%m/", blank=True,
                            validators=[FileExtensionValidator(ALLOWED_EXTENSIONS), validate_size])
    url = models.URLField(blank=True, verbose_name="Link", help_text="Google Drive, YouTube, website, etc.")
    pinned = models.BooleanField(default=False, help_text="Keep at the top of the list.")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-pinned", "-created_at"]

    def __str__(self):
        return self.title

    def clean(self):
        if not self.file and not self.url:
            raise ValidationError("Attach a file or add a link.")
        if self.audience == self.Audience.MINISTRY and not self.ministry:
            raise ValidationError({"audience": "Choose a ministry for 'Only this ministry' resources."})

    @property
    def filename(self):
        return os.path.basename(self.file.name) if self.file else ""

    @property
    def extension(self):
        return os.path.splitext(self.file.name)[1].lstrip(".").upper() if self.file else ""

    @classmethod
    def visible_to(cls, user):
        qs = cls.objects.select_related("ministry", "uploaded_by")
        if user.can_see_all_ministries:
            return qs
        allowed = Q(audience=cls.Audience.MEMBERS) | Q(uploaded_by=user)
        if user.is_leadership:
            allowed |= Q(audience=cls.Audience.LEADERS)
            allowed |= Q(audience=cls.Audience.MINISTRY, ministry__leaders=user)
        return qs.filter(allowed).distinct()

    def can_edit(self, user):
        if user.is_church_admin or self.uploaded_by_id == user.pk:
            return True
        return bool(self.ministry_id) and user.can_edit_ministry(self.ministry)
