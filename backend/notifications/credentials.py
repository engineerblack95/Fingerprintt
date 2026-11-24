"""Resolve the Brevo API key from the database override or the environment.

The environment variable is the primary, deployment-level source. A value
stored through the administrator endpoint takes precedence so a bad environment
entry can be corrected without shell or host access. Ciphertext is encrypted
with the same Fernet key used for fingerprint templates.
"""

import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)

MIN_KEY_LENGTH = 40


def _fernet() -> Fernet:
    return Fernet(settings.TEMPLATE_ENCRYPTION_KEY.encode("utf-8"))


def clean_api_key(raw: str) -> str:
    """Strip the damage that copy/paste introduces (quotes, BOM, whitespace)."""
    value = str(raw or "")
    value = value.replace("\ufeff", "").replace("\u200b", "")
    value = "".join(value.split())
    return value.strip('"').strip("'")


def validate_api_key(raw: str) -> str:
    """Return the cleaned key or raise ``ValueError`` with a readable reason."""
    key = clean_api_key(raw)
    if not key:
        raise ValueError("The API key is empty.")
    if not key.startswith("xkeysib-"):
        raise ValueError(
            "This is not a Brevo API key. API keys start with 'xkeysib-' "
            "(an SMTP key will not work here)."
        )
    if len(key) < MIN_KEY_LENGTH:
        raise ValueError(
            f"This key is only {len(key)} characters long. Brevo API keys are "
            "longer; the value was probably truncated when it was copied."
        )
    return key


def get_stored_api_key() -> str:
    """Return the administrator-installed key, or '' when none is stored."""
    from .models import EmailCredential

    try:
        credential = EmailCredential.objects.filter(pk=1).first()
    except Exception:  # noqa: BLE001 - migrations not applied yet / DB down
        logger.warning("Could not read the stored email credential.", exc_info=True)
        return ""
    if not credential or not credential.api_key_ciphertext:
        return ""
    try:
        return _fernet().decrypt(bytes(credential.api_key_ciphertext)).decode("utf-8")
    except InvalidToken:
        logger.error(
            "The stored email credential cannot be decrypted: "
            "TEMPLATE_ENCRYPTION_KEY changed since it was saved."
        )
        return ""


def get_brevo_api_key() -> str:
    """Effective key: the stored override wins over the environment."""
    return get_stored_api_key() or settings.BREVO_API_KEY


def set_brevo_api_key(raw: str) -> str:
    """Validate, encrypt and store a key. Returns the stored key."""
    from .models import EmailCredential

    key = validate_api_key(raw)
    credential, _ = EmailCredential.objects.get_or_create(pk=1)
    credential.api_key_ciphertext = _fernet().encrypt(key.encode("utf-8"))
    credential.save()
    logger.info("Stored a new email credential from the administrator endpoint.")
    return key


def clear_brevo_api_key() -> None:
    """Remove the stored override and fall back to the environment variable."""
    from .models import EmailCredential

    EmailCredential.objects.filter(pk=1).delete()
    logger.info("Cleared the stored email credential.")
