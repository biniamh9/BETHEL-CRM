from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("activities/", views.public_activities, name="public_activities"),
    path("portal/", views.portal, name="portal"),
]
