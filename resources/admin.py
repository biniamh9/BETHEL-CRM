from django.contrib import admin

from .models import Resource


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "ministry", "audience", "uploaded_by", "created_at")
    list_filter = ("category", "audience", "ministry")
    search_fields = ("title", "description")
