from django.contrib import admin

from .models import Activity, Ministry, Participant


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
