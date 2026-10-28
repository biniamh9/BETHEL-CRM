from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render

from accounts.models import User
from events.models import Event
from fundraising.models import Campaign, Donation
from ministries.models import Activity, GalleryAlbum, GalleryPhoto, Ministry, MinistryInquiry


def home(request):
    today = date.today()
    upcoming = Event.occurrences_between(
        today, today + timedelta(days=45), Event.objects.filter(is_public=True)
    )
    one_time = [occurrence for occurrence in upcoming if occurrence.event.repeat == Event.Repeat.NONE]
    featured_event = next(
        (occurrence for occurrence in one_time if occurrence.event.banner_image_url),
        one_time[0] if one_time else None,
    )
    return render(request, "core/home.html", {
        "featured_event": featured_event,
        "events": [
            occurrence for occurrence in upcoming
            if not featured_event or occurrence.event.pk != featured_event.event.pk
        ][:6],
        "campaign": Campaign.objects.filter(is_active=True, is_public=True).first(),
        "ministries": Ministry.objects.all(),
        "elders": User.objects.filter(is_active=True, role__in=[User.Role.ADMIN, User.Role.ELDER]).order_by("role", "first_name"),
    })


def about(request):
    return render(request, "core/about.html")


def visit(request):
    return render(request, "core/visit.html")


def public_activities(request):
    featured_album = GalleryAlbum.objects.filter(is_public=True, slug="farm-day-at-pettit-creek-farms").prefetch_related("photos").first()
    return render(request, "core/public_activities.html", {
        "gallery_photos": GalleryPhoto.objects.filter(is_public=True).select_related("ministry"),
        "public_activities": Activity.objects.filter(is_public=True).select_related("ministry").prefetch_related("gallery_photos")[:24],
        "featured_album": featured_album,
        "farm_day_photos": featured_album.photos.filter(is_public=True) if featured_album else [],
    })


def gallery_image(request, pk):
    photo = get_object_or_404(GalleryPhoto.objects.select_related("ministry"), pk=pk)
    if not photo.is_public and (
        not request.user.is_authenticated or not request.user.can_view_ministry(photo.ministry)
    ):
        raise Http404
    if photo.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise Http404
    response = HttpResponse(bytes(photo.image_blob), content_type=photo.content_type)
    response["Content-Disposition"] = f'inline; filename="{photo.filename.replace(chr(34), "")}"'
    response["Cache-Control"] = "public, max-age=86400" if photo.is_public else "private, no-store"
    return response


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
        "pending_ministry_inquiries": MinistryInquiry.objects.filter(
            ministry__in=user.visible_ministries(), status=MinistryInquiry.Status.PENDING
        ).select_related("ministry")[:8],
    }
    if user.role == User.Role.MEMBER and not user.is_superuser:
        ctx["my_gifts_total"] = Donation.objects.filter(
            donor__user=user, status=Donation.Status.SUCCEEDED).aggregate(t=Sum("amount"))["t"] or 0
    return render(request, "core/portal.html", ctx)
