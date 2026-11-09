"""Populate the dashboard with realistic demo data for charts and the live feed.

Development helper only. It creates encrypted *placeholder* templates, never
fingerprint images.
"""

import io
import random
from datetime import datetime, time, timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from devices.models import Device
from logs.models import EntryLog
from members.crypto import encrypt_template
from members.models import FingerprintTemplate, Member

DEMO_DEVICES = [
    ("FP-FRONT-01", "Front Door"),
    ("FP-SIDE-02", "Side Gate"),
]

DEMO_MEMBERS = [
    ("amina.k", "Amina Keza", "+250 788 123 401", "amina.keza@example.com", "MEMBER", "#16a34a"),
    ("david.m", "David Mugisha", "+250 788 123 402", "david.mugisha@example.com", "MEMBER", "#0ea5e9"),
    ("sarah.n", "Sarah Nyirahabimana", "+250 788 123 403", "sarah.n@example.com", "MEMBER", "#8b5cf6"),
    ("kevin.visitor", "Kevin Habimana", "+250 788 123 404", "kevin.h@example.com", "VISITOR", "#2563eb"),
    ("grace.visitor", "Grace Uwase", "+250 788 123 405", "grace.u@example.com", "VISITOR", "#2563eb"),
]


def _hex_to_rgb(value: str):
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def _avatar(initials: str, base_color: str) -> bytes:
    """Render a simple gradient avatar so demo members have real photos."""
    width = height = 512
    top = _hex_to_rgb(base_color)
    bottom = tuple(max(0, int(channel * 0.55)) for channel in top)
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / (height - 1)
        color = tuple(
            int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3)
        )
        draw.line((0, y, width, y), fill=color)
    draw.ellipse((150, 150, 362, 362), outline=(255, 255, 255), width=10)
    try:
        font = ImageFont.truetype("arialbd.ttf", 150)
    except OSError:
        try:
            font = ImageFont.truetype("arial.ttf", 150)
        except OSError:
            font = ImageFont.load_default()
    draw.text((width / 2, height / 2 - 6), initials, fill=(255, 255, 255), anchor="mm", font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class Command(BaseCommand):
    help = "Seed demo devices, members, encrypted templates and 7 days of entry logs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete existing members/logs and reseed.",
        )

    def handle(self, *args, **options):
        random.seed(42)
        now = timezone.now()

        if Member.objects.exists() and not options["force"]:
            self.stdout.write(
                self.style.WARNING(
                    "Members already exist. Re-run with --force to wipe and reseed."
                )
            )
            return

        if options["force"]:
            EntryLog.objects.all().delete()
            FingerprintTemplate.objects.all().delete()
            Member.objects.all().delete()
            Device.objects.filter(device_id__in=[d[0] for d in DEMO_DEVICES]).delete()
            self.stdout.write("Cleared existing demo data.")

        devices = []
        for device_id, location in DEMO_DEVICES:
            device, _ = Device.objects.update_or_create(
                device_id=device_id,
                defaults={
                    "location_name": location,
                    "is_online": True,
                    "last_seen_at": now,
                },
            )
            devices.append(device)

        members = []
        for username, full_name, phone, email, role, color in DEMO_MEMBERS:
            member = Member.objects.create(
                username=username,
                full_name=full_name,
                phone_number=phone,
                email=email,
                role=role,
                is_active=True,
            )
            initials = "".join(part[0].upper() for part in full_name.split()[:2])
            member.photo.save(
                f"{username}.png", ContentFile(_avatar(initials, color)), save=True
            )
            FingerprintTemplate.objects.create(
                member=member,
                template_data=encrypt_template(
                    f"DEMO-TEMPLATE:{username}:{random.random()}".encode()
                ),
                sync_status=random.choice(
                    [
                        FingerprintTemplate.SyncStatus.SYNCED,
                        FingerprintTemplate.SyncStatus.SYNCED,
                        FingerprintTemplate.SyncStatus.PENDING,
                    ]
                ),
                last_synced_at=now if random.random() > 0.3 else None,
            )
            members.append(member)

        regular = [m for m in members if m.role == Member.Role.MEMBER]
        visitors = [m for m in members if m.role == Member.Role.VISITOR]

        logs = []
        for day_offset in range(6, -1, -1):
            day = (now - timedelta(days=day_offset)).date()
            count = random.randint(5, 12)
            for _ in range(count):
                # Never generate entries in the future: today's window stops
                # one minute before "now"; past days run until 21:59.
                if day == now.date():
                    end_minutes = max(
                        6 * 60 + 1, now.hour * 60 + now.minute - 1
                    )
                    end_minutes = min(end_minutes, 21 * 60 + 59)
                else:
                    end_minutes = 21 * 60 + 59
                total_minutes = random.randint(6 * 60, end_minutes)
                hour, minute = divmod(total_minutes, 60)
                timestamp = timezone.make_aware(
                    datetime.combine(day, time(hour=hour, minute=minute)),
                    timezone.get_current_timezone(),
                )
                roll = random.random()
                if roll < 0.58:
                    status = EntryLog.Status.MEMBER
                    member = random.choice(regular)
                elif roll < 0.80:
                    status = EntryLog.Status.VISITOR
                    member = random.choice(visitors)
                else:
                    status = EntryLog.Status.UNKNOWN
                    member = None
                logs.append(
                    EntryLog(
                        member=member,
                        device=random.choice(devices),
                        status=status,
                        timestamp=timestamp,
                        synced_from_device=random.random() < 0.12,
                    )
                )

        EntryLog.objects.bulk_create(logs)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(devices)} devices, {len(members)} members, "
                f"{len(logs)} entry logs over the last 7 days."
            )
        )
        self.stdout.write(
            "Open the dashboard to see charts, or run the frontend dev server."
        )
