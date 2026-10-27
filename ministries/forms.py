from django import forms

from pathlib import Path
from datetime import date

from .models import Activity, GalleryPhoto, Ministry, MinistryInquiry, Participant


class DateInput(forms.DateInput):
    input_type = "date"


class TimeInput(forms.TimeInput):
    input_type = "time"


class ActivityForm(forms.ModelForm):
    image = forms.FileField(
        required=False, label="Activity photo",
        help_text="Optional JPG, PNG, or WebP; maximum 4 MB. You can add another photo each time you edit.",
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )
    image_caption = forms.CharField(
        required=False, max_length=220, label="Photo caption",
        help_text="Describe who or what is shown. Required when uploading a photo.",
    )
    class Meta:
        model = Activity
        fields = (
            "title", "kind", "date", "start_time", "location", "attendance",
            "attendees", "volunteer_hours", "summary", "follow_up", "is_public",
        )
        widgets = {
            "date": DateInput(),
            "start_time": TimeInput(),
            "attendees": forms.CheckboxSelectMultiple,
            "summary": forms.Textarea(attrs={"rows": 4}),
            "follow_up": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, ministry=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = ministry.participants.filter(is_active=True) if ministry else Participant.objects.none()
        self.fields["attendees"].queryset = qs
        self.fields["attendees"].required = False
        if not qs.exists():
            self.fields.pop("attendees")

    def clean_image(self):
        upload = self.cleaned_data.get("image")
        return validate_gallery_image(upload) if upload else upload

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("image") and not cleaned.get("image_caption", "").strip():
            self.add_error("image_caption", "Add a caption for this photo.")
        return cleaned


class ParticipantForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = (
            "first_name", "last_name", "kind", "phone", "email", "guardian_name",
            "guardian_phone", "birth_year", "joined_on", "is_active", "notes",
        )
        widgets = {"joined_on": DateInput(), "notes": forms.Textarea(attrs={"rows": 3})}


class MinistryContactForm(forms.ModelForm):
    website = forms.CharField(required=False, widget=forms.HiddenInput, label="Leave blank")

    class Meta:
        model = MinistryInquiry
        fields = ("name", "email", "phone", "message")
        widgets = {"message": forms.Textarea(attrs={"rows": 5})}

    def clean_website(self):
        value = self.cleaned_data.get("website")
        if value:
            raise forms.ValidationError("Unable to submit this form.")
        return value


class MinistryJoinForm(MinistryContactForm):
    class Meta(MinistryContactForm.Meta):
        fields = ("name", "email", "phone", "area_interest", "message")
        labels = {"area_interest": "Area of interest", "message": "Additional message"}


class MinistryProfileForm(forms.ModelForm):
    class Meta:
        model = Ministry
        fields = (
            "description", "mission", "serves", "regular_activities", "participation",
            "cash_app", "zelle",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "mission": forms.Textarea(attrs={"rows": 4}),
            "serves": forms.Textarea(attrs={"rows": 3}),
            "regular_activities": forms.Textarea(attrs={"rows": 4}),
            "participation": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_cash_app(self):
        value = self.cleaned_data.get("cash_app", "").strip()
        if value and not value.startswith("$"):
            value = f"${value}"
        if value and (" " in value or len(value) < 2):
            raise forms.ValidationError("Enter a valid public $Cashtag, such as $BethelYouth.")
        return value


class GalleryPhotoForm(forms.ModelForm):
    image = forms.FileField(
        label="Photo", help_text="JPG, PNG, or WebP; maximum 4 MB.",
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )

    class Meta:
        model = GalleryPhoto
        fields = ("caption", "occasion", "year", "is_public")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["year"].initial = date.today().year

    def clean_year(self):
        year = self.cleaned_data["year"]
        if not 2000 <= year <= date.today().year + 1:
            raise forms.ValidationError("Enter a year between 2000 and next year.")
        return year

    def clean_image(self):
        return validate_gallery_image(self.cleaned_data["image"])

    def save(self, commit=True):
        photo = super().save(commit=False)
        upload = self.cleaned_data["image"]
        photo.image_blob = upload.read()
        photo.content_type = upload.detected_content_type
        photo.filename = Path(upload.name).name[:180]
        if commit:
            photo.save()
        return photo


class PortalGalleryPhotoForm(GalleryPhotoForm):
    ministry = forms.ModelChoiceField(queryset=Ministry.objects.none())

    field_order = ("ministry", "image", "caption", "occasion", "year", "is_public")

    def __init__(self, *args, ministries=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ministry"].queryset = ministries if ministries is not None else Ministry.objects.none()


def validate_gallery_image(upload):
    if upload.size > 4 * 1024 * 1024:
        raise forms.ValidationError("The photo must be 4 MB or smaller.")
    head = upload.read(16)
    upload.seek(0)
    suffix = Path(upload.name).suffix.lower()
    detected = None
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        detected = "image/png"
    elif head.startswith(b"\xff\xd8\xff"):
        detected = "image/jpeg"
    elif head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        detected = "image/webp"
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"} or not detected:
        raise forms.ValidationError("Upload a valid JPG, PNG, or WebP image.")
    upload.detected_content_type = detected
    return upload
