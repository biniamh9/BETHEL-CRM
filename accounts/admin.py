from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class ChurchUserAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name", "email", "role", "title", "is_active")
    list_filter = ("role", "is_active", "is_staff")
    fieldsets = UserAdmin.fieldsets + (("Church role", {"fields": ("role", "title", "phone")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Church role", {"fields": ("first_name", "last_name", "email", "role", "title")}),)
