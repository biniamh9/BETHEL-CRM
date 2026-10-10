from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
    path("profile/", views.profile, name="profile"),
    path(
        "password/",
        auth_views.PasswordChangeView.as_view(
            template_name="accounts/simple_form.html",
            success_url=reverse_lazy("accounts:profile"),
            extra_context={"title": "Change password"},
        ),
        name="password_change",
    ),
    path(
        "password/reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/simple_form.html",
            email_template_name="accounts/password_reset_email.txt",
            success_url=reverse_lazy("accounts:password_reset_done"),
            extra_context={"title": "Reset your password"},
        ),
        name="password_reset",
    ),
    path(
        "password/reset/sent/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/message.html",
            extra_context={"title": "Check your email", "body": "If that address has an account, a reset link is on its way."},
        ),
        name="password_reset_done",
    ),
    path(
        "password/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/simple_form.html",
            success_url=reverse_lazy("accounts:login"),
            extra_context={"title": "Choose a new password"},
        ),
        name="password_reset_confirm",
    ),
    path("team/", views.team_list, name="team"),
    path("team/new/", views.team_edit, name="team_new"),
    path("team/<int:pk>/", views.team_edit, name="team_edit"),
]
