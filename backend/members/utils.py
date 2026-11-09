from django.conf import settings


def absolute_photo_url(member) -> str | None:
    """Return a fully qualified photo URL usable in emails and WebSocket payloads."""
    if not member or not getattr(member, "photo", None):
        return None
    try:
        url = member.photo.url
    except ValueError:
        return None
    if url.startswith(("http://", "https://")):
        return url
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    return f"{base}{url}"
