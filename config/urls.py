from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Bethel Eritrean Church — Administration"
admin.site.site_title = "Bethel CRM Admin"
admin.site.index_title = "Database administration"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("portal/ministries/", include("ministries.urls")),
    path("", include("fundraising.urls")),
    path("", include("core.urls")),
]
