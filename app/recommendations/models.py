from django.conf import settings
from django.db import models

from measurements.models import Measurement


class Recommendation(models.Model):
    class Engine(models.TextChoices):
        RULES = "rules", "Rules"
        AI = "ai", "AI"

    class Level(models.TextChoices):
        NORMAL = "normal", "Normal"
        PREVENTIVE = "preventive", "Preventive"
        CRITICAL = "critical", "Critical"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recommendations"
    )
    measurement = models.ForeignKey(
        Measurement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recommendations",
    )
    engine = models.CharField(max_length=20, choices=Engine.choices)
    text = models.TextField()
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.NORMAL)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self) -> str:
        return f"{self.engine} - {self.level}"
