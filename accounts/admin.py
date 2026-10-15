from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db import transaction
from django.utils import timezone

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
        with transaction.atomic():
            for access_request in queryset.select_related("user").prefetch_related("ministries"):
                user = access_request.user
                user.led_ministries.add(*access_request.ministries.all())
                if user.role == User.Role.MEMBER:
                    user.role = User.Role.LEADER
                    user.save(update_fields=["role"])
                access_request.status = MinistryAccessRequest.Status.APPROVED
                access_request.reviewed_by = request.user
                access_request.reviewed_at = timezone.now()
                access_request.save(update_fields=["status", "reviewed_by", "reviewed_at"])

    @admin.action(description="Reject selected requests without granting access")
    def reject_requests(self, request, queryset):
        queryset.update(
            status=MinistryAccessRequest.Status.REJECTED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
