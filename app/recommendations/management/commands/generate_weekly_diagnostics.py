from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand, CommandParser

from recommendations.engines import generate_weekly_diagnostics_for_period


class Command(BaseCommand):
    help = "Generate weekly deterministic diagnostics for supported devices."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--period-end",
            type=date.fromisoformat,
            help="Inclusive period end date in YYYY-MM-DD format.",
        )

    def handle(self, *args, **options):
        diagnostics = generate_weekly_diagnostics_for_period(period_end=options.get("period_end"))
        self.stdout.write(self.style.SUCCESS(f"Generated {len(diagnostics)} weekly diagnostics."))
