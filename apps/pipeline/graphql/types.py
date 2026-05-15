from decimal import Decimal

import strawberry
import strawberry_django

from apps.admin_areas.graphql.types import AdminAreaType
from apps.pipeline.models import (
    ArcRainfallObservation,
    ArcTriggerEvent,
    FloodForecastFile,
    FloodForecastImpact,
    HdxDataset,
    JbaIngestionRun,
)
from apps.users.graphql.types import UserType

# ---------------------------------------------------------------------------
# JBA ingestion
# ---------------------------------------------------------------------------


@strawberry_django.type(JbaIngestionRun)
class JbaIngestionRunType:
    id: strawberry.ID
    run_date: strawberry.auto
    forecast_issue_time: strawberry.auto
    status: strawberry.auto
    files_expected: strawberry.auto
    files_processed: strawberry.auto
    # Single CSV covering all lead times for this run
    csv_blob_url: strawberry.auto
    error_log: strawberry.auto
    started_at: strawberry.auto
    completed_at: strawberry.auto


@strawberry_django.type(FloodForecastFile)
class FloodForecastFileType:
    id: strawberry.ID
    ingestion_run_id: strawberry.ID | None
    forecast_issue_date: strawberry.auto
    forecast_target_date: strawberry.auto
    tiff_blob_url: strawberry.auto
    original_filename: strawberry.auto
    file_size_bytes: strawberry.auto
    created_at: strawberry.auto

    @strawberry.field(description="Computed as forecast_target_date - forecast_issue_date.")
    def lead_time_days(self) -> int | None:
        if self.forecast_target_date and self.forecast_issue_date:
            return (self.forecast_target_date - self.forecast_issue_date).days
        return None


@strawberry_django.type(FloodForecastImpact)
class FloodForecastImpactType:
    id: strawberry.ID
    forecast_file_id: strawberry.ID | None
    admin_area_id: strawberry.ID
    admin_area: AdminAreaType
    forecast_issue_date: strawberry.auto
    forecast_target_date: strawberry.auto
    band_5_mean: Decimal | None
    band_5_median: Decimal | None
    band_5_p75: Decimal | None
    band_5_p90: Decimal | None
    band_5_max: Decimal | None
    ensembles_nonzero_count: strawberry.auto
    created_at: strawberry.auto

    @strawberry.field(description="Computed as forecast_target_date - forecast_issue_date.")
    def lead_time_days(self) -> int | None:
        if self.forecast_target_date and self.forecast_issue_date:
            return (self.forecast_target_date - self.forecast_issue_date).days
        return None


# ---------------------------------------------------------------------------
# ARC rainfall
# ---------------------------------------------------------------------------


@strawberry_django.type(ArcRainfallObservation)
class ArcRainfallObservationType:
    id: strawberry.ID
    observation_date: strawberry.auto
    admin_area_id: strawberry.ID
    admin_area: AdminAreaType
    rainfall_raw: Decimal | None
    rainfall: Decimal | None
    impact: Decimal | None
    event_rp: strawberry.auto
    cell_trigger: strawberry.auto
    # Raw data URL
    source_csv_blob_url: strawberry.auto
    ingested_at: strawberry.auto


@strawberry_django.type(ArcTriggerEvent)
class ArcTriggerEventType:
    id: strawberry.ID
    trigger_date: strawberry.auto
    triggered_admin_areas_count: strawberry.auto
    affected_admin_areas: list[int] | None
    status: strawberry.auto
    reviewed_by_id: strawberry.ID | None
    reviewed_by: UserType | None
    reviewed_at: strawberry.auto
    review_notes: strawberry.auto
    email_sent_at: strawberry.auto
    created_at: strawberry.auto


# ---------------------------------------------------------------------------
# HDX
# ---------------------------------------------------------------------------


@strawberry_django.type(HdxDataset)
class HdxDatasetType:
    id: strawberry.ID
    dataset_name: strawberry.auto
    hdx_url: strawberry.auto
    description: strawberry.auto
    file_type: strawberry.auto
    # Raw data URL
    file_blob_url: strawberry.auto
    data: strawberry.auto
    loaded_by_id: strawberry.ID | None
    loaded_by: UserType | None
    loaded_at: strawberry.auto
