import typing

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django_stubs_ext.db.models.manager import RelatedManager

# ---------------------------------------------------------------------------
# Choices
# ---------------------------------------------------------------------------


class IngestionStatus(models.TextChoices):
    """Status of a JBA or ARC ingestion run."""

    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    PARTIAL = "partial", "Partial"


class TriggerEventStatus(models.TextChoices):
    """Workflow status of an ARC parametric trigger event."""

    PENDING_REVIEW = "pending_review", "Pending Review"
    CONFIRMED = "confirmed", "Confirmed"
    REJECTED = "rejected", "Rejected"
    SENT = "sent", "Sent"
    SEND_FAILED = "send_failed", "Send Failed"


class HdxFileType(models.TextChoices):
    """File format of an HDX reference dataset."""

    GEOJSON = "geojson", "GeoJSON"
    CSV = "csv", "CSV"


# ---------------------------------------------------------------------------
# JBA ingestion
# ---------------------------------------------------------------------------


class JbaIngestionRun(models.Model):
    """Tracks each daily JBA fetch job."""

    Status = IngestionStatus  # convenience alias

    run_date = models.DateField()
    forecast_issue_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=IngestionStatus.choices,
        default=IngestionStatus.PENDING,
    )
    files_expected = models.IntegerField(null=True, blank=True)
    files_processed = models.IntegerField(null=True, blank=True)
    csv = models.FileField(upload_to="jba/csv/", null=True, blank=True)
    error_log = models.JSONField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # reverse relation type hints
    forecast_files: typing.ClassVar[RelatedManager["FloodForecastFile"]]

    class Meta:
        verbose_name = "JBA Ingestion Run"
        verbose_name_plural = "JBA Ingestion Runs"
        ordering = ["-run_date"]

    @typing.override
    def __str__(self) -> str:
        return f"JBA run {self.run_date} [{self.status}]"


class FloodForecastFile(models.Model):
    """One TIFF file downloaded from JBA, stored in Azure Blob.

    JBA delivers 10 TIFFs per day (one per lead time) plus a single CSV for the
    whole run — the CSV URL lives on JbaIngestionRun, not here.

    lead_time_days is NOT a column — derive it as:
        forecast_target_date - forecast_issue_date
    """

    ingestion_run = models.ForeignKey(
        JbaIngestionRun,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="forecast_files",
    )
    forecast_issue_date = models.DateField()
    forecast_target_date = models.DateField()
    tiff = models.FileField(upload_to="jba/tiff/")
    original_filename = models.TextField(null=True, blank=True)
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    # bounds (GEOMETRY(Polygon, 4326)) — added via RunSQL in migration, not mapped here
    created_at = models.DateTimeField(auto_now_add=True)

    # reverse relation type hints
    impacts: typing.ClassVar[RelatedManager["FloodForecastImpact"]]

    class Meta:
        verbose_name = "Flood Forecast File"
        verbose_name_plural = "Flood Forecast Files"
        ordering = ["-forecast_issue_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["forecast_issue_date", "forecast_target_date"],
                name="unique_forecast_issue_target_date",
            ),
        ]

    @typing.override
    def __str__(self) -> str:
        return f"Forecast {self.forecast_issue_date} → {self.forecast_target_date}"


class FloodForecastImpact(models.Model):
    """Ensemble-aggregated band_5 stats, one row per admin area per (issue, target) date pair.

    Raw 51-ensemble values are NOT retained — the source CSV in blob storage
    is the authoritative record.
    """

    forecast_file = models.ForeignKey(
        FloodForecastFile,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="impacts",
    )
    admin_area = models.ForeignKey(
        "admin_areas.AdminArea",
        on_delete=models.PROTECT,
        related_name="flood_impacts",
    )
    forecast_issue_date = models.DateField()
    forecast_target_date = models.DateField()
    # NUMERIC columns — DecimalField with generous precision
    band_5_mean = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    band_5_median = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    band_5_p75 = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    band_5_p90 = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    band_5_max = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    ensembles_nonzero_count = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Flood Forecast Impact"
        verbose_name_plural = "Flood Forecast Impacts"
        ordering = ["-forecast_issue_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["forecast_issue_date", "forecast_target_date", "admin_area"],
                name="unique_impact_issue_target_admin",
            ),
        ]

    @typing.override
    def __str__(self) -> str:
        return f"Impact {self.forecast_issue_date} → {self.forecast_target_date} [{self.admin_area_id}]"  # type: ignore[reportAttributeAccessIssue]


# ---------------------------------------------------------------------------
# ARC parametric rainfall
# ---------------------------------------------------------------------------


class ArcIngestionRun(models.Model):
    """Tracks each daily ARC fetch job.

    Mirrors JbaIngestionRun so operators have a single place to check whether
    today's ingestion ran successfully and to diagnose failures.
    """

    Status = IngestionStatus  # convenience alias

    run_date = models.DateField(unique=True)
    status = models.CharField(
        max_length=20,
        choices=IngestionStatus.choices,
        default=IngestionStatus.PENDING,
    )
    rows_expected = models.IntegerField(null=True, blank=True)
    rows_processed = models.IntegerField(null=True, blank=True)
    source_csv = models.FileField(upload_to="arc/csv/", null=True, blank=True)
    error_log = models.JSONField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # reverse relation type hints
    observations: typing.ClassVar[RelatedManager["ArcRainfallObservation"]]

    class Meta:
        verbose_name = "ARC Ingestion Run"
        verbose_name_plural = "ARC Ingestion Runs"
        ordering = ["-run_date"]

    @typing.override
    def __str__(self) -> str:
        return f"ARC run {self.run_date} [{self.status}]"


class ArcRainfallObservation(models.Model):
    """ARC parametric rainfall observation, keyed by admin area.

    Column name cell_trigger is preserved from the JBA source CSV for
    traceability — do not rename.
    """

    ingestion_run = models.ForeignKey(
        ArcIngestionRun,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="observations",
    )
    observation_date = models.DateField()
    admin_area = models.ForeignKey(
        "admin_areas.AdminArea",
        on_delete=models.PROTECT,
        related_name="arc_observations",
    )
    rainfall_raw = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    rainfall = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    impact = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    event_rp = models.IntegerField(null=True, blank=True)
    cell_trigger = models.BooleanField()
    ingested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ARC Rainfall Observation"
        verbose_name_plural = "ARC Rainfall Observations"
        ordering = ["-observation_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["observation_date", "admin_area"],
                name="unique_arc_obs_date_admin",
            ),
        ]

    @typing.override
    def __str__(self) -> str:
        return f"ARC {self.observation_date} [{self.admin_area_id}]"  # type: ignore[reportAttributeAccessIssue]


class ArcTriggerEvent(models.Model):
    """Workflow record created each time the ARC threshold trips.

    MRCS staff must confirm or reject before notifications go out.
    affected_admin_areas stores the integer PKs of AdminArea rows
    that crossed the threshold on trigger_date.
    """

    Status = TriggerEventStatus  # convenience alias

    trigger_date = models.DateField(unique=True)
    triggered_admin_areas_count = models.IntegerField()
    affected_admin_areas = ArrayField(models.IntegerField(), null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=TriggerEventStatus.choices,
        default=TriggerEventStatus.PENDING_REVIEW,
    )
    reviewed_by = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reviewed_trigger_events",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(null=True, blank=True)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # reverse relation type hints
    notification_logs: typing.ClassVar[RelatedManager["apps.notifications.models.NotificationLog"]]  # type: ignore[name-defined]  # noqa: F821

    class Meta:
        verbose_name = "ARC Trigger Event"
        verbose_name_plural = "ARC Trigger Events"
        ordering = ["-trigger_date"]

    @typing.override
    def __str__(self) -> str:
        return f"Trigger {self.trigger_date} [{self.status}]"

    def get_admin_review_path(self) -> str:
        """Relative URL to the admin review page for this event.

        Prepend APP_DOMAIN at the call site to form an absolute URL for emails.
        Example: f"{settings.APP_DOMAIN}{event.get_admin_review_path()}"
        """
        from django.urls import reverse

        return reverse("admin:pipeline_arctriggerevent_review", args=[self.pk])


# ---------------------------------------------------------------------------
# HDX reference datasets
# ---------------------------------------------------------------------------


class HdxDataset(models.Model):
    """Reference data manually loaded from HDX.

    Small structured data is stored inline in the data JSONB field;
    larger files are stored in Azure Blob and referenced by file_blob_url.
    """

    FileType = HdxFileType  # convenience alias

    dataset_name = models.TextField()
    hdx_url = models.TextField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    file_type = models.CharField(max_length=10, choices=HdxFileType.choices)
    file = models.FileField(upload_to="hdx/", null=True, blank=True)
    data = models.JSONField(null=True, blank=True)
    loaded_by = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="loaded_datasets",
    )
    loaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "HDX Dataset"
        verbose_name_plural = "HDX Datasets"
        ordering = ["-loaded_at"]

    @typing.override
    def __str__(self) -> str:
        return self.dataset_name
