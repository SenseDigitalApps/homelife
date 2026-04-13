from django.db import migrations, models


DBP_PROFILE = {
    "name": "Tensiómetro Joytech DBP-6296B",
    "device_type": "tensiometro",
    "manufacturer": "Joytech",
    "model_name": "DBP-6296B",
    "protocol": "bluetooth",
    "ble_service_uuid": "FFF0",
    "ble_notify_characteristic_uuid": "FFF1",
    "ble_write_characteristic_uuid": "FFF2",
    "ble_characteristic_uuid": "FFF1",
    "supported_parameters": ["bp_systolic", "bp_diastolic", "pulse_rate"],
    "is_active": True,
}


def forwards(apps, schema_editor):
    DeviceProfile = apps.get_model("devices", "DeviceProfile")

    # Backward-compatibility: populate notify UUID from existing single characteristic.
    for profile in DeviceProfile.objects.filter(
        ble_notify_characteristic_uuid="", ble_characteristic_uuid__gt=""
    ):
        profile.ble_notify_characteristic_uuid = profile.ble_characteristic_uuid
        profile.save(update_fields=["ble_notify_characteristic_uuid", "updated_at"])

    DeviceProfile.objects.update_or_create(
        model_name=DBP_PROFILE["model_name"],
        defaults=DBP_PROFILE,
    )


def backwards(apps, schema_editor):
    DeviceProfile = apps.get_model("devices", "DeviceProfile")
    DeviceProfile.objects.filter(model_name=DBP_PROFILE["model_name"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("devices", "0005_seed_oximetro_yk67b1"),
    ]

    operations = [
        migrations.AddField(
            model_name="deviceprofile",
            name="ble_notify_characteristic_uuid",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="deviceprofile",
            name="ble_write_characteristic_uuid",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.RunPython(forwards, backwards),
    ]
