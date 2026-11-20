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


def send_entry_notification(log: EntryLog) -> bool:
    """Send the HTML alert for one entry event to the owner.

    Returns True when the message was handed to the email backend, False when
    the event was intentionally skipped (enrollment, missing configuration,
    deleted-member row). Delivery errors propagate to the caller so they are
    logged with a full traceback.
    """
    if log.status == EntryLog.Status.ENROLLED:
        logger.info("Skipping email for hardware enrollment log %s", log.pk)
        return False

    owner_email = (settings.OWNER_EMAIL or "").strip()
    if not owner_email:
        logger.error(
            "OWNER_EMAIL is not configured; entry alerts cannot be sent. "
            "Set OWNER_EMAIL in the environment."
        )
        return False

    local_time = timezone.localtime(log.timestamp)
    timestamp = local_time.strftime("%A, %d %B %Y at %H:%M %Z")
    location = log.device.location_name

    if log.status == EntryLog.Status.UNKNOWN or log.member is None:
        if log.member is None and log.member_name:
            # The member was deleted after the event; there is no profile to
            # render, so an intruder alert would be misleading.
            logger.info(
                "Skipping email for log %s: member profile was deleted.", log.pk
            )
            return False
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
    return True


def send_password_reset_email(user, reset_url: str) -> bool:
    """Email a single-use password reset link to ``user``.

    Returns True when the message was handed to the email backend. Errors
    propagate so the caller can log them; the API never reveals them.
    """
    recipient = (user.email or "").strip()
    if not recipient:
        logger.error(
            "User %s has no email address; password reset cannot be sent.",
            user.pk,
        )
        return False

    full_name = user.get_full_name() or user.username
    timeout_seconds = int(getattr(settings, "PASSWORD_RESET_TIMEOUT", 3600))
    expires_minutes = max(1, timeout_seconds // 60)
    requested_at = timezone.localtime().strftime("%A, %d %B %Y at %H:%M %Z")

    context = {
        "user": user,
        "full_name": full_name,
        "reset_url": reset_url,
        "expires_minutes": expires_minutes,
        "requested_at": requested_at,
        "frontend_url": settings.FRONTEND_URL,
    }

    subject = "🔐 Reset your Fingerprint Access password"
    text_body = (
        f"Hello {full_name},\n\n"
        "We received a request to reset the password for your Fingerprint "
        "Access Control account.\n\n"
        f"Reset your password here (valid for {expires_minutes} minutes):\n"
        f"{reset_url}\n\n"
        "If you did not request this, you can safely ignore this email - your "
        "password will not change.\n\n"
        f"Requested: {requested_at}\n"
    )

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    message.attach_alternative(
        render_to_string("notifications/password_reset.html", context),
        "text/html",
    )
    message.send(fail_silently=False)
    logger.info("Sent password reset email to %s", recipient)
    return True
