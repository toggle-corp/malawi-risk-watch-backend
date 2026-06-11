import strawberry
import strawberry_django
from strawberry_django.pagination import OffsetPaginated

from .filters import (
    ArcIngestionRunFilter,
    ArcRainfallObservationFilter,
    ArcTriggerEventFilter,
    FloodForecastFileFilter,
    FloodForecastImpactFilter,
    HdxDatasetFilter,
    JbaIngestionRunFilter,
)
from .orders import (
    ArcIngestionRunOrder,
    ArcRainfallObservationOrder,
    ArcTriggerEventOrder,
    FloodForecastFileOrder,
    FloodForecastImpactOrder,
    HdxDatasetOrder,
    JbaIngestionRunOrder,
)
from .types import (
    ArcIngestionRunType,
    ArcRainfallObservationType,
    ArcTriggerEventType,
    FloodForecastFileType,
    FloodForecastImpactType,
    HdxDatasetType,
    JbaIngestionRunType,
)


@strawberry.type
class Query:
    # -- JBA ingestion runs
    jba_ingestion_runs: OffsetPaginated[JbaIngestionRunType] = strawberry_django.offset_paginated(
        filters=JbaIngestionRunFilter,
        order=JbaIngestionRunOrder,
    )
    jba_ingestion_run: JbaIngestionRunType = strawberry_django.field()

    # -- Flood forecast files (one TIFF per lead time; CSV URL is on the run)
    flood_forecast_files: OffsetPaginated[FloodForecastFileType] = strawberry_django.offset_paginated(
        filters=FloodForecastFileFilter,
        order=FloodForecastFileOrder,
    )
    flood_forecast_file: FloodForecastFileType = strawberry_django.field()

    # -- Flood forecast impacts (aggregated stats per admin area)
    flood_forecast_impacts: OffsetPaginated[FloodForecastImpactType] = strawberry_django.offset_paginated(
        filters=FloodForecastImpactFilter,
        order=FloodForecastImpactOrder,
    )

    # -- ARC ingestion runs
    arc_ingestion_runs: OffsetPaginated[ArcIngestionRunType] = strawberry_django.offset_paginated(
        filters=ArcIngestionRunFilter,
        order=ArcIngestionRunOrder,
    )
    arc_ingestion_run: ArcIngestionRunType = strawberry_django.field()

    # -- ARC rainfall observations
    arc_rainfall_observations: OffsetPaginated[ArcRainfallObservationType] = strawberry_django.offset_paginated(
        filters=ArcRainfallObservationFilter,
        order=ArcRainfallObservationOrder,
    )

    # -- ARC trigger events
    arc_trigger_events: OffsetPaginated[ArcTriggerEventType] = strawberry_django.offset_paginated(
        filters=ArcTriggerEventFilter,
        order=ArcTriggerEventOrder,
    )
    arc_trigger_event: ArcTriggerEventType = strawberry_django.field()

    # -- HDX datasets
    hdx_datasets: OffsetPaginated[HdxDatasetType] = strawberry_django.offset_paginated(
        filters=HdxDatasetFilter,
        order=HdxDatasetOrder,
    )
    hdx_dataset: HdxDatasetType = strawberry_django.field()
