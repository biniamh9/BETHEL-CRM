from django import forms
from django.contrib.auth.forms import UserCreationForm

from ministries.models import Ministry

from .models import User


class RegistrationForm(UserCreationForm):
    """Public sign-up. New accounts are members; the Pastor promotes leaders."""

    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    phone = forms.CharField(max_length=30, required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "last_name", "username", "email", "phone")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone")


class TeamMemberForm(forms.ModelForm):
    """Used by the Pastor to create or edit a login and assign ministries."""

    ministries = forms.ModelMultipleChoiceField(
        queryset=Ministry.objects.all(), required=False, widget=forms.CheckboxSelectMultiple,
        help_text="Ministry leaders can only open the portals ticked here.",
    )
    password = forms.CharField(
        widget=forms.PasswordInput(render_value=False), required=False,
        help_text="Set a temporary password. Leave blank when editing to keep the current one.",
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "username", "email", "phone", "role", "title", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["ministries"].initial = self.instance.led_ministries.all()
        else:
            self.fields["password"].required = True

    def clean_password(self):
        pw = self.cleaned_data.get("password")
        if pw:
            from django.contrib.auth.password_validation import validate_password

            validate_password(pw, self.instance)
        return pw

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("password"):
            user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            user.led_ministries.set(self.cleaned_data["ministries"])
        return user
