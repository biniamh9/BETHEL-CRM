import csv
import logging
from datetime import date

from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.decorators import finance_required, fund_totals_required

from . import payments
from .forms import PRESET_AMOUNTS, DonationForm, DonorForm, PledgeForm, PublicGiftForm, PublicPledgeForm
from .models import Campaign, Donation, Donor, Pledge

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Public giving pages
# --------------------------------------------------------------------------

def give(request):
    campaign = Campaign.objects.filter(is_active=True, is_public=True).first()
    if not campaign:
        raise Http404("No active campaign")
    return redirect(campaign)


def _campaign_context(campaign, gift_form=None, pledge_form=None):
    wall = []
    if campaign.show_donor_wall:
        wall = (campaign.succeeded().filter(show_on_wall=True).exclude(donor=None)
                .select_related("donor").order_by("-received_on", "-created_at")[:24])
    story_blocks = []
    for block in (p.strip() for p in campaign.story.split("\n\n") if p.strip()):
        if block.startswith("## "):
            story_blocks.append({"kind": "heading", "text": block[3:].strip()})
        elif all(line.startswith("- ") for line in block.splitlines()):
            story_blocks.append({"kind": "list", "items": [line[2:].strip() for line in block.splitlines()]})
        elif all(". " in line and line.partition(". ")[0].isdigit() for line in block.splitlines()):
            story_blocks.append({"kind": "ordered", "items": [line.split(". ", 1)[1] for line in block.splitlines()]})
        else:
            story_blocks.append({"kind": "paragraph", "text": block})
    return {
        "campaign": campaign,
        "story_blocks": story_blocks,
        "wall": wall,
        "gift_form": gift_form or PublicGiftForm(),
        "pledge_form": pledge_form or PublicPledgeForm(),
        "presets": PRESET_AMOUNTS,
        "stripe_enabled": payments.stripe_enabled(),
    }


def campaign_detail(request, slug):
    campaign = get_object_or_404(Campaign, slug=slug, is_public=True)
    return render(request, "fundraising/campaign.html", _campaign_context(campaign))


@require_POST
def donate(request, slug):
    campaign = get_object_or_404(Campaign, slug=slug, is_public=True, is_active=True)
    form = PublicGiftForm(request.POST)
    if not payments.stripe_enabled():
        messages.info(request, "Online giving isn't switched on yet. Please use Zelle, check, or make a pledge below.")
        return redirect(campaign)
    if not form.is_valid():
        return render(request, "fundraising/campaign.html", _campaign_context(campaign, gift_form=form), status=400)
    d = form.cleaned_data
    donor = payments_donor(d)
    donation = Donation.objects.create(
        campaign=campaign, donor=donor, amount=d["amount"], method=Donation.Method.ONLINE,
        status=Donation.Status.PENDING, received_on=date.today(),
        show_on_wall=d["show_on_wall"], public_message=d["public_message"],
    )
    try:
        url = payments.create_checkout_session(
            donation,
            success_url=request.build_absolute_uri(reverse("fundraising:thanks")),
            cancel_url=request.build_absolute_uri(campaign.get_absolute_url()) + "#give",
        )
    except Exception:
        logger.exception("Stripe checkout failed")
        donation.status = Donation.Status.FAILED
        donation.save(update_fields=["status"])
        messages.error(request, "We couldn't start the online payment. Please try again or use another giving option.")
        return redirect(campaign)
    return redirect(url)


def payments_donor(d):
    return Donor.find_or_create(d["first_name"], d["last_name"], d["email"], d.get("phone", ""))


def pledge(request, slug):
    campaign = get_object_or_404(Campaign, slug=slug, is_public=True, is_active=True)
    form = PublicPledgeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        p = Pledge.objects.create(
            donor=payments_donor(d), campaign=campaign, total_amount=d["total_amount"],
            frequency=d["frequency"], start_date=date.today(), target_date=d["target_date"], notes=d["notes"],
        )
        return render(request, "fundraising/thanks.html", {"campaign": campaign, "pledge": p})
    if request.method == "POST":
        return render(request, "fundraising/campaign.html", _campaign_context(campaign, pledge_form=form), status=400)
    return redirect(f"{campaign.get_absolute_url()}#pledge")


def thanks(request):
    donation = None
    session_id = request.GET.get("session_id")
    if session_id and payments.stripe_enabled():
        try:
            donation = payments.apply_session(payments.retrieve_session(session_id))
        except Exception:
            logger.exception("Could not confirm Stripe session %s", session_id)
    campaign = donation.campaign if donation else Campaign.objects.filter(is_active=True, is_public=True).first()
    return render(request, "fundraising/thanks.html", {"donation": donation, "campaign": campaign})


@csrf_exempt
@require_POST
def stripe_webhook(request):
    try:
        event = payments.parse_webhook(request.body, request.META.get("HTTP_STRIPE_SIGNATURE", ""))
    except Exception:
        return HttpResponseBadRequest("invalid signature")
    kind = event["type"]
    session = event["data"]["object"]
    if kind in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        payments.apply_session(session)
    elif kind in ("checkout.session.async_payment_failed", "checkout.session.expired"):
        Donation.objects.filter(stripe_session_id=session["id"], status=Donation.Status.PENDING).update(
            status=Donation.Status.FAILED)
    return HttpResponse("ok")


# --------------------------------------------------------------------------
# Finance portal
# --------------------------------------------------------------------------

def _selected_campaign(request):
    slug = request.GET.get("campaign")
    qs = Campaign.objects.all()
    return (qs.filter(slug=slug).first() if slug else None) or qs.filter(is_active=True).first() or qs.first()


@fund_totals_required
def dashboard(request):
    campaign = _selected_campaign(request)
    ctx = {"campaign": campaign, "campaigns": Campaign.objects.all(), "show_names": request.user.can_manage_finance}
    if campaign:
        ok = campaign.succeeded()
        ctx["by_method"] = ok.values("method").annotate(total=Sum("amount"), n=Count("id")).order_by("-total")
        for row in ctx["by_method"]:
            row["label"] = Donation.Method(row["method"]).label
        monthly = list(ok.annotate(m=TruncMonth("received_on")).values("m").annotate(total=Sum("amount")).order_by("m"))[-12:]
        top = max((r["total"] for r in monthly), default=0) or 1
        for r in monthly:
            r["height"] = round(float(r["total"] / top) * 100)
        ctx["monthly"] = monthly
        this_month = date.today().replace(day=1)
        ctx["month_total"] = ok.filter(received_on__gte=this_month).aggregate(t=Sum("amount"))["t"] or 0
        ctx["pending_online"] = campaign.donations.filter(status=Donation.Status.PENDING).count()
        if ctx["show_names"]:
            ctx["recent"] = campaign.donations.select_related("donor")[:10]
            ctx["pledges"] = campaign.pledges.filter(status=Pledge.Status.ACTIVE).select_related("donor")[:10]
    return render(request, "fundraising/portal/dashboard.html", ctx)


@finance_required
def donation_list(request):
    qs = Donation.objects.select_related("donor", "campaign")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(donor__first_name__icontains=q) | Q(donor__last_name__icontains=q)
                       | Q(donor__email__icontains=q) | Q(reference__icontains=q))
    for field in ("method", "status"):
        if request.GET.get(field):
            qs = qs.filter(**{field: request.GET[field]})
    if request.GET.get("year"):
        qs = qs.filter(received_on__year=request.GET["year"])
    total = qs.filter(status=Donation.Status.SUCCEEDED).aggregate(t=Sum("amount"))["t"] or 0
    if request.GET.get("export") == "csv":
        return _donations_csv(qs)
    return render(request, "fundraising/portal/donations.html", {
        "donations": qs[:300], "total": total, "count": qs.count(),
        "methods": Donation.Method.choices, "statuses": Donation.Status.choices,
    })


def _donations_csv(qs):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="building-fund-donations.csv"'
    w = csv.writer(response)
    w.writerow(["Receipt", "Date", "Donor", "Email", "Phone", "Amount", "Method", "Status", "Reference", "Campaign", "Notes"])
    for d in qs:
        w.writerow([d.receipt_number, d.received_on, d.donor.full_name if d.donor else "Anonymous",
                    d.donor.email if d.donor else "", d.donor.phone if d.donor else "", d.amount,
                    d.get_method_display(), d.get_status_display(), d.reference, d.campaign.name, d.notes])
    return response


@finance_required
def donation_edit(request, pk=None):
    donation = get_object_or_404(Donation, pk=pk) if pk else None
    initial = {}
    if not donation:
        initial = {"received_on": date.today(), "campaign": Campaign.objects.filter(is_active=True).first()}
        if request.GET.get("donor"):
            initial["donor"] = request.GET["donor"]
        if request.GET.get("pledge"):
            p = Pledge.objects.filter(pk=request.GET["pledge"]).first()
            if p:
                initial.update(pledge=p, donor=p.donor, campaign=p.campaign)
    form = DonationForm(request.POST or None, instance=donation, initial=initial)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if not obj.recorded_by_id:
            obj.recorded_by = request.user
        obj.save()
        if obj.pledge:
            obj.pledge.refresh_status()
        messages.success(request, f"Saved {obj}. Receipt {obj.receipt_number}.")
        return redirect("fundraising:donations")
    return render(request, "fundraising/portal/donation_form.html", {"form": form, "donation": donation})


@finance_required
def donation_receipt(request, pk):
    donation = get_object_or_404(Donation.objects.select_related("donor", "campaign"), pk=pk)
    return render(request, "fundraising/portal/receipt.html", {"d": donation})


@finance_required
def donor_list(request):
    qs = Donor.with_totals()
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q)
                       | Q(phone__icontains=q) | Q(organization__icontains=q))
    order = "-total" if request.GET.get("sort") == "total" else "first_name"
    return render(request, "fundraising/portal/donors.html", {"donors": qs.order_by(order, "last_name")})


@finance_required
def donor_detail(request, pk):
    donor = get_object_or_404(Donor, pk=pk)
    years = sorted({d.year for d in donor.donations.dates("received_on", "year")}, reverse=True)
    return render(request, "fundraising/portal/donor_detail.html", {
        "donor": donor,
        "donations": donor.donations.select_related("campaign"),
        "pledges": donor.pledges.select_related("campaign"),
        "years": years,
    })


@finance_required
def donor_edit(request, pk=None):
    donor = get_object_or_404(Donor, pk=pk) if pk else None
    form = DonorForm(request.POST or None, instance=donor)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        messages.success(request, f"Saved {obj}.")
        return redirect(obj)
    return render(request, "fundraising/portal/simple_form.html", {
        "form": form, "title": f"Edit {donor}" if donor else "Add a donor",
        "back": donor.get_absolute_url() if donor else reverse("fundraising:donors"),
    })


@finance_required
def donor_statement(request, pk, year):
    donor = get_object_or_404(Donor, pk=pk)
    gifts = donor.donations.filter(status=Donation.Status.SUCCEEDED, received_on__year=year).select_related("campaign")
    total = gifts.aggregate(t=Sum("amount"))["t"] or 0
    return render(request, "fundraising/portal/statement.html", {"donor": donor, "gifts": gifts, "total": total, "year": year})


@finance_required
def pledge_list(request):
    status = request.GET.get("status", Pledge.Status.ACTIVE)
    qs = Pledge.objects.select_related("donor", "campaign")
    if status != "all":
        qs = qs.filter(status=status)
    return render(request, "fundraising/portal/pledges.html", {
        "pledges": qs, "status": status, "statuses": Pledge.Status.choices,
    })


@finance_required
def pledge_edit(request, pk=None):
    obj = get_object_or_404(Pledge, pk=pk) if pk else None
    initial = {} if obj else {"start_date": date.today(), "campaign": Campaign.objects.filter(is_active=True).first(),
                              "donor": request.GET.get("donor")}
    form = PledgeForm(request.POST or None, instance=obj, initial=initial)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        messages.success(request, f"Saved pledge: {saved}.")
        return redirect("fundraising:pledges")
    return render(request, "fundraising/portal/simple_form.html", {
        "form": form, "title": "Edit pledge" if obj else "Record a pledge", "back": reverse("fundraising:pledges"),
    })


@finance_required
def campaign_edit(request, pk=None):
    from django import forms as djforms

    CampaignForm = djforms.modelform_factory(Campaign, exclude=("slug", "created_at"), widgets={
        "start_date": djforms.DateInput(attrs={"type": "date"}),
        "end_date": djforms.DateInput(attrs={"type": "date"}),
        "story": djforms.Textarea(attrs={"rows": 10}),
    })
    obj = get_object_or_404(Campaign, pk=pk) if pk else None
    form = CampaignForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        messages.success(request, f"Saved campaign {saved}.")
        return redirect(f"{reverse('fundraising:dashboard')}?campaign={saved.slug}")
    return render(request, "fundraising/portal/simple_form.html", {
        "form": form, "title": f"Edit {obj}" if obj else "New campaign", "back": reverse("fundraising:dashboard"),
    })
