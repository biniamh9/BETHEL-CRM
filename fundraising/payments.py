"""Stripe Checkout integration and email receipts.

Stripe is optional: when STRIPE_SECRET_KEY is empty the site shows only
offline giving options (Zelle, check, cash) and pledge forms.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def stripe_enabled():
    return bool(settings.STRIPE_SECRET_KEY)


def _stripe():
    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def create_checkout_session(donation, success_url, cancel_url):
    stripe = _stripe()
    donor = donation.donor
    description = f"Gift to {donation.campaign.name} — {settings.CHURCH['name']}"
    session = stripe.checkout.Session.create(
        mode="payment",
        submit_type="donate",
        customer_email=donor.email if donor and donor.email else None,
        line_items=[{
            "quantity": 1,
            "price_data": {
                "currency": "usd",
                "unit_amount": int(donation.amount * 100),
                "product_data": {"name": donation.campaign.name, "description": description},
            },
        }],
        metadata={"donation_id": str(donation.pk), "campaign": donation.campaign.slug},
        payment_intent_data={"description": description, "metadata": {"donation_id": str(donation.pk)}},
        success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel_url,
    )
    donation.stripe_session_id = session["id"]
    donation.save(update_fields=["stripe_session_id"])
    return session["url"]


def retrieve_session(session_id):
    return _stripe().checkout.Session.retrieve(session_id)


def parse_webhook(payload, signature):
    return _stripe().Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)


def apply_session(session):
    """Update our Donation from a Stripe Checkout Session. Safe to call repeatedly."""
    from .models import Donation

    donation = Donation.objects.filter(stripe_session_id=session["id"]).select_related("donor", "campaign").first()
    if donation is None:
        return None
    if session.get("payment_status") in ("paid", "no_payment_required"):
        was_pending = donation.status != Donation.Status.SUCCEEDED
        donation.mark_succeeded(payment_intent=session.get("payment_intent") or "")
        if was_pending:
            send_receipt(donation)
    return donation


def send_receipt(donation):
    donor = donation.donor
    if not donor or not donor.email:
        return
    body = render_to_string("fundraising/email_receipt.txt", {"d": donation, "church": settings.CHURCH})
    try:
        send_mail(
            f"Thank you for your gift — receipt {donation.receipt_number}",
            body, settings.DEFAULT_FROM_EMAIL, [donor.email],
        )
    except Exception:  # never let email trouble break a payment
        logger.exception("Could not send receipt for donation %s", donation.pk)
