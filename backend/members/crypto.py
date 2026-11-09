"""Symmetric encryption for fingerprint templates.

Only ciphertext (Fernet token bytes) is ever written to PostgreSQL. The key is
provided through TEMPLATE_ENCRYPTION_KEY and must be backed up: losing it makes
all stored templates unrecoverable by design.
"""

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    return Fernet(settings.TEMPLATE_ENCRYPTION_KEY.encode("utf-8"))


def encrypt_template(raw: bytes) -> bytes:
    if not raw:
        raise ValueError("Fingerprint template payload is empty.")
    return _fernet().encrypt(raw)


def decrypt_template(ciphertext: bytes) -> bytes:
    """Decrypt a stored template.

    Raises ``cryptography.fernet.InvalidToken`` when the ciphertext was produced
    with a different key or has been tampered with.
    """
    return _fernet().decrypt(bytes(ciphertext))


__all__ = ["encrypt_template", "decrypt_template", "InvalidToken"]
