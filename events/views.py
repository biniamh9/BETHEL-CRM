import calendar as pycal
from collections import defaultdict
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from ministries.models import Activity, Ministry

from .forms import EventForm
from .models import Event


def _ministry_filter(request):
    slug = request.GET.get("ministry", "")
    if slug == "church":
        return slug, None
    return slug, Ministry.objects.filter(slug=slug).first() if slug else None


def _events_for(request):
    slug, ministry = _ministry_filter(request)
    qs = Event.objects.all()
    if slug == "church":
        qs = qs.filter(ministry=None)
    elif ministry:
        qs = qs.filter(ministry=ministry)
    return qs, slug, ministry


@login_required
def month(request, year=None, month=None):
    today = date.today()
    year, month = year or today.year, month or today.month
    if not 1 <= month <= 12:
        return redirect("events:calendar")
    weeks = pycal.Calendar(firstweekday=6).monthdatescalendar(year, month)  # weeks start on Sunday
    first, last = weeks[0][0], weeks[-1][-1]
    qs, slug, ministry = _events_for(request)

    by_day = defaultdict(list)
    for occ in Event.occurrences_between(first, last, qs):
        by_day[occ.date].append({"type": "event", "occ": occ})

    show_activities = request.GET.get("activities") == "1"
    if show_activities:
        acts = Activity.objects.filter(ministry__in=request.user.visible_ministries(), date__range=(first, last))
        if ministry:
            acts = acts.filter(ministry=ministry)
        elif slug == "church":
            acts = acts.none()
        for a in acts.select_related("ministry"):
            by_day[a.date].append({"type": "activity", "a": a})

    prev_m = date(year, month, 1) - timedelta(days=1)
    next_m = date(year, month, 28) + timedelta(days=7)
    keep = request.GET.urlencode()
    return render(request, "events/calendar.html", {
        "weeks": [[{"date": d, "items": by_day.get(d, []), "other": d.month != month, "today": d == today}
                   for d in week] for week in weeks],
        "month_start": date(year, month, 1),
        "prev_url": reverse("events:calendar_month", args=[prev_m.year, prev_m.month]) + (f"?{keep}" if keep else ""),
        "next_url": reverse("events:calendar_month", args=[next_m.year, next_m.month]) + (f"?{keep}" if keep else ""),
        "today_url": reverse("events:calendar") + (f"?{keep}" if keep else ""),
        "ministries": Ministry.objects.all(), "slug": slug, "show_activities": show_activities,
        "weekdays": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
    })


@login_required
def upcoming(request):
    qs, slug, ministry = _events_for(request)
    days = 30 if request.GET.get("range") == "30" else 90
    today = date.today()
    grouped = defaultdict(list)
    for occ in Event.occurrences_between(today, today + timedelta(days=days), qs):
        grouped[occ.date].append(occ)
    return render(request, "events/upcoming.html", {
        "groups": sorted(grouped.items()), "ministries": Ministry.objects.all(), "slug": slug, "days": days,
    })


@login_required
def detail(request, pk):
    event = get_object_or_404(Event.objects.select_related("ministry", "created_by"), pk=pk)
    today = date.today()
    upcoming_dates = event.occurrences(today, today + timedelta(days=120))[:8]
    return render(request, "events/detail.html", {
        "event": event, "upcoming_dates": upcoming_dates, "can_edit": request.user.can_edit_event(event),
        "gcal": event.google_calendar_url(upcoming_dates[0] if upcoming_dates else None),
    })


@login_required
def edit(request, pk=None):
    event = get_object_or_404(Event, pk=pk) if pk else None
    if event and not request.user.can_edit_event(event):
        raise PermissionDenied
    if not event and not request.user.can_create_events:
        raise PermissionDenied
    initial = {}
    if not event:
        if request.GET.get("date"):
            initial["date"] = request.GET["date"]
        if request.GET.get("ministry"):
            initial["ministry"] = Ministry.objects.filter(slug=request.GET["ministry"]).first()
    form = EventForm(request.POST or None, instance=event, user=request.user, initial=initial)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if not obj.created_by_id:
            obj.created_by = request.user
        obj.save()
        messages.success(request, f"Saved “{obj.title}”.")
        return redirect(obj)
    return render(request, "events/form.html", {"form": form, "event": event})


@login_required
def delete(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if not request.user.can_edit_event(event):
        raise PermissionDenied
    if request.method == "POST":
        event.delete()
        messages.success(request, "Event deleted.")
        return redirect("events:upcoming")
    return redirect(event)


def public_events(request):
    today = date.today()
    grouped = defaultdict(list)
    for occ in Event.occurrences_between(today, today + timedelta(days=90), Event.objects.filter(is_public=True)):
        grouped[occ.date].append(occ)
    return render(request, "events/public.html", {"groups": sorted(grouped.items())})
