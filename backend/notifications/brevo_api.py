"""
Django email backend that sends transactional mail through the Brevo (v3) API.

Brevo's HTTPS endpoint is used instead of an SMTP session: on Render the
outbound HTTP(S) is always available, there are no SMTP handshake/timeout
problems, and every send is visible in the Brevo dashboard. Configure it with:

    BREVO_API_KEY=xkeysib-...          # your Brevo API key
    EMAIL_BACKEND=notifications.brevo_api.BrevoAPIEmailBackend
    DEFAULT_FROM_EMAIL=Verified Sender <verified-sender@example.com>

The backend supports the plain Django EmailMessage contract used in this
project (subject, text body, text/html alternative, recipients).
"""

import json
import logging
import urllib.error
import urllib.request
from email.utils import parseaddr

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def _contact(raw: str) -> dict:
    """Convert 'Name <addr>' into Brevo's {name, email} object."""
    name, addr = parseaddr(raw or "")
    contact = {"email": addr}
    if name:
        contact["name"] = name
    return contact


class BrevoAPIEmailBackend(BaseEmailBackend):
    """Send emails with POST https://api.brevo.com/v3/smtp/email."""

    def send_messages(self, email_messages):
        results = 0
        for message in email_messages:
            self._send(message)
            results += 1
        return results

    def _send(self, message) -> None:
        payload = self._build_payload(message)

        request = urllib.request.Request(
            BREVO_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "api-key": settings.BREVO_API_KEY,
                "content-type": "application/json",
                "accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=getattr(settings, "EMAIL_TIMEOUT", 15)
            ) as response:
                body = json.loads(response.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            logger.error("Brevo API rejected email: HTTP %s %s", exc.code, detail)
            raise
        except urllib.error.URLError:
            logger.exception("Could not reach the Brevo API.")
            raise

        message_id = body.get("messageId", "")
        recipients = ", ".join(
            _contact(address).get("email", "") for address in message.recipients()
        )
        logger.info(
            "Email sent via Brevo API (messageId=%s) to %s", message_id, recipients
        )

    def _build_payload(self, message) -> dict:
        sender = _contact(
            getattr(message, "from_email", None) or settings.DEFAULT_FROM_EMAIL
        )
        html_body = None
        for content, mimetype in getattr(message, "alternatives", []) or []:
            if mimetype == "text/html" and html_body is None:
                html_body = content

        payload = {
            "sender": sender,
            "to": [_contact(address) for address in message.recipients()],
            "subject": message.subject or "",
            "textContent": message.body or "",
        }
        if html_body is not None:
            payload["htmlContent"] = html_body

        if not payload["to"]:
            raise ValueError("Brevo email has no recipients: %r" % message.subject)
        return payload
