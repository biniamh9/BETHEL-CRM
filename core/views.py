from datetime import date, timedelta
import logging

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import User
from events.models import Event
from fundraising.models import Campaign, Donation
from ministries.models import Activity, BirthdayCelebration, GalleryAlbum, GalleryPhoto, Ministry, MinistryInquiry
from accounts.decorators import admin_required
from .forms import HeroImageForm
from .image_processing import ImageProcessingError, optimize_image_upload, validate_image_upload
from .models import HeroImage

logger = logging.getLogger(__name__)

GLOBAL_HERO_SLOTS = (
    ("home_primary", "Homepage — first slideshow image", "The main homepage photograph."),
    ("home_secondary", "Homepage — second slideshow image", "The alternate homepage photograph."),
    ("about", "About page", "The image behind the About page introduction."),
    ("visit", "Plan your visit page", "The image behind visitor information."),
    ("ministries", "Ministries page", "The image above the ministry directory."),
    ("activities", "Activities page", "The image above church-life galleries."),
    ("events", "Events page", "The image above upcoming events."),
    ("resources", "Resources page", "The image above teachings and downloads."),
    ("archive", "Event archive", "The image above past events and photo stories."),
    ("campaign", "Building fund page", "The image above the church building campaign."),
)


def _hero_slots():
    slots = list(GLOBAL_HERO_SLOTS)
    slots.extend(
        (f"ministry:{ministry.slug}", f"{ministry.name} — ministry page", "The ministry page hero photograph.")
        for ministry in Ministry.objects.filter(is_public=True).only("name", "slug")
    )
    return slots


def csrf_failure(request, reason=""):
    """Give portal users a recoverable response while preserving CSRF protection."""
    logger.warning("CSRF rejected %s %s: %s", request.method, request.path, reason)
    return render(request, "403_csrf.html", {"retry_url": request.path}, status=403)


def home(request):
    today = date.today()
    birthday_window_start = today - timedelta(days=3)
    birthday_window_end = today + timedelta(days=7)
    # Keep seasonal and other advance-planning events visible. A 45-day window
    # hid Christmas events entered in early November even though they were
    # correctly marked public.
    upcoming = Event.occurrences_between(
        today, today + timedelta(days=120), Event.objects.filter(is_public=True)
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
        "birthday_celebrations": BirthdayCelebration.objects.filter(
            is_active=True, visibility=BirthdayCelebration.Visibility.PUBLIC,
            celebration_date__range=(birthday_window_start, birthday_window_end),
        ).select_related("ministry").annotate(
            reaction_count=Count("reactions", distinct=True), wish_count=Count("wishes", distinct=True),
        ).order_by("celebration_date")[:3],
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


def hero_image(request, pk):
    hero = get_object_or_404(HeroImage, pk=pk)
    if hero.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise Http404
    response = HttpResponse(bytes(hero.image_blob), content_type=hero.content_type)
    response["Content-Disposition"] = f'inline; filename="{hero.filename.replace(chr(34), "")}"'
    response["Cache-Control"] = "public, max-age=3600"
    return response


@admin_required
def hero_manager(request):
    current = {item.placement: item for item in HeroImage.objects.all()}
    slots = [
        {"key": key, "label": label, "description": description, "hero": current.get(key)}
        for key, label, description in _hero_slots()
    ]
    return render(request, "core/hero_manager.html", {"slots": slots})


@admin_required
def hero_edit(request, placement):
    slot = next((item for item in _hero_slots() if item[0] == placement), None)
    if slot is None:
        raise Http404
    hero = HeroImage.objects.filter(placement=placement).first()
    initial = {"alt_text": hero.alt_text if hero else "", "position": hero.position if hero else "center center"}
    form = HeroImageForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data["remove_image"]:
            if hero:
                hero.delete()
            messages.success(request, f"{slot[1]} now uses its original image or background.")
            return redirect("core:hero_manager")
        upload = form.cleaned_data.get("image")
        if not upload and not hero:
            form.add_error("image", "Choose an image to upload.")
        else:
            if upload:
                try:
                    validate_image_upload(upload)
                    data, filename, content_type = optimize_image_upload(upload)
                except ImageProcessingError as exc:
                    form.add_error("image", str(exc))
                else:
                    hero, _ = HeroImage.objects.get_or_create(
                        placement=placement,
                        defaults={"image_blob": data, "filename": filename, "content_type": content_type},
                    )
                    hero.image_blob, hero.filename, hero.content_type = data, filename, content_type
            if not form.errors:
                hero.alt_text = form.cleaned_data["alt_text"]
                hero.position = form.cleaned_data["position"]
                hero.updated_by = request.user
                hero.save()
                messages.success(request, f"{slot[1]} was updated.")
                return redirect("core:hero_manager")
    return render(request, "core/hero_form.html", {"form": form, "hero": hero, "slot": slot})


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
