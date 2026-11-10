"""Audit Member photo rows against the configured storage backend."""

from django.conf import settings as django_settings
from django.core.management.base import BaseCommand, CommandError

from members.models import Member


class Command(BaseCommand):
    help = (
        "List members whose photo property references a file that no longer "
        "exists in storage (e.g. photos lost on Render before Cloudinary was "
        "enabled). Optionally remove those dead references so the UI shows "
        "the initials placeholder instead of broken images."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear-photo",
            action="store_true",
            help="Remove the dead photo references (irreversible).",
        )

    def handle(self, *args, **options):
        backend = django_settings.STORAGES["default"]["BACKEND"]
        if backend.endswith("CloudinaryMediaStorage"):
            from config.storages import CloudinaryMediaStorage
        elif backend.endswith("FileSystemStorage"):
            from django.core.files.storage import FileSystemStorage

            CloudinaryMediaStorage = FileSystemStorage
        else:
            raise CommandError(f"Unsupported storage backend: {backend}")

        storage = CloudinaryMediaStorage()
        broken = []

        for member in Member.objects.exclude(photo="").exclude(photo__isnull=True).iterator():
            try:
                if storage.exists(member.photo.name):
                    continue
            except NotImplementedError:
                continue
            broken.append(member)

        if not broken:
            self.stdout.write(self.style.SUCCESS("No broken photo references."))
            return

        for member in broken:
            self.stdout.write(
                f"[-] pk={member.pk} @{member.username} -> {member.photo.name}"
            )

        if options["clear_photo"]:
            for member in broken:
                member.photo = ""
                member.save(update_fields=["photo"])
            self.stdout.write(
                self.style.SUCCESS(f"Cleared photo references on {len(broken)} member(s).")
            )
        else:
            self.stdout.write(
                self.style.NOTICE(
                    f"{len(broken)} member(s) reference missing photos. Re-upload "
                    "their photos in the dashboard, or run again with --clear-photo "
                    "to remove the dead references."
                )
            )
