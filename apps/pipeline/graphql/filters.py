import strawberry
import strawberry_django
from django.db.models import Q

from apps.pipeline.models import (
    ArcRainfallObservation,
    ArcTriggerEvent,
    FloodForecastFile,
    FloodForecastImpact,
    HdxDataset,
    JbaIngestionRun,
)


@strawberry_django.filters.filter(JbaIngestionRun, lookups=True)
class JbaIngestionRunFilter:
    id: strawberry.ID | None = strawberry.UNSET
    status: str | None = strawberry.UNSET
    run_date: strawberry.auto


@strawberry_django.filters.filter(FloodForecastFile, lookups=True)
class FloodForecastFileFilter:
    id: strawberry.ID | None = strawberry.UNSET
    ingestion_run_id: strawberry.ID | None = strawberry.UNSET
    forecast_issue_date: strawberry.auto
    forecast_target_date: strawberry.auto


@strawberry_django.filters.filter(FloodForecastImpact, lookups=True)
class FloodForecastImpactFilter:
    id: strawberry.ID | None = strawberry.UNSET
    admin_area_id: strawberry.ID | None = strawberry.UNSET
    forecast_issue_date: strawberry.auto
    forecast_target_date: strawberry.auto


@strawberry_django.filters.filter(ArcRainfallObservation, lookups=True)
class ArcRainfallObservationFilter:
    id: strawberry.ID | None = strawberry.UNSET
    admin_area_id: strawberry.ID | None = strawberry.UNSET
    cell_trigger: bool | None = strawberry.UNSET
    observation_date: strawberry.auto


@strawberry_django.filters.filter(ArcTriggerEvent, lookups=True)
class ArcTriggerEventFilter:
    id: strawberry.ID | None = strawberry.UNSET
    status: str | None = strawberry.UNSET
    trigger_date: strawberry.auto


@strawberry_django.filters.filter(HdxDataset, lookups=True)
class HdxDatasetFilter:
    id: strawberry.ID | None = strawberry.UNSET
    file_type: str | None = strawberry.UNSET

    @strawberry_django.filter_field
    def search(self, value: str, prefix: str) -> Q:
        return Q(dataset_name__icontains=value) | Q(description__icontains=value)
