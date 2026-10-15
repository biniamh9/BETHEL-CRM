from django.contrib import admin

from .models import Activity, Ministry, MinistryAnnouncement, MinistryInquiry, Participant


@admin.register(Ministry)
class MinistryAdmin(admin.ModelAdmin):
    list_display = ("name", "leader_display", "sort_order")
    list_editable = ("sort_order",)
    filter_horizontal = ("leaders",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("date", "ministry", "title", "kind", "attendance", "created_by")
    list_filter = ("ministry", "kind")
    search_fields = ("title", "summary")
    date_hierarchy = "date"


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ("__str__", "ministry", "kind", "phone", "is_active")
    list_filter = ("ministry", "kind", "is_active")
    search_fields = ("first_name", "last_name", "email", "phone")


@admin.register(MinistryAnnouncement)
class MinistryAnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "ministry", "status", "updated_at")
    list_filter = ("status", "ministry")


@admin.register(MinistryInquiry)
class MinistryInquiryAdmin(admin.ModelAdmin):
    list_display = ("name", "ministry", "kind", "status", "created_at")
    list_filter = ("kind", "status", "ministry")
    search_fields = ("name", "email", "message")
