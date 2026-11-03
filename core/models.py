from django.conf import settings
from django.db import models
from django.urls import reverse


class HeroImage(models.Model):
    """An administrator-managed hero image stored in Postgres for Vercel safety."""

    placement = models.CharField(max_length=120, unique=True)
    image_blob = models.BinaryField()
    content_type = models.CharField(max_length=50, default="image/jpeg")
    filename = models.CharField(max_length=190)
    alt_text = models.CharField(max_length=220, blank=True)
    position = models.CharField(max_length=30, default="center center")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="updated_hero_images",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("placement",)

    def __str__(self):
        return self.placement

    @property
    def image_url(self):
        return reverse("core:hero_image", args=[self.pk])
