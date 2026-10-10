from django.urls import path

from . import views

app_name = "fundraising"

urlpatterns = [
    # public
    path("give/", views.give, name="give"),
    path("give/thank-you/", views.thanks, name="thanks"),
    path("give/<slug:slug>/", views.campaign_detail, name="campaign"),
    path("give/<slug:slug>/donate/", views.donate, name="donate"),
    path("give/<slug:slug>/pledge/", views.pledge, name="pledge"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
    # finance portal
    path("portal/fund/", views.dashboard, name="dashboard"),
    path("portal/fund/campaigns/new/", views.campaign_edit, name="campaign_new"),
    path("portal/fund/campaigns/<int:pk>/", views.campaign_edit, name="campaign_edit"),
    path("portal/fund/donations/", views.donation_list, name="donations"),
    path("portal/fund/donations/new/", views.donation_edit, name="donation_new"),
    path("portal/fund/donations/<int:pk>/", views.donation_edit, name="donation_edit"),
    path("portal/fund/donations/<int:pk>/receipt/", views.donation_receipt, name="receipt"),
    path("portal/fund/donors/", views.donor_list, name="donors"),
    path("portal/fund/donors/new/", views.donor_edit, name="donor_new"),
    path("portal/fund/donors/<int:pk>/", views.donor_detail, name="donor_detail"),
    path("portal/fund/donors/<int:pk>/edit/", views.donor_edit, name="donor_edit"),
    path("portal/fund/donors/<int:pk>/statement/<int:year>/", views.donor_statement, name="statement"),
    path("portal/fund/pledges/", views.pledge_list, name="pledges"),
    path("portal/fund/pledges/new/", views.pledge_edit, name="pledge_new"),
    path("portal/fund/pledges/<int:pk>/", views.pledge_edit, name="pledge_edit"),
]
