from django import forms

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
        if not user.is_leadership:  # members can't post; view guards this too
            self.fields["audience"].choices = [c for c in Resource.Audience.choices if c[0] == "members"]
