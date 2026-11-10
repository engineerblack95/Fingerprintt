import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from logs.models import EntryLog
from members.utils import absolute_photo_url

logger = logging.getLogger(__name__)


def _initials(name: str) -> str:
    parts = [part for part in (name or "").split() if part]
    return "".join(part[0].upper() for part in parts[:2]) or "?"


def send_entry_notification(log: EntryLog) -> None:
    """Send the HTML alert for one entry event to the owner."""
    if log.status == EntryLog.Status.ENROLLED:
        logger.info("Skipping email for hardware enrollment log %s", log.pk)
        return

    owner_email = (settings.OWNER_EMAIL or "").strip()
    if not owner_email:
        logger.warning("OWNER_EMAIL is not configured; skipping notification.")
        return

    local_time = timezone.localtime(log.timestamp)
    timestamp = local_time.strftime("%A, %d %B %Y at %H:%M %Z")
    location = log.device.location_name

    if log.status == EntryLog.Status.UNKNOWN or log.member is None:
        subject = f"🚨 SECURITY ALERT: Unknown person at {location}"
        template = "notifications/email_unknown.html"
        context = {
            "location": location,
            "timestamp": timestamp,
            "dashboard_url": f"{settings.FRONTEND_URL}/dashboard",
        }
        text_body = (
            "UNKNOWN PERSON DETECTED\n"
            f"Location: {location}\n"
            f"Time: {timestamp}\n"
            "Status: UNKNOWN / INTRUDER\n"
            "No registered profile found - no image, name, or contact available.\n"
            f"Open the dashboard: {settings.FRONTEND_URL}/dashboard"
        )
    else:
        member = log.member
        role_display = member.get_role_display()
        context = {
            "member": member,
            "role_display": role_display,
            "location": location,
            "timestamp": timestamp,
            "initials": _initials(member.full_name),
            # Cloudinary (or local) URL of the profile photo. Remote https URLs
            # render directly in the inbox, so no CID attachment is required.
            "photo_url": absolute_photo_url(member),
        }
        if log.status == EntryLog.Status.VISITOR:
            subject = f"🔵 Visitor Arrived: {member.full_name} at {location}"
            template = "notifications/email_visitor.html"
            text_body = (
                f"Visitor arrived: {member.full_name}\n"
                f"Role: {role_display}\n"
                f"Phone: {member.phone_number}\n"
                f"Email: {member.email}\n"
                f"Location: {location}\n"
                f"Time: {timestamp}"
            )
        else:
            subject = f"✅ Entry Granted: {member.full_name} at {location}"
            template = "notifications/email_member.html"
            text_body = (
                f"Entry granted: {member.full_name}\n"
                f"Role: {role_display}\n"
                f"Phone: {member.phone_number}\n"
                f"Email: {member.email}\n"
                f"Location: {location}\n"
                f"Time: {timestamp}"
            )

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[owner_email],
    )
    message.attach_alternative(render_to_string(template, context), "text/html")

    message.send(fail_silently=False)
    logger.info("Sent %s notification for log %s to %s", log.status, log.pk, owner_email)
