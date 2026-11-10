from datetime import date, timedelta
import logging
from types import SimpleNamespace
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch, Q, Sum
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.models import User
from events.models import Event
from fundraising.models import Campaign, Donation
from ministries.models import Activity, BirthdayCelebration, GalleryAlbum, GalleryPhoto, Ministry, MinistryInquiry, StudentAchievement
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
        "student_achievements": StudentAchievement.objects.filter(
            is_active=True, visibility=StudentAchievement.Visibility.PUBLIC,
        ).select_related("ministry").order_by("-recognition_date")[:3],
        "ministries": Ministry.objects.all(),
        "elders": User.objects.filter(is_active=True, role__in=[User.Role.ADMIN, User.Role.ELDER]).order_by("role", "first_name"),
    })


def about(request):
    return render(request, "core/about.html")


def visit(request):
    return render(request, "core/visit.html")


def public_activities(request):
    public_photos = GalleryPhoto.objects.filter(is_public=True).select_related("ministry").order_by("created_at")
    albums = GalleryAlbum.objects.filter(is_public=True, photos__is_public=True).select_related("ministry").annotate(
        photo_count=Count("photos", filter=Q(photos__is_public=True), distinct=True),
    ).prefetch_related(Prefetch("photos", queryset=public_photos, to_attr="public_photos")).distinct()

    q = request.GET.get("q", "").strip()
    ministry = request.GET.get("ministry", "").strip()
    occasion = request.GET.get("occasion", "").strip()
    year = request.GET.get("year", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    sort = request.GET.get("sort", "newest").strip()

    if q:
        albums = albums.filter(
            Q(title__icontains=q) | Q(description__icontains=q) |
            Q(location__icontains=q) | Q(ministry__name__icontains=q),
        )
    if ministry:
        albums = albums.filter(ministry__slug=ministry)
    if occasion:
        albums = albums.filter(photos__is_public=True, photos__occasion=occasion)
    if year.isdigit():
        albums = albums.filter(event_date__year=int(year))
    try:
        if date_from:
            albums = albums.filter(event_date__gte=date.fromisoformat(date_from))
    except ValueError:
        date_from = ""
    try:
        if date_to:
            albums = albums.filter(event_date__lte=date.fromisoformat(date_to))
    except ValueError:
        date_to = ""

    orderings = {
        "oldest": ("event_date", "title"),
        "title": ("title", "-event_date"),
        "newest": ("-event_date", "-created_at"),
    }
    albums = list(albums.order_by(*orderings.get(sort, orderings["newest"])).distinct())
    for album in albums:
        album.cover_photo = album.public_photos[0] if album.public_photos else None
        album.occasion_labels = list(dict.fromkeys(photo.get_occasion_display() for photo in album.public_photos))

    for album in albums:
        album.detail_url = reverse("core:public_activity_album", args=[album.slug])
        album.date_label = album.event_date.strftime("%B %-d, %Y") if album.event_date else "Photo collection"

    loose_photos = GalleryPhoto.objects.filter(is_public=True, album__isnull=True).select_related("ministry", "activity")
    if q:
        loose_photos = loose_photos.filter(
            Q(caption__icontains=q) | Q(activity__title__icontains=q) | Q(ministry__name__icontains=q),
        )
    if ministry:
        loose_photos = loose_photos.filter(ministry__slug=ministry)
    if occasion:
        loose_photos = loose_photos.filter(occasion=occasion)
    if year.isdigit():
        loose_photos = loose_photos.filter(year=int(year))
    if date_from:
        from_date = date.fromisoformat(date_from)
        loose_photos = loose_photos.filter(
            Q(activity__date__gte=from_date) | Q(activity__isnull=True, year__gte=from_date.year),
        )
    if date_to:
        to_date = date.fromisoformat(date_to)
        loose_photos = loose_photos.filter(
            Q(activity__date__lte=to_date) | Q(activity__isnull=True, year__lte=to_date.year),
        )

    grouped_photos = {}
    for photo in loose_photos:
        public_activity = photo.activity if photo.activity and photo.activity.is_public else None
        key = ("activity", public_activity.pk) if public_activity else (
            "collection", photo.ministry_id, photo.occasion, photo.year,
        )
        grouped_photos.setdefault(key, []).append(photo)

    collections = []
    for key, photos in grouped_photos.items():
        first = photos[0]
        activity = first.activity if first.activity and first.activity.is_public else None
        title = activity.title if activity else f"{first.get_occasion_display()} · {first.ministry.name}"
        event_date = activity.date if activity else None
        params = {"ministry": first.ministry.slug}
        if activity:
            params["activity"] = activity.pk
        else:
            params.update({"occasion": first.occasion, "year": first.year})
        collections.append(SimpleNamespace(
            title=title, ministry=first.ministry, event_date=event_date,
            date_label=event_date.strftime("%B %-d, %Y") if event_date else str(first.year),
            description=activity.summary if activity else "A collection of moments shared by this ministry.",
            location=activity.location if activity else "", photo_count=len(photos), cover_photo=first,
            public_photos=photos, occasion_labels=[first.get_occasion_display()],
            detail_url=f'{reverse("core:public_activity_collection")}?{urlencode(params)}',
        ))

    if sort == "title":
        collections.sort(key=lambda item: item.title.lower())
    elif sort == "oldest":
        collections.sort(key=lambda item: (item.event_date or date(item.cover_photo.year, 1, 1), item.title))
    else:
        collections.sort(key=lambda item: (item.event_date or date(item.cover_photo.year, 1, 1), item.title), reverse=True)
    albums.extend(collections)
    if sort == "title":
        albums.sort(key=lambda item: item.title.lower())
    elif sort == "oldest":
        albums.sort(key=lambda item: (item.event_date or date(item.cover_photo.year, 1, 1), item.title))
    else:
        albums.sort(key=lambda item: (item.event_date or date(item.cover_photo.year, 1, 1), item.title), reverse=True)

    represented_activity_ids = {
        photo.activity_id for collection in collections for photo in collection.public_photos if photo.activity_id
    }
    activity_records = Activity.objects.filter(is_public=True).exclude(pk__in=represented_activity_ids).select_related("ministry")
    if q:
        activity_records = activity_records.filter(
            Q(title__icontains=q) | Q(summary__icontains=q) |
            Q(location__icontains=q) | Q(ministry__name__icontains=q),
        )
    if ministry:
        activity_records = activity_records.filter(ministry__slug=ministry)
    if year.isdigit():
        activity_records = activity_records.filter(date__year=int(year))
    if date_from:
        activity_records = activity_records.filter(date__gte=date.fromisoformat(date_from))
    if date_to:
        activity_records = activity_records.filter(date__lte=date.fromisoformat(date_to))
    if occasion:
        activity_records = activity_records.none()
    activity_orderings = {
        "oldest": ("date", "title"), "title": ("title", "-date"), "newest": ("-date", "title"),
    }
    activity_records = list(activity_records.order_by(*activity_orderings.get(sort, activity_orderings["newest"])))

    available_albums = GalleryAlbum.objects.filter(is_public=True, photos__is_public=True)
    album_years = set(available_albums.exclude(event_date=None).values_list("event_date__year", flat=True))
    photo_years = set(GalleryPhoto.objects.filter(is_public=True).values_list("year", flat=True))
    available_years = sorted(album_years | photo_years, reverse=True)
    available_ministries = Ministry.objects.filter(
        Q(gallery_albums__is_public=True, gallery_albums__photos__is_public=True) |
        Q(gallery_photos__is_public=True),
    ).distinct().order_by("name")
    used_occasions = set(GalleryPhoto.objects.filter(is_public=True).values_list("occasion", flat=True))

    return render(request, "core/public_activities.html", {
        "albums": albums,
        "album_count": len(albums) + len(activity_records),
        "photo_count": sum(album.photo_count for album in albums),
        "activity_records": activity_records,
        "available_years": available_years,
        "available_ministries": available_ministries,
        "occasion_choices": [choice for choice in GalleryPhoto.Occasion.choices if choice[0] in used_occasions],
        "filters": {
            "q": q, "ministry": ministry, "occasion": occasion, "year": year,
            "date_from": date_from, "date_to": date_to, "sort": sort,
        },
    })


def public_activity_album(request, slug):
    album = get_object_or_404(
        GalleryAlbum.objects.select_related("ministry").prefetch_related("photos"),
        slug=slug,
        is_public=True,
    )
    return render(request, "resources/public_album_detail.html", {
        "album": album,
        "photos": album.photos.filter(is_public=True),
        "back_url": "core:public_activities",
        "back_label": "Activities & galleries",
    })


def public_activity_collection(request):
    ministry = get_object_or_404(Ministry, slug=request.GET.get("ministry", ""), is_public=True)
    photos = GalleryPhoto.objects.filter(is_public=True, album__isnull=True, ministry=ministry).select_related("activity")
    activity = None
    if request.GET.get("activity", "").isdigit():
        activity = get_object_or_404(Activity, pk=int(request.GET["activity"]), ministry=ministry, is_public=True)
        photos = photos.filter(activity=activity)
    else:
        occasion = request.GET.get("occasion", "")
        year = request.GET.get("year", "")
        if occasion not in GalleryPhoto.Occasion.values or not year.isdigit():
            raise Http404
        photos = photos.filter(occasion=occasion, year=int(year), activity=None)
    photos = list(photos)
    if not photos:
        raise Http404
    first = photos[0]
    album = SimpleNamespace(
        title=activity.title if activity else f"{first.get_occasion_display()} · {ministry.name}",
        ministry=ministry, event_date=activity.date if activity else None,
        description=activity.summary if activity else "A collection of moments shared by this ministry.",
        location=activity.location if activity else "",
    )
    return render(request, "resources/public_album_detail.html", {
        "album": album, "photos": photos,
        "back_url": "core:public_activities", "back_label": "Activities & galleries",
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
