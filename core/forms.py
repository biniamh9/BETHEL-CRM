from django import forms


class HeroImageForm(forms.Form):
    POSITION_CHOICES = (
        ("center center", "Center"),
        ("center top", "Top"),
        ("center 35%", "Upper center"),
        ("center bottom", "Bottom"),
        ("left center", "Left"),
        ("right center", "Right"),
    )

    image = forms.ImageField(
        required=False,
        help_text="JPG, PNG, or WebP. The portal automatically resizes and compresses it below 1 MB.",
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp", "data-optimize-image": ""}),
    )
    alt_text = forms.CharField(
        max_length=220, required=False,
        help_text="Briefly describe the image for visitors who use a screen reader.",
    )
    position = forms.ChoiceField(
        choices=POSITION_CHOICES,
        help_text="Choose which part of the photo remains visible on different screen sizes.",
    )
    remove_image = forms.BooleanField(
        required=False,
        label="Remove the uploaded image and restore the original design",
    )
