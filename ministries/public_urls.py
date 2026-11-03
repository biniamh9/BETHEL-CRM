from django.urls import path

from . import views

app_name = "public_ministries"

urlpatterns = [
    path("", views.public_ministry_list, name="list"),
    path("birthdays/<int:pk>/", views.public_birthday_detail, name="birthday_detail"),
    path("birthdays/<int:pk>/image/", views.public_birthday_image, name="birthday_image"),
    path("<slug:slug>/members/<int:pk>/image/", views.public_member_spotlight_image, name="member_image"),
    path("<slug:slug>/", views.public_ministry_detail, name="detail"),
    path("<slug:slug>/contact/", views.public_ministry_inquiry, {"kind": "contact"}, name="contact"),
    path("<slug:slug>/join/", views.public_ministry_inquiry, {"kind": "join"}, name="join"),
]
