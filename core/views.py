from datetime import date, timedelta
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import render
from django.conf import settings

from accounts.models import User
from events.models import Event
from fundraising.models import Campaign, Donation
from ministries.models import Activity, Ministry


def home(request):
    today = date.today()
    return render(request, "core/home.html", {
        "events": Event.occurrences_between(today, today + timedelta(days=45), Event.objects.filter(is_public=True))[:6],
        "campaign": Campaign.objects.filter(is_active=True, is_public=True).first(),
        "ministries": Ministry.objects.all(),
        "elders": User.objects.filter(is_active=True, role__in=[User.Role.ADMIN, User.Role.ELDER]).order_by("role", "first_name"),
    })


def public_activities(request):
    image_root = Path(settings.BASE_DIR) / "images"
    allowed = {".jpg", ".jpeg", ".png", ".webp"}
    images = [
        f"activity-images/{item.name}" for item in sorted(image_root.iterdir())
        if item.is_file() and item.suffix.lower() in allowed
    ] if image_root.is_dir() else []
    return render(request, "core/public_activities.html", {"activity_images": images})


@login_required
def portal(request):
    user = request.user
    since = date.today() - timedelta(days=30)
    ministries = user.visible_ministries().annotate(
        recent_count=Count("activities", filter=Q(activities__date__gte=since), distinct=True),
        recent_attendance=Sum("activities__attendance", filter=Q(activities__date__gte=since)),
        people=Count("participants", filter=Q(participants__is_active=True), distinct=True),
    )
    feed = Activity.objects.filter(ministry__in=user.visible_ministries()).select_related("ministry", "created_by")[:12]
    ctx = {
        "ministries": ministries,
        "my_ministries": user.led_ministries.all(),
        "feed": feed,
        "campaign": Campaign.objects.filter(is_active=True).first(),
        "month_activities": Activity.objects.filter(ministry__in=user.visible_ministries(), date__gte=since).count(),
        "upcoming": Event.occurrences_between(date.today(), date.today() + timedelta(days=14))[:8],
    }
    if user.role == User.Role.MEMBER and not user.is_superuser:
        ctx["my_gifts_total"] = Donation.objects.filter(
            donor__user=user, status=Donation.Status.SUCCEEDED).aggregate(t=Sum("amount"))["t"] or 0
    return render(request, "core/portal.html", ctx)
