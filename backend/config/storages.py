"""
Cloudinary-backed storage for Django media files.

Activated when the ``CLOUDINARY_URL`` environment variable is set (see
``config/settings.py``). Without it Django falls back to the local filesystem,
which is fine for development but useless on Render where the disk is
ephemeral - every redeploy would wipe the member photos.

Notes
-----
* This account is provisioned with dynamic folders, so delivery URLs MUST
  include the resource version. Versions are captured on upload and cached
  per-process; ``url()`` for an unknown public id falls back to the Admin API
  once and caches the result.
* Only the storage surface Django needs is implemented: saving, URL building,
  existence checks, size, opening for read (used by email photo rendering)
  and deletion.
"""

import os
from urllib.request import urlopen

import cloudinary.api
import cloudinary.uploader
import cloudinary.utils
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


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
        super().__init__(*args, **kwargs)

    # ------------------------------------------------------------------ write
    def _save(self, name, content):
        stem, _ = _split_name(name)
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
        self._versions[result["public_id"]] = int(result["version"])
        # Keep the actual uploaded format (e.g. .jfif stored as .jpg) in the
        # name so ``url()`` can rebuild the correct CDN link from the stored
        # value alone.
        return f"{result['public_id']}.{result['format']}"

    # ------------------------------------------------------------------ read
    def exists(self, name) -> bool:
        try:
            self._read_resource_version(name)
            return True
        except cloudinary.api.NotFound:
            return False

    def url(self, name):
        stem, ext = _split_name(name)
        version = self._read_resource_version(name)
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
        return ContentFile(urlopen(self.url(name), timeout=30).read(), name=name)

    def size(self, name) -> int:
        stem, _ = _split_name(name)
        resource = cloudinary.api.resource(
            stem, type="upload", resource_type=self.resource_type
        )
        return int(resource.get("bytes", 0))

    # ---------------------------------------------------------------- delete
    def delete(self, name) -> bool:
        stem, _ = _split_name(name)
        self._versions.pop(stem, None)
        result = cloudinary.uploader.destroy(
            stem, resource_type=self.resource_type, type="upload", invalidate=True
        )
        return result.get("result") == "ok"

    # ---------------------------------------------------------- version lookup
    def _read_resource_version(self, name) -> int:
        stem, _ = _split_name(name)
        version = self._versions.get(stem)
        if version is not None:
            return version
        try:
            resource = cloudinary.api.resource(
                stem, type="upload", resource_type=self.resource_type
            )
        except cloudinary.api.NotFound:
            self._versions.pop(stem, None)
            raise
        version = int(resource["version"])
        self._versions[stem] = version
        return version

    # ------------------------------------------------------------ unsupported
    def listdir(self, path):  # pragma: no cover - not needed by this project
        raise NotImplementedError("Cloudinary storage does not support listdir().")

    def path(self, name):  # pragma: no cover - no filesystem path exists
        raise NotImplementedError("Cloudinary storage has no filesystem paths.")
