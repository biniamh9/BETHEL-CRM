from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import MinistryAccessRequest, User


@admin.register(User)
class ChurchUserAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name", "email", "role", "title", "is_active")
    list_filter = ("role", "is_active", "is_staff")
    fieldsets = UserAdmin.fieldsets + (("Church role", {"fields": ("role", "title", "phone")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Church role", {"fields": ("first_name", "last_name", "email", "role", "title")}),)


@admin.register(MinistryAccessRequest)
class MinistryAccessRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "created_at", "reviewed_by")
    list_filter = ("status", "created_at")
    filter_horizontal = ("ministries",)
    readonly_fields = ("created_at",)
    actions = ("approve_requests", "reject_requests")

    @admin.action(description="Approve selected requests and grant ministry access")
    def approve_requests(self, request, queryset):
        for access_request in queryset.select_related("user").prefetch_related("ministries"):
            access_request.approve(request.user)

    @admin.action(description="Reject selected requests without granting access")
    def reject_requests(self, request, queryset):
        for access_request in queryset:
            access_request.reject(request.user)
