"""ArcPipeline: a single class that owns the full ingestion lifecycle.

    pipeline = ArcPipeline(arc_ingestion_run=run)
    pipeline.run()

Phases (all private methods on the class)
-----------------------------------------
    _collect             — locate and download the S3 CSV
    _transform           — coerce types, filter, resolve admin areas, aggregate
    _resolve_admin_areas — join coord map from PostGIS onto the DataFrame
    _write               — atomic bulk-insert into the DB
    _save_run_metadata   — persist source CSV and row count on the run record

Supporting modules (kept separate — no reason to live inside the class):
    resolve_geo.py      — resolve_admin_areas  (raw PostGIS round-trip)
    helpers.py  — type-coercion utilities (coerce_cell_trigger, coerce_event_rp)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from io import BytesIO
from pathlib import PurePosixPath

import boto3
import polars as pl
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.pipeline.helpers import coerce_cell_trigger, coerce_event_rp
from apps.pipeline.models import ArcIngestionRun, ArcRainfallObservation, IngestionStatus
from apps.pipeline.resolve_geo import resolve_admin_areas

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {
        "id",
        "lon",
        "lat",
        "date",
        "rainfall_raw",
        "rainfall",
        "impact",
        "event_rp",
        "cell_trigger",
    },
)

_COLUMN_RENAMES: dict[str, str] = {
    "lat": "latitude",
    "lon": "longitude",
    "date": "observation_date",
}


@dataclass(frozen=True)
class S3Config:
    bucket: str
    prefix: str
    aws_access_key_id: str
    aws_secret_access_key: str
    region_name: str

    @classmethod
    def from_settings(cls) -> S3Config:
        arc = settings.ARC_PIPELINE
        return cls(
            bucket=arc["S3_BUCKET"],
            prefix=arc["S3_PREFIX"],
            aws_access_key_id=arc["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=arc["AWS_SECRET_ACCESS_KEY"],
            region_name=arc.get("AWS_REGION", "us-east-1"),
        )


def _make_s3_client(cfg: S3Config):
    return boto3.client(
        "s3",
        aws_access_key_id=cfg.aws_access_key_id,
        aws_secret_access_key=cfg.aws_secret_access_key,
        region_name=cfg.region_name,
    )


@dataclass(frozen=True)
class CSVObject:
    key: str
    raw_bytes: bytes
    df: pl.DataFrame


class ArcPipeline:
    """Orchestrates one ARC rainfall ingestion run end-to-end.

    Parameters
    ----------
    arc_ingestion_run:
        The :class:`~apps.pipeline.models.ArcIngestionRun` record that
        owns this run.

    Usage
    -----
    ::

        pipeline = ArcPipeline(arc_ingestion_run=run)
        pipeline.run()   # raises on failure; caller handles status updates

    """

    def __init__(self, arc_ingestion_run: ArcIngestionRun) -> None:
        self.arc_ingestion_run = arc_ingestion_run
        self._cfg = S3Config.from_settings()

    def get_csv_key(self, dt: date) -> str:
        s3 = _make_s3_client(self._cfg)
        prefix = f"{self._cfg.prefix}/{dt:%m/%d}/"
        paginator = s3.get_paginator("list_objects_v2")

        try:
            for page in paginator.paginate(Bucket=self._cfg.bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if "NASA_grid_togglecorp" in key and key.endswith(".csv"):
                        return key

        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"Failed to list S3 objects: {exc}") from exc

        raise FileNotFoundError("No matching CSV file found")

    def run(self) -> None:
        """Execute collect → transform → write in sequence.

        The observation write and the run-metadata/status update share a single
        transaction so the DB never ends up with rows but a FAILED run (or vice
        versa). Any exception propagates to the Celery task, which owns retry
        scheduling and the failure-status update.
        """
        obs_date = self.arc_ingestion_run.run_date - timedelta(days=1)
        key = self.get_csv_key(dt=obs_date)
        logger.info("Starting ARC pipeline for run=%s", self.arc_ingestion_run.pk)

        csv_object = self._collect(key)
        records = self._transform(csv_object.df, obs_date)

        with transaction.atomic():
            written = self._write(records, obs_date)
            self._save_run_metadata(csv_object, written)

        logger.info("[run=%s] Completed — %d rows written.", self.arc_ingestion_run.pk, written)

    def _collect(self, key: str) -> CSVObject:
        """Download *key* from S3 and return a validated :class:`CSVObject`."""
        logger.info("[run=%s] Downloading s3 key=%s", self.arc_ingestion_run.pk, key)

        s3 = _make_s3_client(self._cfg)

        try:
            response = s3.get_object(Bucket=self._cfg.bucket, Key=key)
            raw_bytes: bytes = response["Body"].read()
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(
                f"Failed to download s3://{self._cfg.bucket}/{key}: {exc}",
            ) from exc

        df = pl.read_csv(BytesIO(raw_bytes))
        self._validate_columns(df, key)

        return CSVObject(key=key, raw_bytes=raw_bytes, df=df)

    def _validate_columns(self, df: pl.DataFrame, source_key: str) -> None:
        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(
                f"CSV {source_key!r} is missing required columns: {sorted(missing)}",
            )

    def _transform(
        self,
        df: pl.DataFrame,
        observation_date: date | None = None,
        target_level: int = 3,
    ) -> list[dict]:
        """Coerce, filter, resolve admin areas, and aggregate raw rows."""
        logger.info("[run=%s] Transforming dataframe", self.arc_ingestion_run.pk)

        # 1. Rename source columns to internal names
        rename_map = {k: v for k, v in _COLUMN_RENAMES.items() if k in df.columns}
        df = df.rename(rename_map)

        # 2. Coerce types
        df = coerce_cell_trigger(df)
        df = (
            coerce_event_rp(df)
            if "event_rp" in df.columns
            else df.with_columns(pl.lit(None).cast(pl.Float64).alias("event_rp"))
        )

        numeric_cols = ["latitude", "longitude", "rainfall", "rainfall_raw", "impact"]
        df = df.with_columns(
            [pl.col(c).cast(pl.Float64, strict=False) for c in numeric_cols],
        )

        if observation_date is not None:
            df = df.with_columns(pl.lit(observation_date).alias("observation_date"))
        else:
            df = df.with_columns(
                pl.col("observation_date").str.to_date(strict=False),
            )

        # 3. Filter: keep only triggered cells
        triggered = df.filter(pl.col("cell_trigger"))
        logger.info(
            "[run=%s] Rows after cell_trigger filter: %d / %d.",
            self.arc_ingestion_run.pk,
            len(triggered),
            len(df),
        )

        if triggered.is_empty():
            logger.info("[run=%s] No triggered cells — nothing to write.", self.arc_ingestion_run.pk)
            return []

        triggered = triggered.drop_nulls(subset=["latitude", "longitude"])

        triggered = self._resolve_admin_areas(triggered, target_level)

        if triggered.is_empty():
            logger.info(
                "[run=%s] No rows left after admin area resolution.",
                self.arc_ingestion_run.pk,
            )
            return []

        agg = triggered.group_by(["observation_date", "admin_area_id"]).agg(
            [
                pl.col("rainfall_raw").sum(),
                pl.col("rainfall").sum(),
                pl.col("impact").sum(),
                pl.col("event_rp").max(),  # NULL when no RP triggered in area
                pl.col("cell_trigger").any(),
            ],
        )

        records = agg.to_dicts()
        logger.info(
            "[run=%s] Aggregated to %d (observation_date, admin_area) record(s).",
            self.arc_ingestion_run.pk,
            len(records),
        )
        return records

    def _resolve_admin_areas(
        self,
        triggered: pl.DataFrame,
        target_level: int,
    ) -> pl.DataFrame:
        unique_coords: list[tuple[float, float]] = triggered.select(["latitude", "longitude"]).unique().rows()
        coord_map = resolve_admin_areas(unique_coords, target_level=target_level)

        # Explode: one row per (coord, admin_area_id) pair
        lookup_rows = [
            {"latitude": lat, "longitude": lon, "admin_area_id": admin_id}
            for (lat, lon), admin_ids in coord_map.items()
            for admin_id in admin_ids  # empty list → no rows for unresolved coords
        ]

        if not lookup_rows:
            logger.warning("[run=%s] No coords resolved to any admin area.", self.arc_ingestion_run.pk)
            return triggered.clear()

        lookup = pl.DataFrame(
            lookup_rows,
            schema={
                "latitude": pl.Float64,
                "longitude": pl.Float64,
                "admin_area_id": pl.Int64,
            },
        )

        # One triggered row can now join to multiple admin areas
        triggered = triggered.join(lookup, on=["latitude", "longitude"], how="left")

        unresolved = triggered["admin_area_id"].null_count()
        if unresolved:
            logger.warning(
                "[run=%s] %d triggered row(s) could not be resolved to any admin area and will be skipped.",
                self.arc_ingestion_run.pk,
                unresolved,
            )

        return triggered.drop_nulls(subset=["admin_area_id"])

    def _write(self, records: list[dict], run_date: date) -> int:
        """Bulk-insert aggregated observation records.

        Raises
        ------
        IntegrityError
            If a (observation_date, admin_area) pair already exists —
            indicates the launcher scheduled the same date twice. The whole
            run (rows + metadata) rolls back together.

        """
        if not records:
            logger.info("[run=%s] No records to write.", self.arc_ingestion_run.pk)
            return 0

        observations = [
            ArcRainfallObservation(
                ingestion_run=self.arc_ingestion_run,
                observation_date=rec["observation_date"],
                admin_area_id=rec["admin_area_id"],
                rainfall_raw=rec["rainfall_raw"],
                rainfall=rec["rainfall"],
                impact=rec["impact"],
                event_rp=int(rec["event_rp"]) if rec.get("event_rp") is not None else None,  # None → NULL
                cell_trigger=rec["cell_trigger"],
            )
            for rec in records
        ]

        ArcRainfallObservation.objects.bulk_create(observations)

        logger.info("[run=%s] Inserted %d rows.", self.arc_ingestion_run.pk, len(observations))
        return len(observations)

    def _save_run_metadata(self, csv_object: CSVObject, written: int) -> None:
        """Persist source CSV, row count, and success status onto the run record."""
        filename = PurePosixPath(csv_object.key).name
        run = self.arc_ingestion_run
        run.rows_processed = written
        run.completed_at = timezone.now()
        run.status = IngestionStatus.SUCCESS
        run.source_csv.save(filename, ContentFile(csv_object.raw_bytes), save=False)
        run.save(update_fields=["rows_processed", "completed_at", "status", "source_csv"])

    # in arc/test_pipeline.py (or pipeline.py later)

    def run_test_with_df(self, df: pl.DataFrame, observation_date: date) -> int:
        """Public entry point for testing — accepts a pre-loaded DataFrame.

        Skips S3 collect phase; otherwise identical to the production path.
        """
        self._validate_columns(df, source_key="<injected>")
        records = self._transform(df, observation_date=observation_date)
        return self._write(records, observation_date)
