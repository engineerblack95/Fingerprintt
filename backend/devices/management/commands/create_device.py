from django.core.management.base import BaseCommand, CommandError

from devices.models import Device


class Command(BaseCommand):
    help = "Register a fingerprint device (or update its location)."

    def add_arguments(self, parser):
        parser.add_argument("--device-id", required=True, help="Hardware identifier")
        parser.add_argument("--location", required=True, help='e.g. "Front Door"')

    def handle(self, *args, **options):
        device_id = options["device_id"].strip()
        location = options["location"].strip()
        if not device_id or not location:
            raise CommandError("Both --device-id and --location are required.")

        device, created = Device.objects.update_or_create(
            device_id=device_id, defaults={"location_name": location}
        )
        action = "Registered" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(f"{action} device '{device.device_id}' at '{device.location_name}'.")
        )
