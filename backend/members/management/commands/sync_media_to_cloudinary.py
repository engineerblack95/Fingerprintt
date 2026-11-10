"""Upload locally stored member photos to Cloudinary (one-time migration)."""

from pathlib import Path

from django.conf import settings as django_settings
from django.core.files.storage import FileSystemStorage
from django.core.management.base import BaseCommand, CommandError

from members.models import Member


class Command(BaseCommand):
    help = (
        "Copy every existing local member photo from MEDIA_ROOT to Cloudinary "
        "and point the Member rows at the new Cloudinary names. Only run while "
        "CLOUDINARY_URL is configured."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List what would be uploaded without uploading anything.",
        )

    def handle(self, *args, **options):
        backend = django_settings.STORAGES["default"]["BACKEND"]
        if not backend.endswith("CloudinaryMediaStorage"):
            raise CommandError(
                "The default storage is not Cloudinary - set CLOUDINARY_URL in "
                ".env / Render environment before running this command."
            )

        from config.storages import CloudinaryMediaStorage

        media_root = Path(django_settings.MEDIA_ROOT)
        local = FileSystemStorage(location=str(media_root))
        remote = CloudinaryMediaStorage()

        photos = Member.objects.exclude(photo="").exclude(photo__isnull=True)
        uploaded = kept = missing = 0

        for member in photos.iterator():
            name = member.photo.name
            if local.exists(name):
                if remote.exists(name):
                    kept += 1
                    continue
                if options["dry_run"]:
                    self.stdout.write(f"would upload: {name}")
                    continue
                with local.open(name, "rb") as handle:
                    new_name = remote.save(name, handle)
                if new_name != name:
                    member.photo.name = new_name
                    member.save(update_fields=["photo"])
                uploaded += 1
                self.stdout.write(f"uploaded: {name} -> {new_name}")
            elif remote.exists(name):
                kept += 1
                self.stdout.write(f"already in Cloudinary: {name}")
            else:
                missing += 1
                self.stderr.write(
                    self.style.WARNING(
                        f"local file not found for member pk={member.pk}: {name}"
                    )
                )

        summary = (
            f"uploaded={uploaded} already_present={kept} local_files_missing={missing}"
        )
        if options["dry_run"]:
            self.stdout.write(self.style.NOTICE(f"DRY RUN - {summary}"))
        else:
            self.stdout.write(self.style.SUCCESS(summary))
