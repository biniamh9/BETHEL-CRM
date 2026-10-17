from datetime import datetime, time, timedelta
from pathlib import Path

from django import forms
from django.conf import settings
from django.utils import timezone

from .models import Event


class ChildEventRegistrationForm(forms.Form):
    parent_name = forms.CharField(max_length=160, label="Parent or guardian name")
    email = forms.EmailField(label="Parent or guardian email")
    phone = forms.CharField(max_length=30, label="Parent or guardian phone")
    children = forms.CharField(
        label="Children attending",
        help_text="List each child’s first name and age (for example: Sara, age 8; Noah, age 11).",
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    notes = forms.CharField(
        required=False, label="Anything the ministry team should know?",
        help_text="Optional. Do not include medical records or other sensitive information.",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    consent = forms.BooleanField(
        label="I am the parent or legal guardian and may register these children for this event."
    )
    website = forms.CharField(required=False, widget=forms.HiddenInput, label="Leave blank")

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("Unable to submit this form.")
        return ""


class EventForm(forms.ModelForm):
    """Date and times are separate inputs (easier on phones); combined into start/end on save."""

    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    start_time = forms.TimeField(required=False, widget=forms.TimeInput(attrs={"type": "time"}))
    end_time = forms.TimeField(required=False, widget=forms.TimeInput(attrs={"type": "time"}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}),
                               help_text="Only for events that run over several days (e.g. a retreat).")
    flyer_upload = forms.FileField(
        required=False,
        label="Flyer or banner image",
        help_text="JPG, PNG, or WebP; maximum 3 MB.",
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )

    class Meta:
        model = Event
        fields = ("title", "kind", "ministry", "all_day", "location", "description", "banner", "banner_url", "repeat", "repeat_until", "is_public")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "repeat_until": forms.DateInput(attrs={"type": "date"}),
        }

    field_order = ("title", "kind", "ministry", "date", "start_time", "end_time", "end_date", "all_day",
                   "location", "description", "banner", "flyer_upload", "banner_url", "repeat", "repeat_until", "is_public")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if not settings.UPLOADS_ENABLED:
            self.fields.pop("banner")
            self.fields["flyer_upload"].help_text = "Stored securely with the event in the church database. JPG, PNG, or WebP; maximum 3 MB."
        else:
            self.fields.pop("flyer_upload")
        self.fields["ministry"].queryset = user.editable_ministries()
        if not user.can_create_churchwide_events:
            self.fields["ministry"].required = True
            self.fields["ministry"].empty_label = None
            self.fields["ministry"].help_text = ""
        if self.instance.pk:
            s = timezone.localtime(self.instance.start)
            self.initial.update(date=s.date(), start_time=None if self.instance.all_day else s.time())
            if self.instance.end:
                e = timezone.localtime(self.instance.end)
                self.initial["end_time"] = None if self.instance.all_day else e.time()
                if e.date() != s.date():
                    self.initial["end_date"] = e.date()

    def clean_flyer_upload(self):
        upload = self.cleaned_data.get("flyer_upload")
        if not upload:
            return upload
        if upload.size > 3 * 1024 * 1024:
            raise forms.ValidationError("The flyer must be 3 MB or smaller.")
        suffix = Path(upload.name).suffix.lower()
        head = upload.read(16)
        upload.seek(0)
        detected = None
        if head.startswith(b"\x89PNG\r\n\x1a\n"):
            detected = "image/png"
        elif head.startswith(b"\xff\xd8\xff"):
            detected = "image/jpeg"
        elif head.startswith(b"RIFF") and head[8:12] == b"WEBP":
            detected = "image/webp"
        allowed_suffixes = {".jpg", ".jpeg", ".png", ".webp"}
        if suffix not in allowed_suffixes or detected is None:
            raise forms.ValidationError("Upload a valid JPG, PNG, or WebP image.")
        upload.detected_content_type = detected
        return upload

    def save(self, commit=True):
        event = super().save(commit=False)
        upload = self.cleaned_data.get("flyer_upload")
        if upload:
            event.banner_blob = upload.read()
            event.banner_content_type = upload.detected_content_type
            event.banner_filename = Path(upload.name).name[:180]
        if commit:
            event.save()
            self.save_m2m()
        return event

    def clean(self):
        data = super().clean()
        d = data.get("date")
        if not d:
            return data
        if not data.get("all_day") and not data.get("start_time"):
            self.add_error("start_time", "Add a start time, or tick 'All day'.")
            return data
        tz = timezone.get_current_timezone()
        start = timezone.make_aware(datetime.combine(d, time(0, 0) if data.get("all_day") else data["start_time"]), tz)
        end = None
        end_d = data.get("end_date") or d
        if data.get("all_day"):
            if data.get("end_date"):
                end = timezone.make_aware(datetime.combine(end_d, time(23, 59)), tz)
        elif data.get("end_time"):
            end = timezone.make_aware(datetime.combine(end_d, data["end_time"]), tz)
            if end <= start:
                self.add_error("end_time", "The end must be after the start.")
                end = None
        if data.get("repeat") != Event.Repeat.NONE and data.get("end_date") and end_d - d > timedelta(days=6):
            self.add_error("end_date", "Repeating events can't run longer than a week.")
        if data.get("repeat_until") and data["repeat_until"] < d:
            self.add_error("repeat_until", "Must be on or after the first date.")
        self.instance.start, self.instance.end = start, end
        return data
