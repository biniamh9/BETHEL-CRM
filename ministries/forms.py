from django import forms

from pathlib import Path
from datetime import date

from core.image_processing import ImageProcessingError, optimize_image_upload, validate_image_upload
from .models import Activity, BirthdayCelebration, BirthdayWish, GalleryAlbum, GalleryPhoto, Ministry, MinistryInquiry, MinistryMemberSpotlight, Participant, StudentAchievement


class DateInput(forms.DateInput):
    input_type = "date"


class TimeInput(forms.TimeInput):
    input_type = "time"


class ActivityForm(forms.ModelForm):
    image = forms.FileField(
        required=False, label="Activity photo",
        help_text="Optional JPG, PNG, or WebP; maximum 4 MB. You can add another photo each time you edit.",
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp", "data-optimize-image": "1"}),
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
        if not upload:
            return upload
        upload = validate_gallery_image(upload)
        try:
            self.optimized_image = optimize_image_upload(upload)
        except ImageProcessingError as exc:
            raise forms.ValidationError(str(exc)) from exc
        return upload

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


class MinistryMemberSpotlightForm(forms.ModelForm):
    image = forms.FileField(
        required=False, label="Member photo",
        help_text="Optional JPG, PNG, or WebP. It will be resized below 1 MB.",
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp", "data-optimize-image": "1"}),
    )
    remove_image = forms.BooleanField(required=False, label="Remove the current photo and use the placeholder")

    class Meta:
        model = MinistryMemberSpotlight
        fields = ("display_name", "role", "short_message", "is_public", "sort_order")
        widgets = {"short_message": forms.Textarea(attrs={"rows": 4, "maxlength": 500})}

    def clean_image(self):
        upload = self.cleaned_data.get("image")
        if not upload:
            return upload
        upload = validate_gallery_image(upload)
        try:
            self.optimized_image = optimize_image_upload(upload)
        except ImageProcessingError as exc:
            raise forms.ValidationError(str(exc)) from exc
        return upload

    def save(self, commit=True):
        spotlight = super().save(commit=False)
        if self.cleaned_data.get("remove_image"):
            spotlight.image_blob = b""
            spotlight.image_content_type = ""
            spotlight.image_filename = ""
        upload = self.cleaned_data.get("image")
        if upload:
            data, filename, content_type = self.optimized_image
            spotlight.image_blob = data
            spotlight.image_content_type = content_type
            spotlight.image_filename = filename
        if commit:
            spotlight.save()
        return spotlight


class BirthdayCelebrationForm(forms.ModelForm):
    image = forms.FileField(
        required=False, label="Birthday photo",
        help_text="Optional JPG, PNG, or WebP. It will be automatically resized below 1 MB.",
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp", "data-optimize-image": "1"}),
    )
    remove_image = forms.BooleanField(required=False, label="Remove the current photo and use the birthday placeholder")

    class Meta:
        model = BirthdayCelebration
        fields = ("member_name", "celebration_date", "message", "visibility", "consent_confirmed", "is_active")
        widgets = {
            "celebration_date": DateInput(),
            "message": forms.Textarea(attrs={"rows": 5, "maxlength": 800}),
        }
        labels = {"message": "Birthday message from the ministry", "visibility": "Who can see the celebration?"}
        help_texts = {
            "visibility": "Public celebrations may appear on the homepage and can be opened from shared links. Wishes and reactions still require sign-in.",
        }

    def clean_consent_confirmed(self):
        if not self.cleaned_data.get("consent_confirmed"):
            raise forms.ValidationError("Consent is required for the selected visibility and social sharing.")
        return True

    def clean_image(self):
        upload = self.cleaned_data.get("image")
        if not upload:
            return upload
        upload = validate_gallery_image(upload)
        try:
            self.optimized_image = optimize_image_upload(upload)
        except ImageProcessingError as exc:
            raise forms.ValidationError(str(exc)) from exc
        return upload

    def save(self, commit=True):
        celebration = super().save(commit=False)
        if self.cleaned_data.get("remove_image"):
            celebration.image_blob = b""
            celebration.image_content_type = ""
            celebration.image_filename = ""
        if self.cleaned_data.get("image"):
            celebration.image_blob, celebration.image_filename, celebration.image_content_type = self.optimized_image
        if commit:
            celebration.save()
        return celebration


class BirthdayWishForm(forms.ModelForm):
    class Meta:
        model = BirthdayWish
        fields = ("message",)
        labels = {"message": "Write a warm birthday wish"}
        widgets = {"message": forms.Textarea(attrs={"rows": 3, "maxlength": 600, "placeholder": "Share a kind message…"})}


class StudentAchievementForm(forms.ModelForm):
    image = forms.FileField(
        required=False, label="Student recognition photo",
        help_text="Optional JPG, PNG, or WebP. It will be automatically resized below 1 MB.",
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp", "data-optimize-image": "1"}),
    )
    remove_image = forms.BooleanField(required=False, label="Remove the current photo and use the achievement placeholder")

    class Meta:
        model = StudentAchievement
        fields = (
            "student_name", "kind", "recognition_title", "recognition_date",
            "academic_year", "message", "visibility", "consent_confirmed", "is_active",
        )
        widgets = {
            "recognition_date": DateInput(),
            "message": forms.Textarea(attrs={"rows": 5, "maxlength": 1000}),
        }
        labels = {
            "student_name": "Student display name",
            "kind": "Recognition type",
            "recognition_title": "Award or recognition",
            "visibility": "Who can see this recognition?",
        }
        help_texts = {
            "visibility": "Public recognitions may appear on the homepage and Achievement Corner. Members-only recognitions stay inside the portal.",
        }

    def clean_consent_confirmed(self):
        if not self.cleaned_data.get("consent_confirmed"):
            raise forms.ValidationError("Parent or legal guardian consent is required before saving this recognition.")
        return True

    def clean_image(self):
        upload = self.cleaned_data.get("image")
        if not upload:
            return upload
        upload = validate_gallery_image(upload)
        try:
            self.optimized_image = optimize_image_upload(upload)
        except ImageProcessingError as exc:
            raise forms.ValidationError(str(exc)) from exc
        return upload

    def save(self, commit=True):
        achievement = super().save(commit=False)
        if self.cleaned_data.get("remove_image"):
            achievement.image_blob = b""
            achievement.image_content_type = ""
            achievement.image_filename = ""
        if self.cleaned_data.get("image"):
            achievement.image_blob, achievement.image_filename, achievement.image_content_type = self.optimized_image
        if commit:
            achievement.save()
        return achievement


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
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp", "data-optimize-image": "1"}),
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
        upload = validate_gallery_image(self.cleaned_data["image"])
        try:
            self.optimized_image = optimize_image_upload(upload)
        except ImageProcessingError as exc:
            raise forms.ValidationError(str(exc)) from exc
        return upload

    def save(self, commit=True):
        photo = super().save(commit=False)
        upload = self.cleaned_data["image"]
        photo.image_blob, photo.filename, photo.content_type = self.optimized_image
        if commit:
            photo.save()
        return photo


class PortalGalleryPhotoForm(GalleryPhotoForm):
    ministry = forms.ModelChoiceField(queryset=Ministry.objects.none())
    album = forms.ModelChoiceField(queryset=GalleryAlbum.objects.none(), required=False, help_text="Optional photo album.")

    field_order = ("ministry", "album", "image", "caption", "occasion", "year", "is_public")

    def __init__(self, *args, ministries=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ministry"].queryset = ministries if ministries is not None else Ministry.objects.none()
        self.fields["album"].queryset = GalleryAlbum.objects.filter(ministry__in=self.fields["ministry"].queryset)

    def clean(self):
        cleaned = super().clean()
        album, ministry = cleaned.get("album"), cleaned.get("ministry")
        if album and ministry and album.ministry_id != ministry.pk:
            self.add_error("album", "Choose an album belonging to the selected ministry.")
        return cleaned


class GalleryAlbumForm(forms.ModelForm):
    ministry = forms.ModelChoiceField(queryset=Ministry.objects.none())

    class Meta:
        model = GalleryAlbum
        fields = ("ministry", "title", "event_date", "location", "description", "is_public")
        widgets = {"event_date": DateInput(), "description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, ministries=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ministry"].queryset = ministries if ministries is not None else Ministry.objects.none()


class GalleryPhotoMetadataForm(forms.ModelForm):
    class Meta:
        model = GalleryPhoto
        fields = ("album", "caption", "occasion", "year", "is_public")

    def __init__(self, *args, ministry=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["album"].queryset = ministry.gallery_albums.all() if ministry else GalleryAlbum.objects.none()


def validate_gallery_image(upload):
    try:
        return validate_image_upload(upload)
    except ImageProcessingError as exc:
        raise forms.ValidationError(str(exc)) from exc
