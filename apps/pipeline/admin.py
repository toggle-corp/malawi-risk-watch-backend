from django.contrib import admin

from .models import (
    ArcRainfallObservation,
    ArcTriggerEvent,
    FloodForecastFile,
    FloodForecastImpact,
    HdxDataset,
    JbaIngestionRun,
)


@admin.register(JbaIngestionRun)
class JbaIngestionRunAdmin(admin.ModelAdmin):
    list_display = ["run_date", "status", "files_expected", "files_processed", "started_at"]
    list_filter = ["status"]
    ordering = ["-run_date"]


@admin.register(FloodForecastFile)
class FloodForecastFileAdmin(admin.ModelAdmin):
    list_display = ["forecast_issue_date", "forecast_target_date", "ingestion_run", "created_at"]
    ordering = ["-forecast_issue_date"]


@admin.register(FloodForecastImpact)
class FloodForecastImpactAdmin(admin.ModelAdmin):
    list_display = ["forecast_issue_date", "forecast_target_date", "admin_area", "band_5_mean"]
    ordering = ["-forecast_issue_date"]


@admin.register(ArcRainfallObservation)
class ArcRainfallObservationAdmin(admin.ModelAdmin):
    list_display = ["observation_date", "admin_area", "rainfall", "cell_trigger", "ingested_at"]
    list_filter = ["cell_trigger"]
    ordering = ["-observation_date"]


@admin.register(ArcTriggerEvent)
class ArcTriggerEventAdmin(admin.ModelAdmin):
    list_display = ["trigger_date", "status", "triggered_admin_areas_count", "reviewed_by", "created_at"]
    list_filter = ["status"]
    ordering = ["-trigger_date"]


@admin.register(HdxDataset)
class HdxDatasetAdmin(admin.ModelAdmin):
    list_display = ["dataset_name", "file_type", "loaded_by", "loaded_at"]
    list_filter = ["file_type"]
    ordering = ["-loaded_at"]
