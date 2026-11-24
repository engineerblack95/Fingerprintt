"""Administrator-only email diagnostics endpoints.

The deployment cannot be inspected from a laptop, so these two endpoints let
the administrator confirm from the dashboard (or with two curl calls) that the
Brevo key is valid and that a real message can be delivered. They never return
or log the key itself - only a masked fragment and a stable fingerprint.
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

from .diagnostics import key_fingerprint, mask_key

logger = logging.getLogger(__name__)

BREVO_ACCOUNT_URL = "https://api.brevo.com/v3/account"


class EmailStatusView(APIView):
    """GET /api/notifications/status/ - is the configured email transport usable?"""

    permission_classes = [IsAuthenticated, IsAdministrator]

    def get(self, request):
        key = settings.BREVO_API_KEY
        backend = settings.EMAIL_BACKEND or ""
        payload = {
            "backend": backend,
            "key": mask_key(key),
            "fingerprint": key_fingerprint(key),
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
            payload.update(
                {"ok": False, "detail": "BREVO_API_KEY is not set."}
            )
            return Response(payload)

        request_obj = urllib.request.Request(
            BREVO_ACCOUNT_URL,
            headers={"api-key": key, "accept": "application/json"},
            method="GET",
        )
        body = None
        last_error = None
        for attempt in range(2):
            try:
                with urllib.request.urlopen(
                    request_obj, timeout=getattr(settings, "EMAIL_TIMEOUT", 15)
                ) as response:
                    body = json.loads(response.read().decode("utf-8") or "{}")
                break
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:400]
                if exc.code in (401, 403):
                    logger.error(
                        "Deployment Brevo key rejected: HTTP %s %s "
                        "(fingerprint=%s)",
                        exc.code,
                        detail,
                        key_fingerprint(key),
                    )
                    payload.update(
                        {
                            "ok": False,
                            "status_code": exc.code,
                            "detail": (
                                "Brevo rejected this deployment's key "
                                f"(HTTP {exc.code}). Replace BREVO_API_KEY "
                                "with the key that works locally and redeploy. "
                                "The currently deployed key has fingerprint "
                                f"{key_fingerprint(key)}."
                            ),
                        }
                    )
                    return Response(payload, status=status.HTTP_502_BAD_GATEWAY)
                last_error = f"HTTP {exc.code} {detail}".strip()
                logger.warning(
                    "Brevo health check attempt %s failed: %s", attempt + 1, last_error
                )
            except urllib.error.URLError as exc:
                last_error = f"Could not reach Brevo: {exc.reason}"
                logger.warning(
                    "Brevo health check attempt %s failed: %s", attempt + 1, last_error
                )

        if body is None:
            payload.update(
                {
                    "ok": False,
                    "detail": (
                        "Brevo did not answer the health check "
                        f"({last_error}). This is usually temporary; try the "
                        "test email to confirm delivery."
                    ),
                }
            )
            return Response(payload, status=status.HTTP_502_BAD_GATEWAY)

        payload.update(
            {
                "ok": True,
                "detail": "Brevo accepted the configured key.",
                "brevo_account": body.get("email") or body.get("companyName"),
            }
        )
        return Response(payload)


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
                    "fingerprint": key_fingerprint(settings.BREVO_API_KEY),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        logger.info("Deployment test email sent to %s", recipient)
        return Response({"ok": True, "detail": f"Test email sent to {recipient}."})
