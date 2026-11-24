"""Verify the email configuration and send a test alert."""

import json
import urllib.error
import urllib.request

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.utils import timezone

from notifications.credentials import get_brevo_api_key, get_stored_api_key
from notifications.diagnostics import key_fingerprint, mask_key

BREVO_ACCOUNT_URL = "https://api.brevo.com/v3/account"


class Command(BaseCommand):
    help = (
        "Print the active email configuration and send a test message to "
        "OWNER_EMAIL. Use it locally and on the Render shell after changing "
        "environment variables. Add --check-key to validate the Brevo key "
        "without sending anything."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            default="",
            help="Override the recipient (defaults to OWNER_EMAIL).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only print the configuration; do not send anything.",
        )
        parser.add_argument(
            "--check-key",
            action="store_true",
            help="Ask Brevo whether the configured API key is valid.",
        )

    def handle(self, *args, **options):
        recipient = (options["to"] or settings.OWNER_EMAIL or "").strip()
        key = get_brevo_api_key()
        source = "database" if get_stored_api_key() else "environment"
        is_brevo = "brevo" in (settings.EMAIL_BACKEND or "").lower()

        self.stdout.write("Email configuration")
        self.stdout.write(f"  EMAIL_BACKEND      = {settings.EMAIL_BACKEND}")
        self.stdout.write(f"  BREVO_API_KEY      = {mask_key(key)} ({source})")
        self.stdout.write(f"  key fingerprint    = {key_fingerprint(key)}")
        self.stdout.write(f"  DEFAULT_FROM_EMAIL = {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"  OWNER_EMAIL        = {settings.OWNER_EMAIL or 'MISSING'}")
        self.stdout.write(f"  FRONTEND_URL       = {settings.FRONTEND_URL}")
        self.stdout.write(f"  Recipient          = {recipient or 'MISSING'}")

        problems = []
        if not key:
            problems.append("BREVO_API_KEY is not set.")
        elif not key.startswith("xkeysib-"):
            problems.append(
                "BREVO_API_KEY does not start with 'xkeysib-'. The Brevo API "
                "requires an API key (not an SMTP key) from "
                "https://app.brevo.com/settings/keys/api"
            )
        if not is_brevo:
            problems.append(
                "EMAIL_BACKEND is not the Brevo API backend, so messages will "
                "not be delivered."
            )
        if not recipient:
            problems.append("OWNER_EMAIL is not set and no --to was given.")

        if problems:
            for problem in problems:
                self.stderr.write(self.style.ERROR(f"  ! {problem}"))
        else:
            self.stdout.write(self.style.SUCCESS("  Configuration looks good."))

        if options["check_key"] and is_brevo and key:
            self._check_key(key)
            return

        if options["dry_run"] or not recipient:
            return

        subject = "✅ Fingerprint Access email test"
        text = (
            "This is a test message from your Fingerprint Access Control "
            f"dashboard, sent at {timezone.localtime():%A, %d %B %Y %H:%M %Z}."
        )
        html = (
            '<div style="font-family:Arial,sans-serif;padding:24px">'
            '<h2 style="color:#16a34a;margin:0 0 8px">✅ Email is working</h2>'
            '<p style="color:#334155">The Django email backend is configured '
            "correctly and your access alerts will be delivered.</p>"
            f'<p style="color:#64748b;font-size:13px">Backend: '
            f"{settings.EMAIL_BACKEND}</p>"
            "</div>"
        )
        message = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )
        message.attach_alternative(html, "text/html")
        message.send(fail_silently=False)
        self.stdout.write(
            self.style.SUCCESS(f"Test email handed to the backend for {recipient}.")
        )

    def _check_key(self, key: str) -> None:
        request = urllib.request.Request(
            BREVO_ACCOUNT_URL,
            headers={
                "api-key": key,
                "accept": "application/json",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=getattr(settings, "EMAIL_TIMEOUT", 15)
            ) as response:
                body = json.loads(response.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            self.stderr.write(
                self.style.ERROR(
                    f"Brevo key check failed: HTTP {exc.code} {detail}"
                )
            )
            if exc.code in (401, 403):
                self.stderr.write(
                    self.style.ERROR(
                        "The active key is invalid, revoked or truncated. "
                        "Install the working key with "
                        "POST /api/notifications/key/ or replace BREVO_API_KEY "
                        f"(active fingerprint {key_fingerprint(key)})."
                    )
                )
            else:
                self.stderr.write(
                    self.style.ERROR(
                        "Brevo answered with a server error; this is usually "
                        "temporary. Try `send_test_email` to confirm delivery."
                    )
                )
            return
        except urllib.error.URLError as exc:
            self.stderr.write(
                self.style.ERROR(f"Could not reach Brevo: {exc}")
            )
            return

        email = body.get("email") or body.get("companyName") or "unknown"
        self.stdout.write(
            self.style.SUCCESS(f"Brevo accepted the key for: {email}")
        )
