from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("devices", "0008_seed_bascula_jk100"),
    ]

    operations = [
        migrations.AlterField(
            model_name="device",
            name="device_type",
            field=models.CharField(
                choices=[
                    ("glucometro", "Glucómetro"),
                    ("oximetro", "Oxímetro"),
                    ("tensiometro", "Tensiómetro"),
                    ("bascula", "Báscula"),
                    ("termometro", "Termómetro"),
                    ("ecg", "ECG"),
                    ("otro", "Otro"),
                ],
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="deviceprofile",
            name="device_type",
            field=models.CharField(
                choices=[
                    ("glucometro", "Glucómetro"),
                    ("oximetro", "Oxímetro"),
                    ("tensiometro", "Tensiómetro"),
                    ("bascula", "Báscula"),
                    ("termometro", "Termómetro"),
                    ("ecg", "ECG"),
                    ("otro", "Otro"),
                ],
                max_length=30,
            ),
        ),
    ]
