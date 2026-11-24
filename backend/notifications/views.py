"""Administrator-only email diagnostics and credential management.

The deployment cannot be inspected from a laptop, so these endpoints let the
administrator confirm from the dashboard (or with a couple of curl calls) that
the Brevo key is valid, deliver a real test message, and install a corrected
key without shell or host access. They never return or log the key itself -
only a masked fragment and a stable fingerprint.
"""

import json
import logging
import urllib.error
import urllib.request

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdministrator

from .credentials import (
    clear_brevo_api_key,
    get_brevo_api_key,
    get_stored_api_key,
    set_brevo_api_key,
    validate_api_key,
)
from .diagnostics import key_fingerprint, mask_key

logger = logging.getLogger(__name__)

BREVO_ACCOUNT_URL = "https://api.brevo.com/v3/account"


def _brevo_account(key: str):
    """Ask Brevo whether ``key`` is valid.

    Returns ``(account, error)`` where exactly one is set. Server-side hiccups
    are retried once so a transient 5xx is not reported as a bad key.
    """
    request = urllib.request.Request(
        BREVO_ACCOUNT_URL,
        headers={"api-key": key, "accept": "application/json"},
        method="GET",
    )
    last_error = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(
                request, timeout=getattr(settings, "EMAIL_TIMEOUT", 15)
            ) as response:
                return json.loads(response.read().decode("utf-8") or "{}"), None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            if exc.code in (401, 403):
                return None, (exc.code, detail)
            last_error = f"HTTP {exc.code} {detail}".strip()
            logger.warning(
                "Brevo check attempt %s failed: %s", attempt + 1, last_error
            )
        except urllib.error.URLError as exc:
            last_error = f"Could not reach Brevo: {exc.reason}"
            logger.warning(
                "Brevo check attempt %s failed: %s", attempt + 1, last_error
            )
    return None, last_error


class EmailStatusView(APIView):
    """GET /api/notifications/status/ - is the configured email transport usable?"""

    permission_classes = [IsAuthenticated, IsAdministrator]

    def get(self, request):
        key = get_brevo_api_key()
        backend = settings.EMAIL_BACKEND or ""
        payload = {
            "backend": backend,
            "key": mask_key(key),
            "fingerprint": key_fingerprint(key),
            "source": "database" if get_stored_api_key() else "environment",
            "from_email": settings.DEFAULT_FROM_EMAIL,
            "owner_email": settings.OWNER_EMAIL,
            "frontend_url": settings.FRONTEND_URL,
            "commit": (settings.GIT_COMMIT or "")[:7] or "dev",
        }

        if "brevo_api" not in backend:
            payload.update(
                {
                    "ok": False,
                    "detail": (
                        "EMAIL_BACKEND is not the Brevo API backend, so no "
                        "message can be delivered from this deployment."
                    ),
                }
            )
            return Response(payload)

        if not key:
            payload.update({"ok": False, "detail": "No Brevo API key is set."})
            return Response(payload)

        account, error = _brevo_account(key)
        if error:
            if isinstance(error, tuple):
                code, detail = error
                logger.error(
                    "Brevo rejected the active key: HTTP %s %s (fingerprint=%s)",
                    code,
                    detail,
                    key_fingerprint(key),
                )
                payload.update(
                    {
                        "ok": False,
                        "status_code": code,
                        "detail": (
                            f"Brevo rejected the active key (HTTP {code}). "
                            "Install a valid key with "
                            "POST /api/notifications/key/ or replace "
                            "BREVO_API_KEY in the deployment environment. "
                            f"The active key has fingerprint {key_fingerprint(key)}."
                        ),
                    }
                )
            else:
                payload.update({"ok": False, "detail": error})
            return Response(payload, status=status.HTTP_502_BAD_GATEWAY)

        payload.update(
            {
                "ok": True,
                "detail": "Brevo accepted the active key.",
                "brevo_account": account.get("email") or account.get("companyName"),
            }
        )
        return Response(payload)


class EmailKeyView(APIView):
    """Install (POST) or remove (DELETE) the stored Brevo API key."""

    permission_classes = [IsAuthenticated, IsAdministrator]

    def post(self, request):
        raw = request.data.get("api_key") if isinstance(request.data, dict) else ""
        try:
            candidate = validate_api_key(raw)
        except ValueError as exc:
            return Response(
                {"ok": False, "detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate with Brevo *before* replacing anything, so a rejected key can
        # never disable an already working configuration.
        account, error = _brevo_account(candidate)
        if error:
            if isinstance(error, tuple):
                code, _detail = error
                return Response(
                    {
                        "ok": False,
                        "detail": (
                            f"Brevo rejected this key (HTTP {code}). Check that "
                            "it is the full API key from "
                            "https://app.brevo.com/settings/keys/api."
                        ),
                        "fingerprint": key_fingerprint(candidate),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {"ok": False, "detail": error},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        set_brevo_api_key(candidate)
        return Response(
            {
                "ok": True,
                "detail": "Brevo accepted the new key; it is now active.",
                "fingerprint": key_fingerprint(candidate),
                "brevo_account": account.get("email") or account.get("companyName"),
            }
        )

    def delete(self, request):
        clear_brevo_api_key()
        return Response(
            {
                "ok": True,
                "detail": (
                    "The stored key was removed; the environment value is "
                    "active again."
                ),
            }
        )


class EmailTestView(APIView):
    """POST /api/notifications/test/ - deliver a real message to OWNER_EMAIL."""

    permission_classes = [IsAuthenticated, IsAdministrator]

    def post(self, request):
        recipient = (
            request.data.get("to") if isinstance(request.data, dict) else ""
        ) or settings.OWNER_EMAIL
        recipient = (recipient or "").strip()
        if not recipient:
            return Response(
                {"detail": "OWNER_EMAIL is not configured and no 'to' was given."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.localtime()
        subject = "Fingerprint Access email test"
        text = (
            "This test message confirms that your Fingerprint Access Control "
            f"deployment can send email. Sent {now:%A, %d %B %Y %H:%M %Z} from "
            f"commit {(settings.GIT_COMMIT or 'dev')[:7]}."
        )
        html = (
            '<div style="font-family:Arial,sans-serif;padding:24px">'
            '<h2 style="color:#16a34a;margin:0 0 8px">Email is working</h2>'
            '<p style="color:#334155">Access alerts and password reset links '
            "from this deployment will be delivered.</p>"
            f'<p style="color:#64748b;font-size:13px">{text}</p>'
            "</div>"
        )
        message = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )
        message.attach_alternative(html, "text/html")

        try:
            message.send(fail_silently=False)
        except Exception as exc:  # noqa: BLE001 - report the cause to the admin
            logger.exception("Deployment test email failed")
            return Response(
                {
                    "ok": False,
                    "detail": f"Delivery failed: {type(exc).__name__}: {exc}",
                    "fingerprint": key_fingerprint(get_brevo_api_key()),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        logger.info("Deployment test email sent to %s", recipient)
        return Response({"ok": True, "detail": f"Test email sent to {recipient}."})
