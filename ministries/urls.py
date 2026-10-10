from django.urls import path

from . import views

app_name = "ministries"

urlpatterns = [
    path("", views.ministry_list, name="list"),
    path("<slug:slug>/", views.ministry_detail, name="detail"),
    path("<slug:slug>/activities/new/", views.activity_edit, name="activity_new"),
    path("<slug:slug>/activities/<int:pk>/", views.activity_edit, name="activity_edit"),
    path("<slug:slug>/activities/<int:pk>/delete/", views.activity_delete, name="activity_delete"),
    path("<slug:slug>/activities.csv", views.activity_export, name="activity_export"),
    path("<slug:slug>/people/new/", views.participant_edit, name="participant_new"),
    path("<slug:slug>/people/<int:pk>/", views.participant_edit, name="participant_edit"),
]
