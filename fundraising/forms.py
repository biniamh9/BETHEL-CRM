from decimal import Decimal

from django import forms

from .models import Donation, Donor, Pledge

PRESET_AMOUNTS = [50, 100, 250, 500, 1000, 2500]


class DateInput(forms.DateInput):
    input_type = "date"


class GiverFields(forms.Form):
    first_name = forms.CharField(max_length=80)
    last_name = forms.CharField(max_length=80)
    email = forms.EmailField(help_text="Your receipt is sent here.")
    phone = forms.CharField(max_length=30, required=False)


class PublicGiftForm(GiverFields):
    amount = forms.DecimalField(min_value=Decimal("5"), max_value=Decimal("100000"), decimal_places=2)
    show_on_wall = forms.BooleanField(required=False, initial=True, label="Show my name on the donor wall")
    public_message = forms.CharField(max_length=280, required=False, widget=forms.Textarea(attrs={"rows": 2}),
                                     label="A short message or blessing (optional)")


class PublicPledgeForm(GiverFields):
    total_amount = forms.DecimalField(min_value=Decimal("10"), decimal_places=2, label="Total pledge amount")
    frequency = forms.ChoiceField(choices=Pledge.Frequency.choices, initial=Pledge.Frequency.MONTHLY,
                                  label="How will you give?")
    target_date = forms.DateField(required=False, widget=DateInput(), label="Complete by (optional)")
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Notes for the finance team")


class DonationForm(forms.ModelForm):
    """Finance team records any gift: cash, check, Zelle, or a correction."""

    new_donor_first = forms.CharField(max_length=80, required=False, label="First name")
    new_donor_last = forms.CharField(max_length=80, required=False, label="Last name")
    new_donor_email = forms.EmailField(required=False, label="Email")
    new_donor_phone = forms.CharField(max_length=30, required=False, label="Phone")

    class Meta:
        model = Donation
        fields = ("campaign", "donor", "pledge", "amount", "method", "status", "received_on",
                  "reference", "show_on_wall", "notes")
        widgets = {"received_on": DateInput(), "notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["donor"].required = False
        self.fields["donor"].queryset = Donor.objects.order_by("first_name", "last_name")
        self.fields["pledge"].queryset = Pledge.objects.filter(status=Pledge.Status.ACTIVE).select_related("donor")
        self.fields["pledge"].help_text = "If this payment is toward a pledge, choose it so progress updates."

    def clean(self):
        data = super().clean()
        if data.get("donor") and data.get("new_donor_first"):
            raise forms.ValidationError("Choose an existing donor or enter a new one, not both.")
        pledge = data.get("pledge")
        donor = data.get("donor")
        if pledge and donor and pledge.donor_id != donor.pk:
            self.add_error("pledge", "That pledge belongs to a different donor.")
        if pledge and data.get("campaign") and pledge.campaign_id != data["campaign"].pk:
            self.add_error("pledge", "That pledge is for a different campaign.")
        return data

    def save(self, commit=True):
        donation = super().save(commit=False)
        if not donation.donor and self.cleaned_data.get("new_donor_first"):
            donation.donor = Donor.find_or_create(
                self.cleaned_data["new_donor_first"], self.cleaned_data.get("new_donor_last", ""),
                self.cleaned_data.get("new_donor_email", ""), self.cleaned_data.get("new_donor_phone", ""),
            )
        if not donation.donor and donation.pledge:
            donation.donor = donation.pledge.donor
        if commit:
            donation.save()
            if donation.pledge:
                donation.pledge.refresh_status()
        return donation


class DonorForm(forms.ModelForm):
    class Meta:
        model = Donor
        fields = ("first_name", "last_name", "organization", "email", "phone", "address", "city",
                  "state", "postal_code", "user", "notes")
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}


class PledgeForm(forms.ModelForm):
    class Meta:
        model = Pledge
        fields = ("donor", "campaign", "total_amount", "frequency", "start_date", "target_date", "status", "notes")
        widgets = {"start_date": DateInput(), "target_date": DateInput(), "notes": forms.Textarea(attrs={"rows": 2})}
