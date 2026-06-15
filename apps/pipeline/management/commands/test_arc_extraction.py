import typing
from datetime import datetime
from io import BytesIO
from pathlib import Path

import polars as pl
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.pipeline.extraction.arc.pipeline import ArcPipeline
from apps.pipeline.models import ArcIngestionRun, IngestionStatus

TEST_CSV = Path(__file__).resolve().parent.parent.parent.parent.parent / "dummy" / "NASA_grid_togglecorp_malawi_test1.csv"


class Command(BaseCommand):
    help = "Run ARC pipeline with test CSV to verify the happy path."

    @typing.override
    def handle(self, *args: typing.Any, **kwargs: typing.Any) -> None:

        run = ArcIngestionRun.objects.create(
            status=IngestionStatus.PENDING,
            run_date=timezone.now(),
        )
        self.stdout.write(f"Created ArcIngestionRun pk={run.pk}")

        try:
            raw_bytes = TEST_CSV.read_bytes()
            df = pl.read_csv(BytesIO(raw_bytes))
            obs_date = timezone.make_aware(datetime(2026, 6, 6))

            pipeline = ArcPipeline(arc_ingestion_run=run)
            written = pipeline.run_test_with_df(df, observation_date=obs_date)

            run.status = IngestionStatus.SUCCESS
            run.save(update_fields=["status"])

            self.stdout.write(self.style.SUCCESS(f"Written {written} row(s) to DB."))

        except Exception as exc:
            run.status = IngestionStatus.FAILED
            run.save(update_fields=["status"])
            self.stderr.write(self.style.ERROR(f"Pipeline failed: {exc}"))
            raise
