import logging

from django.apps import AppConfig
from django.conf import settings

from .diagnostics import key_fingerprint, mask_key

logger = logging.getLogger(__name__)


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"
    verbose_name = "Email notifications"

    def ready(self):
        """Log a safe email-configuration summary at startup.

        On Render the only clue to a broken key used to be a 401 deep inside a
        request traceback. This line makes the active transport, key
        fingerprint and public URLs visible in the deploy log immediately.
        """
        backend = (settings.EMAIL_BACKEND or "").lower()
        if "brevo_api" not in backend:
            return

        key = settings.BREVO_API_KEY
        logger.info(
            "Email transport: backend=%s env_key=%s fingerprint=%s from=%r "
            "owner=%r frontend=%s (an administrator-installed credential, if "
            "present, overrides the environment key)",
            settings.EMAIL_BACKEND,
            mask_key(key),
            key_fingerprint(key),
            settings.DEFAULT_FROM_EMAIL,
            settings.OWNER_EMAIL,
            settings.FRONTEND_URL,
        )

        if not key:
            logger.error(
                "BREVO_API_KEY is empty; no email can be delivered unless an "
                "administrator installs a key via POST /api/notifications/key/."
            )
        elif not key.startswith("xkeysib-"):
            logger.error(
                "BREVO_API_KEY does not start with 'xkeysib-'. It may be an "
                "SMTP key or a placeholder, but the API requires an API key "
                "from https://app.brevo.com/settings/keys/api"
            )
        elif len(key) < 40:
            logger.error(
                "BREVO_API_KEY is only %s characters long, which is too short "
                "for a Brevo API key - the value was probably truncated. Fix it "
                "or install the key via POST /api/notifications/key/.",
                len(key),
            )
