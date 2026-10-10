from django.contrib import admin

from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "start", "ministry", "kind", "repeat", "is_public")
    list_filter = ("kind", "repeat", "is_public", "ministry")
    search_fields = ("title", "location", "description")
