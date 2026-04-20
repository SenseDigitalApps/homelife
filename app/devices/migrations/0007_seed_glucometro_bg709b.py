from django.db import migrations


BG709B_PROFILE = {
    "name": "Glucómetro SEJOY BG-709b",
    "device_type": "glucometro",
    "manufacturer": "SEJOY",
    "model_name": "BG-709b",
    "protocol": "bluetooth",
    "ble_service_uuid": "FFF0",
    "ble_notify_characteristic_uuid": "FFF1",
    "ble_write_characteristic_uuid": "FFF2",
    "ble_characteristic_uuid": "FFF1",
    "supported_parameters": ["glucose"],
    "is_active": True,
}


def forwards(apps, schema_editor):
    DeviceProfile = apps.get_model("devices", "DeviceProfile")
    DeviceProfile.objects.update_or_create(
        model_name=BG709B_PROFILE["model_name"],
        defaults=BG709B_PROFILE,
    )


def backwards(apps, schema_editor):
    DeviceProfile = apps.get_model("devices", "DeviceProfile")
    DeviceProfile.objects.filter(model_name=BG709B_PROFILE["model_name"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("devices", "0006_deviceprofile_ble_bidirectional_and_seed_dbp6296b"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
