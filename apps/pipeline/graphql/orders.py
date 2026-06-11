import strawberry
import strawberry_django

from apps.pipeline.models import (
    ArcIngestionRun,
    ArcRainfallObservation,
    ArcTriggerEvent,
    FloodForecastFile,
    FloodForecastImpact,
    HdxDataset,
    JbaIngestionRun,
)


@strawberry_django.order_type(JbaIngestionRun)
class JbaIngestionRunOrder:
    run_date: strawberry.auto
    started_at: strawberry.auto


@strawberry_django.order_type(FloodForecastFile)
class FloodForecastFileOrder:
    forecast_issue_date: strawberry.auto
    forecast_target_date: strawberry.auto
    created_at: strawberry.auto


@strawberry_django.order_type(FloodForecastImpact)
class FloodForecastImpactOrder:
    forecast_issue_date: strawberry.auto
    forecast_target_date: strawberry.auto
    created_at: strawberry.auto


@strawberry_django.order_type(ArcIngestionRun)
class ArcIngestionRunOrder:
    run_date: strawberry.auto
    started_at: strawberry.auto


@strawberry_django.order_type(ArcRainfallObservation)
class ArcRainfallObservationOrder:
    observation_date: strawberry.auto
    ingested_at: strawberry.auto


@strawberry_django.order_type(ArcTriggerEvent)
class ArcTriggerEventOrder:
    trigger_date: strawberry.auto
    created_at: strawberry.auto


@strawberry_django.order_type(HdxDataset)
class HdxDatasetOrder:
    dataset_name: strawberry.auto
    loaded_at: strawberry.auto
