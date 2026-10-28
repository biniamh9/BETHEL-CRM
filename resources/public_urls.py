from django.urls import path

from . import views

app_name = "public_resources"

urlpatterns = [
    path("", views.public_resource_list, name="list"),
    path("archive/", views.public_archive, name="archive"),
    path("archive/albums/<slug:slug>/", views.public_album_detail, name="album_detail"),
    path("<int:pk>/open/", views.public_resource_open, name="open"),
]
