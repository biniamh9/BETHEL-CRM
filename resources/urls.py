from django.urls import path

from . import views

app_name = "resources"

urlpatterns = [
    path("", views.resource_list, name="list"),
    path("new/", views.edit, name="new"),
    path("<int:pk>/edit/", views.edit, name="edit"),
    path("<int:pk>/delete/", views.delete, name="delete"),
    path("<int:pk>/download/", views.download, name="download"),
]
