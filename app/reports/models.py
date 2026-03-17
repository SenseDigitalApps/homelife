from django.conf import settings
from django.db import models


class Report(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports"
    )
    date_from = models.DateField()
    date_to = models.DateField()
    file_url = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Report #{self.id} ({self.date_from} - {self.date_to})"
