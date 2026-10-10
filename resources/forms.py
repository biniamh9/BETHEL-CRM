from django import forms
from django.conf import settings

from .models import Resource


class ResourceForm(forms.ModelForm):
    class Meta:
        model = Resource
        fields = ("title", "category", "ministry", "audience", "file", "url", "description", "pinned")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ministry"].queryset = user.editable_ministries()
        if not user.is_church_admin:
            self.fields.pop("pinned")
        if not settings.UPLOADS_ENABLED:
            # e.g. on Vercel before Supabase Storage is configured: links only
            self.fields.pop("file")
            self.fields["url"].required = True
            self.fields["url"].help_text = "Paste a Google Drive, Dropbox, YouTube or website link. (File uploads aren't set up on this server yet.)"
        else:
            self.fields["file"].help_text = f"Up to {settings.MAX_UPLOAD_MB} MB."
        if not user.is_leadership:  # members can't post; view guards this too
            self.fields["audience"].choices = [c for c in Resource.Audience.choices if c[0] == "members"]
