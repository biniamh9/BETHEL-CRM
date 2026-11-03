from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("visit/", views.visit, name="visit"),
    path("activities/", views.public_activities, name="public_activities"),
    path("activities/photos/<int:pk>/image/", views.gallery_image, name="gallery_image"),
    path("site/hero-images/<int:pk>/", views.hero_image, name="hero_image"),
    path("portal/", views.portal, name="portal"),
    path("portal/site/hero-images/", views.hero_manager, name="hero_manager"),
    path("portal/site/hero-images/<path:placement>/", views.hero_edit, name="hero_edit"),
]
