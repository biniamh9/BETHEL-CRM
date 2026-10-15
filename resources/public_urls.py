from django.urls import path

from . import views

app_name = "public_resources"

urlpatterns = [
    path("", views.public_resource_list, name="list"),
    path("<int:pk>/open/", views.public_resource_open, name="open"),
]
