from django.conf import settings

from ministries.models import Ministry
from .models import HeroImage


def church(request):
    return {"church": settings.CHURCH}


def public_navigation(request):
    """Supply the ministry submenu on every public page."""
    return {"navigation_ministries": Ministry.objects.filter(is_public=True).only("name", "slug", "color")}


def public_hero_images(request):
    """Make global hero slots available to every public template."""
    return {"hero_images": {item.placement: item for item in HeroImage.objects.filter(placement__in={
        "home_primary", "home_secondary", "about", "visit", "ministries", "activities",
        "events", "resources", "archive", "campaign",
    })}}
