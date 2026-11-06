"""Small Twilio REST adapter. Credentials are read only from environment-backed settings."""

import base64
import json
from urllib import parse, request

from django.conf import settings


def sms_is_configured():
    return all((
        getattr(settings, "TWILIO_ACCOUNT_SID", ""),
        getattr(settings, "TWILIO_AUTH_TOKEN", ""),
        getattr(settings, "TWILIO_FROM_NUMBER", ""),
    ))


def send_sms(to_number, body):
    if not sms_is_configured():
        raise RuntimeError("SMS delivery is not configured.")
    sid = settings.TWILIO_ACCOUNT_SID
    token = settings.TWILIO_AUTH_TOKEN
    endpoint = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    payload = parse.urlencode({"To": to_number, "From": settings.TWILIO_FROM_NUMBER, "Body": body}).encode()
    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
    req = request.Request(endpoint, data=payload, headers={"Authorization": f"Basic {auth}"})
    try:
        with request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
    except Exception as exc:
        raise RuntimeError("The text provider rejected the message.") from exc
    return data.get("sid", "sent")
