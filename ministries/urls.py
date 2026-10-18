from django.urls import path

from . import views

app_name = "ministries"

urlpatterns = [
    path("", views.ministry_list, name="list"),
    path("photos/", views.gallery_hub, name="gallery_hub"),
    path("<slug:slug>/profile/edit/", views.ministry_profile_edit, name="profile_edit"),
    path("<slug:slug>/gallery/", views.gallery_manage, name="gallery"),
    path("<slug:slug>/gallery/<int:pk>/delete/", views.gallery_delete, name="gallery_delete"),
    path("<slug:slug>/inquiries/<int:pk>/status/", views.inquiry_status, name="inquiry_status"),
    path("<slug:slug>/", views.ministry_detail, name="detail"),
    path("<slug:slug>/activities/new/", views.activity_edit, name="activity_new"),
    path("<slug:slug>/activities/<int:pk>/", views.activity_edit, name="activity_edit"),
    path("<slug:slug>/activities/<int:pk>/delete/", views.activity_delete, name="activity_delete"),
    path("<slug:slug>/activities.csv", views.activity_export, name="activity_export"),
    path("<slug:slug>/people/new/", views.participant_edit, name="participant_new"),
    path("<slug:slug>/people/<int:pk>/", views.participant_edit, name="participant_edit"),
]
