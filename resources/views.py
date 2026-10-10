from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from ministries.models import Ministry

from .forms import ResourceForm
from .models import Resource


@login_required
def resource_list(request):
    qs = Resource.visible_to(request.user)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if request.GET.get("category"):
        qs = qs.filter(category=request.GET["category"])
    slug = request.GET.get("ministry", "")
    if slug == "church":
        qs = qs.filter(ministry=None)
    elif slug:
        qs = qs.filter(ministry__slug=slug)
    resources = list(qs)
    for r in resources:
        r.editable = r.can_edit(request.user)
    return render(request, "resources/list.html", {
        "resources": resources, "categories": Resource.Category.choices, "ministries": Ministry.objects.all(),
        "slug": slug, "can_add": request.user.is_leadership,
    })


def _get_visible(request, pk):
    resource = Resource.visible_to(request.user).filter(pk=pk).first()
    if resource is None:
        raise Http404
    return resource


@login_required
def download(request, pk):
    """Files are only served through this view, so permissions apply to downloads too."""
    resource = _get_visible(request, pk)
    if not resource.file:
        raise Http404
    try:
        return FileResponse(resource.file.open("rb"), as_attachment=request.GET.get("view") != "1",
                            filename=resource.filename)
    except NotImplementedError:  # remote storage (Supabase/S3) gives a signed URL instead
        return redirect(resource.file.url)


@login_required
def edit(request, pk=None):
    resource = get_object_or_404(Resource, pk=pk) if pk else None
    if resource and not resource.can_edit(request.user):
        raise PermissionDenied
    if not request.user.is_leadership:
        raise PermissionDenied
    initial = {}
    if not resource and request.GET.get("ministry"):
        initial["ministry"] = Ministry.objects.filter(slug=request.GET["ministry"]).first()
    form = ResourceForm(request.POST or None, request.FILES or None, instance=resource, user=request.user, initial=initial)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if not obj.uploaded_by_id:
            obj.uploaded_by = request.user
        obj.save()
        messages.success(request, f"Saved “{obj.title}”.")
        return redirect("resources:list")
    return render(request, "resources/form.html", {"form": form, "resource": resource})


@login_required
def delete(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    if not resource.can_edit(request.user):
        raise PermissionDenied
    if request.method == "POST":
        if resource.file:
            resource.file.delete(save=False)
        resource.delete()
        messages.success(request, "Resource deleted.")
    return redirect("resources:list")
