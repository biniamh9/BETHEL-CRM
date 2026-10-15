from django import forms

from .models import Activity, Ministry, MinistryInquiry, Participant


class DateInput(forms.DateInput):
    input_type = "date"


class TimeInput(forms.TimeInput):
    input_type = "time"


class ActivityForm(forms.ModelForm):
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
        fields = ("description", "mission", "serves", "regular_activities", "participation")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "mission": forms.Textarea(attrs={"rows": 4}),
            "serves": forms.Textarea(attrs={"rows": 3}),
            "regular_activities": forms.Textarea(attrs={"rows": 4}),
            "participation": forms.Textarea(attrs={"rows": 3}),
        }
