"""
Cloudinary-backed storage for Django media files.

Activated when the ``CLOUDINARY_URL`` environment variable is set (see
``config/settings.py``). Without it Django falls back to the local filesystem,
which is fine for development but useless on Render where the disk is
ephemeral - every redeploy would wipe the member photos.

Reliability contract
--------------------
A member row may legally reference a photo that no longer exists in the cloud
(for example rows created before Cloudinary was enabled on the production
database). Nothing that calls ``.url()`` may therefore ever blow up a request:
``url()`` degrades gracefully to an empty string (the API/frontend then uses
the initials fallback) and the missing resource is negatively cached for
``MISSING_TTL_SECONDS`` so list endpoints never hammer the Admin API.

Offline behaviour
-----------------
When there is no internet (or Cloudinary is unreachable) the project must keep
running locally. Network/server failures are treated the same way as missing
resources - they never raise out of ``url()``/``exists()`` - and new uploads
are mirrored to ``MEDIA_ROOT`` so member creation keeps working offline.
Locally stored files are served through ``MEDIA_URL``; everything is
transparently pushed to Cloudinary the next time it is uploaded online.

Delivery URLs MUST include the resource version (this account is provisioned
with dynamic folders); versions are captured on upload and cached
per-process, falling back to a single Admin API lookup.

Only the storage surface Django needs is implemented: saving, URL building,
existence checks, size, opening for read and deletion.
"""

import logging
import os
import time
from urllib.request import urlopen

import cloudinary.api
import cloudinary.uploader
import cloudinary.utils
from cloudinary.exceptions import GeneralError
from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible

logger = logging.getLogger(__name__)

MISSING_TTL_SECONDS = 300
# Transient failures (offline, Cloudinary 5xx) are retried sooner than
# confirmed-deleted resources.
UNAVAILABLE_TTL_SECONDS = 60

# cloudinary's SDK wraps socket/DNS failures in GeneralError ("Socket Error"),
# and OS-level connection issues surface as OSError subclasses (URLError,
# gaierror, TimeoutError...).
NETWORK_ERRORS = (GeneralError, OSError)


def _ensure_safe(name: str) -> str:
    """Reject path traversal and normalise separators/leading slashes."""
    normalized = name.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise SuspiciousFileOperation("Path traversal is not allowed in media names.")
    return "/".join(parts)


def _split_name(name: str) -> tuple[str, str | None]:
    """Split a stored name into a Cloudinary public id and an extension."""
    stem, ext = os.path.splitext(_ensure_safe(name))
    ext = ext[1:] or None
    return stem, ext


@deconstructible
class CloudinaryMediaStorage(Storage):
    """Stores member photos (images) in a Cloudinary cloud."""

    resource_type = "image"

    def __init__(self, *args, **kwargs):
        # public id -> delivery version (see module docstring)
        self._versions: dict[str, int] = {}
        # public id -> monotonic time the absence was confirmed
        self._missing: dict[str, float] = {}
        # public id -> monotonic time a transient network/server error hit
        self._unavailable: dict[str, float] = {}
        # public ids stored on the local disk because the cloud was unreachable
        self._local_only: set[str] = set()
        super().__init__(*args, **kwargs)

    # ------------------------------------------------------------------ write
    def _save(self, name, content):
        stem, _ = _split_name(name)
        try:
            result = cloudinary.uploader.upload(
                content,
                public_id=stem,
                resource_type=self.resource_type,
                type="upload",
                overwrite=True,
                invalidate=True,
                use_filename=False,
                unique_filename=False,
            )
        except NETWORK_ERRORS as exc:
            # No internet / Cloudinary unreachable: mirror the file to
            # MEDIA_ROOT so member creation keeps working locally. It can be
            # re-uploaded later with `sync_media_to_cloudinary`.
            logger.warning(
                "Cloudinary unreachable (%s); storing %r on the local disk "
                "instead.", exc, stem,
            )
            self._versions.pop(stem, None)
            self._local_only.add(stem)
            return self._write_local_copy(name, content)
        version = int(result["version"])
        self._versions[result["public_id"]] = version
        self._missing.pop(stem, None)
        self._unavailable.pop(stem, None)
        self._local_only.discard(stem)
        # Keep the actual uploaded format (e.g. .jfif stored as .jpg) in the
        # name so ``url()`` can rebuild the correct CDN link from the stored
        # value alone.
        return f"{result['public_id']}.{result['format']}"

    def _write_local_copy(self, name, content) -> str:
        from django.core.files.storage import FileSystemStorage

        if hasattr(content, "seek"):
            try:
                content.seek(0)
            except (OSError, ValueError):
                pass
        local = FileSystemStorage(location=str(settings.MEDIA_ROOT))
        return local.save(name, content)

    # ------------------------------------------------------------- local disk
    def _local_path(self, name: str):
        safe = _ensure_safe(name)
        return os.path.join(str(settings.MEDIA_ROOT), *safe.split("/"))

    def _has_local_copy(self, name: str) -> bool:
        path = self._local_path(name)
        return bool(path) and os.path.isfile(path)

    # ------------------------------------------------------------------ read
    def _lookup_version(self, name: str) -> int | None:
        """Delivery version of a stored name, or None when it can't be served.

        Returns None both when the resource is confirmed gone and when the
        cloud is unreachable - callers degrade gracefully either way.
        """
        stem, _ = _split_name(name)
        version = self._versions.get(stem)
        if version is not None:
            return version

        now = time.monotonic()
        marked_missing = self._missing.get(stem)
        if (
            marked_missing is not None
            and now - marked_missing < MISSING_TTL_SECONDS
        ):
            return None
        marked_unavailable = self._unavailable.get(stem)
        if (
            marked_unavailable is not None
            and now - marked_unavailable < UNAVAILABLE_TTL_SECONDS
        ):
            return None

        try:
            resource = cloudinary.api.resource(
                stem, type="upload", resource_type=self.resource_type
            )
        except cloudinary.api.NotFound:
            self._missing[stem] = time.monotonic()
            logger.warning(
                "Cloudinary resource %r is gone; the API will fall back to the "
                "initials placeholder for it.", stem,
            )
            return None
        except NETWORK_ERRORS as exc:
            self._unavailable[stem] = time.monotonic()
            logger.warning(
                "Cloudinary is unreachable (%s); serving %r without a photo "
                "for now.", exc, stem,
            )
            return None
        version = int(resource["version"])
        self._missing.pop(stem, None)
        self._unavailable.pop(stem, None)
        self._versions[stem] = version
        return version

    def exists(self, name) -> bool:
        return self._has_local_copy(name) or self._lookup_version(name) is not None

    def url(self, name):
        # Files mirrored locally (offline uploads / restarts) are served from
        # the local development server so no network round trip is needed.
        if self._has_local_copy(name):
            return f"{settings.MEDIA_URL.rstrip('/')}/{_ensure_safe(name)}"
        version = self._lookup_version(name)
        if version is None:
            # A row referencing a photo that is not (yet) in the cloud must
            # never 500 a request; an empty URL makes serializers report "no
            # photo" and the UI/email templates use the initials fallback.
            return ""
        stem, ext = _split_name(name)
        url, _ = cloudinary.utils.cloudinary_url(
            stem,
            format=ext,
            type="upload",
            resource_type=self.resource_type,
            secure=True,
            version=version,
        )
        return url

    def _open(self, name, mode="rb"):
        if mode != "rb":
            raise ValueError("Cloudinary storage only supports binary reads.")
        local_path = self._local_path(name)
        if local_path and os.path.isfile(local_path):
            return open(local_path, "rb")
        version = self._lookup_version(name)
        if version is None:
            raise FileNotFoundError(f"Cloudinary resource not found: {name}")
        return ContentFile(
            urlopen(self._delivery_url(name, version), timeout=30).read(), name=name
        )

    def _delivery_url(self, name: str, version: int) -> str:
        stem, ext = _split_name(name)
        url, _ = cloudinary.utils.cloudinary_url(
            stem,
            format=ext,
            type="upload",
            resource_type=self.resource_type,
            secure=True,
            version=version,
        )
        return url

    def size(self, name) -> int:
        local_path = self._local_path(name)
        if local_path and os.path.isfile(local_path):
            return os.path.getsize(local_path)
        stem, _ = _split_name(name)
        try:
            resource = cloudinary.api.resource(
                stem, type="upload", resource_type=self.resource_type
            )
        except cloudinary.api.NotFound:
            raise FileNotFoundError(f"Cloudinary resource not found: {name}") from None
        except NETWORK_ERRORS as exc:
            logger.warning("Cloudinary is unreachable (%s); size unavailable.", exc)
            raise FileNotFoundError(
                f"Cloudinary resource temporarily unavailable: {name}"
            ) from None
        return int(resource.get("bytes", 0))

    # ---------------------------------------------------------------- delete
    def delete(self, name) -> bool:
        stem, _ = _split_name(name)
        self._versions.pop(stem, None)
        self._missing.pop(stem, None)
        self._unavailable.pop(stem, None)
        self._local_only.discard(stem)
        removed_local = False
        local_path = self._local_path(name)
        if local_path and os.path.isfile(local_path):
            os.remove(local_path)
            removed_local = True
        try:
            result = cloudinary.uploader.destroy(
                stem, resource_type=self.resource_type, type="upload", invalidate=True
            )
        except NETWORK_ERRORS as exc:
            logger.warning(
                "Cloudinary unreachable (%s); removed %r locally only.", exc, stem
            )
            return removed_local
        return result.get("result") == "ok"

    # ------------------------------------------------------------ unsupported
    def listdir(self, path):  # pragma: no cover - not needed by this project
        raise NotImplementedError("Cloudinary storage does not support listdir().")

    def path(self, name):  # pragma: no cover - no filesystem path exists
        raise NotImplementedError("Cloudinary storage has no filesystem paths.")
