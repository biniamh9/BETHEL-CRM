from django.contrib import admin

from .models import Campaign, Donation, Donor, Pledge


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "goal_amount", "opening_balance", "is_active", "is_public")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Donor)
class DonorAdmin(admin.ModelAdmin):
    list_display = ("__str__", "email", "phone", "user")
    search_fields = ("first_name", "last_name", "email", "phone", "organization")


@admin.register(Pledge)
class PledgeAdmin(admin.ModelAdmin):
    list_display = ("donor", "campaign", "total_amount", "frequency", "status")
    list_filter = ("status", "frequency", "campaign")


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ("received_on", "donor", "amount", "method", "status", "campaign")
    list_filter = ("status", "method", "campaign")
    search_fields = ("donor__first_name", "donor__last_name", "donor__email", "reference")
    date_hierarchy = "received_on"
    readonly_fields = ("stripe_session_id", "stripe_payment_intent", "created_at")
