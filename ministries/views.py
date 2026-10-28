import csv
from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q, Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import (
    ActivityForm, GalleryAlbumForm, GalleryPhotoForm, GalleryPhotoMetadataForm, MinistryContactForm, MinistryJoinForm,
    MinistryMemberSpotlightForm, MinistryProfileForm, ParticipantForm, PortalGalleryPhotoForm,
)
from .models import Activity, GalleryAlbum, GalleryPhoto, Ministry, MinistryAnnouncement, MinistryInquiry, MinistryMemberSpotlight, Participant
from .forms import validate_gallery_image
from .image_processing import GalleryImageError, automatic_caption, optimize_gallery_image

ACTIVITY_IMAGE_EXTENSIONS = {".gif", ".jpeg", ".jpg", ".png", ".webp"}


def public_ministry_list(request):
    ministries = Ministry.objects.filter(is_public=True).prefetch_related("leaders")
    return render(request, "ministries/public_list.html", {"ministries": ministries})


def public_ministry_detail(request, slug):
    ministry = get_object_or_404(Ministry.objects.filter(is_public=True), slug=slug)
    from events.models import Event
    return render(request, "ministries/public_detail.html", {
        "ministry": ministry,
        "upcoming": Event.occurrences_between(
            date.today(), date.today() + timedelta(days=90), ministry.events.filter(is_public=True)
        )[:6],
        "announcements": ministry.announcements.filter(status=MinistryAnnouncement.Status.PUBLISHED)[:6],
        "gallery_photos": ministry.gallery_photos.filter(is_public=True)[:12],
        "member_spotlights": ministry.member_spotlights.filter(is_public=True),
    })


def public_member_spotlight_image(request, slug, pk):
    spotlight = get_object_or_404(MinistryMemberSpotlight.objects.select_related("ministry"), pk=pk, ministry__slug=slug)
    allowed = spotlight.is_public or (
        request.user.is_authenticated and request.user.can_edit_ministry(spotlight.ministry)
    )
    if not allowed or not spotlight.image_blob:
        raise Http404
    return HttpResponse(bytes(spotlight.image_blob), content_type=spotlight.image_content_type or "image/jpeg")


def public_ministry_inquiry(request, slug, kind):
    ministry = get_object_or_404(Ministry.objects.filter(is_public=True), slug=slug)
    if kind not in {MinistryInquiry.Kind.CONTACT, MinistryInquiry.Kind.JOIN}:
        raise PermissionDenied
    form_class = MinistryJoinForm if kind == MinistryInquiry.Kind.JOIN else MinistryContactForm
    form = form_class(request.POST or None)
    if request.method == "POST" and form.is_valid():
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        client = forwarded or request.META.get("REMOTE_ADDR", "unknown")
        throttle_key = f"ministry-inquiry:{client}:{ministry.pk}"
        attempts = cache.get(throttle_key, 0)
        if attempts >= 5:
            form.add_error(None, "Too many submissions. Please wait a few minutes and try again.")
        else:
            cache.set(throttle_key, attempts + 1, 600)
            inquiry = form.save(commit=False)
            inquiry.ministry = ministry
            inquiry.kind = kind
            inquiry.save()
            messages.success(request, "Thank you. Your message was sent securely to the ministry team.")
            return redirect(ministry.get_public_url())
    return render(request, "ministries/public_inquiry.html", {
        "form": form, "ministry": ministry, "kind": kind,
    })


def _activity_image_paths():
    """Return web-compatible, optimized photographs from the repository."""
    root = Path(settings.BASE_DIR) / "images"
    if not root.is_dir():
        return []
    return [
        f"activity-images/{path.name}"
        for path in sorted(root.iterdir(), key=lambda item: item.name.lower())
        if path.is_file() and path.suffix.lower() in ACTIVITY_IMAGE_EXTENSIONS
    ]


def _get_ministry(request, slug, edit=False):
    ministry = get_object_or_404(Ministry, slug=slug)
    allowed = request.user.can_edit_ministry(ministry) if edit else request.user.can_view_ministry(ministry)
    if not allowed:
        raise PermissionDenied
    return ministry


@login_required
def ministry_list(request):
    ministries = request.user.visible_ministries().annotate(
        n_activities=Count("activities", distinct=True),
        n_participants=Count("participants", distinct=True),
    ).prefetch_related("leaders")
    return render(request, "ministries/list.html", {"ministries": ministries})


@login_required
def all_activities(request):
    """Every recorded activity across the ministries this person can see."""
    visible = request.user.visible_ministries()
    qs = Activity.objects.filter(ministry__in=visible).select_related("ministry", "created_by").prefetch_related("gallery_photos")
    slug = request.GET.get("ministry")
    if slug:
        qs = qs.filter(ministry__slug=slug)
    if request.GET.get("kind"):
        qs = qs.filter(kind=request.GET["kind"])
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(summary__icontains=q) | Q(follow_up__icontains=q))
    period = request.GET.get("period", "90")
    if period != "all":
        qs = qs.filter(date__gte=date.today() - timedelta(days=int(period) if period.isdigit() else 90))
    if request.GET.get("followups") == "1":
        qs = qs.exclude(follow_up="")
    totals = qs.aggregate(attendance=Sum("attendance"), hours=Sum("volunteer_hours"))
    if request.GET.get("export") == "csv":
        return _activities_csv(qs, "all-activities")
    activities = list(qs[:200])
    images = _activity_image_paths()
    if images:
        for activity in activities:
            activity.image_static_path = images[activity.pk % len(images)]
    return render(request, "ministries/activities.html", {
        "activities": activities, "count": qs.count(), "totals": totals,
        "ministries": visible, "editable": request.user.editable_ministries(),
        "kinds": Activity.Kind.choices, "period": period,
        "has_activity_images": bool(images),
    })


def _activities_csv(qs, name):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{name}.csv"'
    writer = csv.writer(response)
    writer.writerow(["Date", "Ministry", "Title", "Type", "Location", "Attendance", "Volunteer hours", "Summary", "Follow-up", "Recorded by"])
    for a in qs:
        writer.writerow([a.date, a.ministry.name, a.title, a.get_kind_display(), a.location, a.attendance,
                         a.volunteer_hours, a.summary, a.follow_up, a.created_by or ""])
    return response


@login_required
def ministry_detail(request, slug):
    ministry = _get_ministry(request, slug)
    activities = ministry.activities.all()
    kind = request.GET.get("kind")
    if kind:
        activities = activities.filter(kind=kind)
    since = date.today() - timedelta(days=90)
    recent = ministry.activities.filter(date__gte=since)
    stats = recent.aggregate(total_attendance=Sum("attendance"), hours=Sum("volunteer_hours"))
    stats["count"] = recent.count()
    from events.models import Event
    from resources.models import Resource

    return render(request, "ministries/detail.html", {
        "upcoming": Event.occurrences_between(date.today(), date.today() + timedelta(days=30), ministry.events.all())[:6],
        "resources": Resource.visible_to(request.user).filter(ministry=ministry)[:6],
        "ministry": ministry,
        "activities": activities.prefetch_related("attendees")[:50],
        "participants": ministry.participants.filter(is_active=True),
        "member_spotlights": ministry.member_spotlights.all(),
        "inactive_count": ministry.participants.filter(is_active=False).count(),
        "stats": stats,
        "kinds": Activity.Kind.choices,
        "current_kind": kind,
        "can_edit": request.user.can_edit_ministry(ministry),
        "pending_inquiries": ministry.inquiries.filter(status=MinistryInquiry.Status.PENDING)[:8],
    })


@login_required
def ministry_profile_edit(request, slug):
    ministry = _get_ministry(request, slug, edit=True)
    form = MinistryProfileForm(request.POST or None, instance=ministry)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Public ministry information updated.")
        return redirect("ministries:detail", slug=ministry.slug)
    return render(request, "ministries/form.html", {
        "form": form, "ministry": ministry, "title": "Edit public ministry information",
    })


@login_required
def gallery_manage(request, slug):
    ministry = _get_ministry(request, slug, edit=True)
    form = GalleryPhotoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        photo = form.save(commit=False)
        photo.ministry = ministry
        photo.created_by = request.user
        photo.save()
        messages.success(request, "Photo uploaded to the ministry gallery.")
        return redirect("ministries:gallery", slug=ministry.slug)
    return render(request, "ministries/gallery.html", {
        "ministry": ministry, "form": form, "photos": ministry.gallery_photos.all(),
    })


@login_required
def gallery_hub(request):
    """One discoverable gallery workspace for every ministry the user can edit."""
    ministries = request.user.editable_ministries().order_by("name")
    if not ministries.exists():
        raise PermissionDenied
    form = PortalGalleryPhotoForm(request.POST or None, request.FILES or None, ministries=ministries)
    if request.method == "POST" and form.is_valid():
        photo = form.save(commit=False)
        photo.ministry = form.cleaned_data["ministry"]
        photo.album = form.cleaned_data.get("album")
        photo.created_by = request.user
        photo.save()
        messages.success(request, "Photo uploaded and added to the public activity gallery.")
        return redirect("ministries:gallery_hub")
    photos = GalleryPhoto.objects.filter(ministry__in=ministries).select_related("ministry", "album")
    return render(request, "ministries/gallery_hub.html", {
        "form": form, "photos": photos, "ministries": ministries,
        "albums": GalleryAlbum.objects.filter(ministry__in=ministries).select_related("ministry"),
        "occasion_choices": GalleryPhoto.Occasion.choices,
    })


@login_required
@require_POST
def gallery_batch_upload(request):
    """Accept one optimized photo at a time from the portal's sequential batch uploader."""
    ministries = request.user.editable_ministries()
    ministry = get_object_or_404(ministries, pk=request.POST.get("ministry"))
    album = None
    if request.POST.get("album"):
        album = get_object_or_404(GalleryAlbum, pk=request.POST["album"], ministry=ministry)
    occasion = request.POST.get("occasion")
    valid_occasions = {value for value, _label in GalleryPhoto.Occasion.choices}
    if occasion not in valid_occasions:
        return JsonResponse({"error": "Choose a valid occasion."}, status=400)
    try:
        year = int(request.POST.get("year", ""))
    except ValueError:
        year = 0
    if not 2000 <= year <= date.today().year + 1:
        return JsonResponse({"error": "Choose a valid year."}, status=400)
    upload = request.FILES.get("image")
    if not upload:
        return JsonResponse({"error": "Choose a photo."}, status=400)
    try:
        validate_gallery_image(upload)
        data, filename, content_type = optimize_gallery_image(upload)
    except (GalleryImageError, ValidationError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    caption = request.POST.get("caption", "").strip()[:220] or automatic_caption(
        upload.name, album.title if album else ""
    )
    photo = GalleryPhoto.objects.create(
        ministry=ministry, album=album, caption=caption, occasion=occasion, year=year,
        image_blob=data, content_type=content_type, filename=filename,
        is_public=request.POST.get("is_public") == "on", created_by=request.user,
    )
    return JsonResponse({
        "id": photo.pk, "caption": photo.caption, "size": len(data), "image_url": photo.get_image_url(),
    }, status=201)


@login_required
def gallery_album_edit(request, pk=None):
    ministries = request.user.editable_ministries().order_by("name")
    if not ministries.exists():
        raise PermissionDenied
    album = get_object_or_404(GalleryAlbum, pk=pk, ministry__in=ministries) if pk else None
    form = GalleryAlbumForm(request.POST or None, instance=album, ministries=ministries)
    if request.method == "POST" and form.is_valid():
        album = form.save(commit=False)
        if not album.created_by_id:
            album.created_by = request.user
        album.save()
        messages.success(request, "Photo album saved.")
        return redirect("ministries:gallery_hub")
    return render(request, "ministries/form.html", {
        "form": form, "ministry": album.ministry if album else ministries.first(),
        "title": "Edit photo album" if album else "Create photo album",
        "cancel_url": reverse("ministries:gallery_hub"),
    })


@login_required
def gallery_album_delete(request, pk):
    ministries = request.user.editable_ministries()
    album = get_object_or_404(GalleryAlbum, pk=pk, ministry__in=ministries)
    if request.method == "POST":
        album.delete()
        messages.success(request, "Album and its photos removed.")
    return redirect("ministries:gallery_hub")


@login_required
def gallery_delete(request, slug, pk):
    ministry = _get_ministry(request, slug, edit=True)
    photo = get_object_or_404(GalleryPhoto, pk=pk, ministry=ministry)
    if request.method == "POST":
        photo.delete()
        messages.success(request, "Photo removed.")
        if request.POST.get("next") == "hub":
            return redirect("ministries:gallery_hub")
    return redirect("ministries:gallery", slug=ministry.slug)


@login_required
def gallery_photo_edit(request, slug, pk):
    ministry = _get_ministry(request, slug, edit=True)
    photo = get_object_or_404(GalleryPhoto, pk=pk, ministry=ministry)
    form = GalleryPhotoMetadataForm(request.POST or None, instance=photo, ministry=ministry)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Photo details updated.")
        return redirect("ministries:gallery_hub")
    return render(request, "ministries/form.html", {
        "form": form, "ministry": ministry, "title": "Edit photo details",
        "cancel_url": reverse("ministries:gallery_hub"),
    })


@login_required
def inquiry_status(request, slug, pk):
    ministry = _get_ministry(request, slug, edit=True)
    inquiry = get_object_or_404(MinistryInquiry, pk=pk, ministry=ministry)
    if request.method == "POST":
        allowed = {choice for choice, _ in MinistryInquiry.Status.choices}
        status = request.POST.get("status")
        if status in allowed:
            inquiry.status = status
            inquiry.save(update_fields=["status", "updated_at"])
            messages.success(request, "Inquiry status updated.")
    return redirect("ministries:detail", slug=ministry.slug)


@login_required
def activity_edit(request, slug, pk=None):
    ministry = _get_ministry(request, slug, edit=True)
    activity = get_object_or_404(Activity, pk=pk, ministry=ministry) if pk else None
    initial = {} if activity else {"date": date.today()}
    form = ActivityForm(
        request.POST or None, request.FILES or None,
        instance=activity, ministry=ministry, initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.ministry = ministry
        if not obj.created_by_id:
            obj.created_by = request.user
        obj.save()
        form.save_m2m()
        upload = form.cleaned_data.get("image")
        if upload:
            GalleryPhoto.objects.create(
                ministry=ministry, activity=obj,
                caption=form.cleaned_data["image_caption"].strip(),
                occasion=GalleryPhoto.Occasion.MINISTRY, year=obj.date.year,
                image_blob=upload.read(), content_type=upload.detected_content_type,
                filename=Path(upload.name).name[:180], is_public=obj.is_public,
                created_by=request.user,
            )
        if obj.attendees.exists() and obj.attendance < obj.attendees.count():
            obj.attendance = obj.attendees.count()
            obj.save(update_fields=["attendance"])
        messages.success(request, "Activity and photo saved." if upload else "Activity saved.")
        return redirect(ministry)
    return render(request, "ministries/form.html", {
        "form": form, "ministry": ministry,
        "title": "Edit activity" if activity else "Record an activity",
        "delete_url": "ministries:activity_delete" if activity else None, "obj": activity,
    })


@login_required
def activity_delete(request, slug, pk):
    ministry = _get_ministry(request, slug, edit=True)
    activity = get_object_or_404(Activity, pk=pk, ministry=ministry)
    if request.method == "POST":
        activity.delete()
        messages.success(request, "Activity deleted.")
    return redirect(ministry)


@login_required
def participant_edit(request, slug, pk=None):
    ministry = _get_ministry(request, slug, edit=True)
    person = get_object_or_404(Participant, pk=pk, ministry=ministry) if pk else None
    form = ParticipantForm(request.POST or None, instance=person)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.ministry = ministry
        obj.save()
        messages.success(request, f"Saved {obj}.")
        return redirect(f"{ministry.get_absolute_url()}#people")
    return render(request, "ministries/form.html", {
        "form": form, "ministry": ministry,
        "title": f"Edit {person}" if person else "Add a person",
    })


@login_required
def member_spotlight_edit(request, slug, pk=None):
    ministry = _get_ministry(request, slug, edit=True)
    spotlight = get_object_or_404(MinistryMemberSpotlight, pk=pk, ministry=ministry) if pk else None
    form = MinistryMemberSpotlightForm(request.POST or None, request.FILES or None, instance=spotlight)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.ministry = ministry
        if not obj.created_by_id:
            obj.created_by = request.user
        obj.save()
        messages.success(request, f"Saved public member profile for {obj.display_name}.")
        return redirect(f"{ministry.get_absolute_url()}#member-spotlights")
    return render(request, "ministries/form.html", {
        "form": form, "ministry": ministry, "spotlight": spotlight,
        "title": f"Edit {spotlight.display_name}" if spotlight else "Add public member profile",
        "cancel_url": f"{ministry.get_absolute_url()}#member-spotlights",
    })


@login_required
def member_spotlight_delete(request, slug, pk):
    ministry = _get_ministry(request, slug, edit=True)
    spotlight = get_object_or_404(MinistryMemberSpotlight, pk=pk, ministry=ministry)
    if request.method == "POST":
        name = spotlight.display_name
        spotlight.delete()
        messages.success(request, f"Removed public member profile for {name}.")
    return redirect(f"{ministry.get_absolute_url()}#member-spotlights")


@login_required
def activity_export(request, slug):
    ministry = _get_ministry(request, slug)
    return _activities_csv(ministry.activities.select_related("ministry", "created_by"), f"{ministry.slug}-activities")
