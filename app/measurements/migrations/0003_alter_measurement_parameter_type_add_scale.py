from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("measurements", "0002_alter_measurement_parameter_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="measurement",
            name="parameter_type",
            field=models.CharField(
                choices=[
                    ("glucose", "Glucosa"),
                    ("weight", "Peso"),
                    ("impedance", "Impedancia"),
                    ("body_fat_pct", "Grasa corporal %"),
                    ("body_water_pct", "Agua corporal %"),
                    ("muscle_mass", "Masa muscular"),
                    ("bmi", "Índice de masa corporal"),
                    ("bmr", "Metabolismo basal"),
                    ("visceral_fat", "Grasa visceral"),
                    ("spo2", "SpO2"),
                    ("pulse_rate", "Frecuencia de pulso"),
                    ("pi_index", "Índice de perfusión"),
                    ("hrv", "Variabilidad de frecuencia cardíaca"),
                    ("bp_systolic", "Presión sistólica"),
                    ("bp_diastolic", "Presión diastólica"),
                    ("temp", "Temperatura"),
                    ("otro", "Otro"),
                ],
                max_length=50,
            ),
        ),
    ]
