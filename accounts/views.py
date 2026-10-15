from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from fundraising.models import Donation

from .decorators import admin_required
from .forms import ProfileForm, RegistrationForm, TeamMemberForm
from .models import MinistryAccessRequest, User


def register(request):
    if request.user.is_authenticated:
        return redirect("core:portal")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.phone = form.cleaned_data.get("phone", "")
        user.save()
        access_request = form.save_access_request(user)
        login(request, user)
        if access_request:
            messages.success(
                request,
                "Your account has been created. Ministry management access requires administrator approval.",
            )
        else:
            messages.success(request, "Welcome! Your member account is ready.")
        return redirect("core:portal")
    return render(request, "accounts/register.html", {"form": form})


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("accounts:profile")
    my_gifts = (
        Donation.objects.filter(donor__user=request.user, status=Donation.Status.SUCCEEDED)
        .select_related("campaign")
        .order_by("-received_on")
    )
    return render(request, "accounts/profile.html", {"form": form, "my_gifts": my_gifts})


@admin_required
def team_list(request):
    users = User.objects.prefetch_related("led_ministries").order_by("role", "first_name")
    return render(request, "accounts/team_list.html", {"users": users})


@admin_required
def team_edit(request, pk=None):
    member = get_object_or_404(User, pk=pk) if pk else None
    form = TeamMemberForm(request.POST or None, instance=member)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        messages.success(request, f"Saved login for {saved}.")
        return redirect("accounts:team")
    return render(request, "accounts/team_form.html", {"form": form, "member": member})


@admin_required
def access_requests(request):
    requests = MinistryAccessRequest.objects.select_related("user", "reviewed_by").prefetch_related("ministries")
    return render(request, "accounts/access_requests.html", {"access_requests": requests})


@admin_required
def access_request_review(request, pk):
    access_request = get_object_or_404(
        MinistryAccessRequest.objects.select_related("user").prefetch_related("ministries"), pk=pk
    )
    if request.method == "POST" and access_request.status == MinistryAccessRequest.Status.PENDING:
        decision = request.POST.get("decision")
        if decision == "approve":
            access_request.approve(request.user)
            messages.success(request, "Ministry access approved.")
        elif decision == "reject":
            access_request.reject(request.user)
            messages.success(request, "Ministry access request rejected.")
    return redirect("accounts:access_requests")
