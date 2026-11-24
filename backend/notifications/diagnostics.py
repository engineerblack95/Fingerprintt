"""Small, dependency-free helpers for diagnosing email configuration.

The full API key must never be logged. A short fingerprint lets an operator
compare the key used by a deployment with the one that works locally without
exposing the secret itself.
"""

import hashlib


def key_fingerprint(key: str) -> str:
    """Stable, non-reversible identifier for a secret key."""
    if not key:
        return "missing"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def mask_key(key: str) -> str:
    """Show a safe, recognisable fragment of a key: ``xkeysib-…n1PJ (89)``."""
    if not key:
        return "missing"
    if len(key) <= 12:
        return f"{key[:2]}... (len {len(key)})"
    return f"{key[:7]}...{key[-4:]} (len {len(key)})"
