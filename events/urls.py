from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    path("portal/calendar/", views.month, name="calendar"),
    path("portal/calendar/<int:year>/<int:month>/", views.month, name="calendar_month"),
    path("portal/events/", views.upcoming, name="upcoming"),
    path("portal/events/new/", views.edit, name="new"),
    path("portal/events/<int:pk>/", views.detail, name="detail"),
    path("portal/events/<int:pk>/edit/", views.edit, name="edit"),
    path("portal/events/<int:pk>/delete/", views.delete, name="delete"),
    path("events/", views.public_events, name="public"),
    path("events/<int:pk>/", views.public_event_detail, name="public_detail"),
    path("events/<int:pk>/banner/", views.public_event_banner, name="public_banner"),
]
