from django.db import migrations


JK100_PROFILE = {
    "name": "Báscula HUIZHOU JK-100",
    "device_type": "bascula",
    "manufacturer": "HUIZHOU",
    "model_name": "JK-100",
    "protocol": "bluetooth",
    "ble_service_uuid": "",
    "ble_notify_characteristic_uuid": "",
    "ble_write_characteristic_uuid": "",
    "ble_characteristic_uuid": "",
    "supported_parameters": [
        "weight",
        "impedance",
        "body_fat_pct",
        "body_water_pct",
        "muscle_mass",
        "bmi",
        "bmr",
        "visceral_fat",
    ],
    "is_active": True,
}


def forwards(apps, schema_editor):
    DeviceProfile = apps.get_model("devices", "DeviceProfile")
    DeviceProfile.objects.update_or_create(
        model_name=JK100_PROFILE["model_name"],
        defaults=JK100_PROFILE,
    )


def backwards(apps, schema_editor):
    DeviceProfile = apps.get_model("devices", "DeviceProfile")
    DeviceProfile.objects.filter(model_name=JK100_PROFILE["model_name"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("devices", "0007_seed_glucometro_bg709b"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
