from django.contrib import admin
from django.urls import include, path

from ministries.views import all_activities

admin.site.site_header = "Bethel Eritrean Church — Administration"
admin.site.site_title = "Bethel CRM Admin"
admin.site.index_title = "Database administration"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("portal/activities/", all_activities, name="activities"),
    path("portal/ministries/", include("ministries.urls")),
    path("portal/resources/", include("resources.urls")),
    path("ministries/", include("ministries.public_urls")),
    path("resources/", include("resources.public_urls")),
    path("", include("events.urls")),
    path("", include("fundraising.urls")),
    path("", include("core.urls")),
]
