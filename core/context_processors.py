from django.conf import settings

from ministries.models import Ministry


def church(request):
    return {"church": settings.CHURCH}


def public_navigation(request):
    """Supply the ministry submenu on every public page."""
    return {"navigation_ministries": Ministry.objects.filter(is_public=True).only("name", "slug", "color")}
