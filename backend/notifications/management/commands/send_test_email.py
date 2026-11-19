"""Verify the email configuration and send a test alert."""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Print the active email configuration and send a test message to "
        "OWNER_EMAIL. Use it locally and on the Render shell after changing "
        "environment variables."
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

    def handle(self, *args, **options):
        recipient = (options["to"] or settings.OWNER_EMAIL or "").strip()

        self.stdout.write("Email configuration")
        self.stdout.write(f"  EMAIL_BACKEND      = {settings.EMAIL_BACKEND}")
        self.stdout.write(
            f"  BREVO_API_KEY      = {'set (%d chars)' % len(settings.BREVO_API_KEY) if settings.BREVO_API_KEY else 'MISSING'}"
        )
        self.stdout.write(f"  DEFAULT_FROM_EMAIL = {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"  OWNER_EMAIL        = {settings.OWNER_EMAIL or 'MISSING'}")
        self.stdout.write(f"  Recipient          = {recipient or 'MISSING'}")

        problems = []
        if not settings.BREVO_API_KEY:
            problems.append("BREVO_API_KEY is not set.")
        if "brevo" not in settings.EMAIL_BACKEND.lower():
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
