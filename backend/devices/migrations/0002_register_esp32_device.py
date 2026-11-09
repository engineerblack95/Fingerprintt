from django.db import migrations


def register_esp32_device(apps, schema_editor):
    """Ensure the BioGate ESP32 terminal exists so firmware events are accepted."""
    Device = apps.get_model("devices", "Device")
    Device.objects.get_or_create(
        device_id="ESP32-01",
        defaults={"location_name": "Main Entrance"},
    )


def unregister_esp32_device(apps, schema_editor):
    # Keep the device on rollback; it may already be in use in production.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("devices", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(register_esp32_device, unregister_esp32_device),
    ]
