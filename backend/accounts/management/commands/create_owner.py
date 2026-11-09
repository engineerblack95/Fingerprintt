import os

from django.core.management.base import BaseCommand

from accounts.models import User


class Command(BaseCommand):
    help = (
        "Create or update the owner/admin account from OWNER_USERNAME, "
        "OWNER_EMAIL and OWNER_PASSWORD in the environment."
    )

    def handle(self, *args, **options):
        username = os.getenv("OWNER_USERNAME", "Engineer")
        email = os.getenv("OWNER_EMAIL", "")
        password = os.getenv("OWNER_PASSWORD", "")

        if not email or not password:
            self.stderr.write(
                self.style.ERROR("OWNER_EMAIL and OWNER_PASSWORD must be set in .env")
            )
            return

        user, created = User.objects.get_or_create(
            username=username, defaults={"email": email}
        )
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(f"{action} owner account '{username}' <{email}>.")
        )
