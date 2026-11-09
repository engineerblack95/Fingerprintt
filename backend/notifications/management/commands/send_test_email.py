from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives


class Command(BaseCommand):
    help = "Send a test HTML email to OWNER_EMAIL using the configured backend."

    def handle(self, *args, **options):
        if not settings.OWNER_EMAIL:
            self.stderr.write(self.style.ERROR("OWNER_EMAIL is not configured."))
            return

        subject = "✅ Test: Fingerprint Access Control email"
        text = "This is a test email from the Fingerprint Access Control backend."
        html = (
            "<div style=\"font-family:Arial,sans-serif;padding:24px\">"
            "<h2 style=\"color:#16a34a;margin:0 0 8px\">✅ Email is working</h2>"
            "<p style=\"color:#334155\">The Django email backend is configured correctly.</p>"
            f"<p style=\"color:#64748b;font-size:13px\">Backend: {settings.EMAIL_BACKEND}</p>"
            "</div>"
        )
        message = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[settings.OWNER_EMAIL],
        )
        message.attach_alternative(html, "text/html")
        message.send(fail_silently=False)
        self.stdout.write(
            self.style.SUCCESS(f"Test email sent to {settings.OWNER_EMAIL}.")
        )
