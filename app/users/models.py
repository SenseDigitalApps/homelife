from django.conf import settings
from django.db import models


class BiologicalSex(models.TextChoices):
    MASCULINO = "masculino", "Masculino"
    FEMENINO = "femenino", "Femenino"


class ActivityLevel(models.TextChoices):
    SEDENTARIO = "sedentario", "Sedentario"
    LIGERO = "ligero", "Ligero"
    MODERADO = "moderado", "Moderado"
    ACTIVO = "activo", "Activo"
    MUY_ACTIVO = "muy_activo", "Muy activo"


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    birth_date = models.DateField(null=True, blank=True)
    biological_sex = models.CharField(
        max_length=10, choices=BiologicalSex.choices, blank=True, default=""
    )
    initial_weight_kg = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    height_cm = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True
    )
    activity_level = models.CharField(
        max_length=15, choices=ActivityLevel.choices, blank=True, default=""
    )
    preexisting_conditions = models.TextField(blank=True, default="")

    def __str__(self) -> str:
        return f"Profile of {self.user.username}"
