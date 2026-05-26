import typing

from django.contrib import admin, messages
from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from djangoql.admin import DjangoQLSearchMixin

from apps.notifications.models import NotificationRecipient
from apps.pipeline.serializers import ReviewTriggerEventSerializer

from .models import (
    ArcRainfallObservation,
    ArcTriggerEvent,
    FloodForecastFile,
    FloodForecastImpact,
    HdxDataset,
    JbaIngestionRun,
    TriggerEventStatus,
)


@admin.register(JbaIngestionRun)
class JbaIngestionRunAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    list_display = ["run_date", "status", "files_expected", "files_processed", "started_at"]
    list_filter = ["status"]
    ordering = ["-run_date"]


@admin.register(FloodForecastFile)
class FloodForecastFileAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    list_display = ["forecast_issue_date", "forecast_target_date", "ingestion_run", "created_at"]
    ordering = ["-forecast_issue_date"]


@admin.register(FloodForecastImpact)
class FloodForecastImpactAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    list_display = ["forecast_issue_date", "forecast_target_date", "admin_area", "band_5_mean"]
    ordering = ["-forecast_issue_date"]


@admin.register(ArcRainfallObservation)
class ArcRainfallObservationAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    list_display = ["observation_date", "admin_area", "rainfall", "cell_trigger", "ingested_at"]
    list_filter = ["cell_trigger"]
    ordering = ["-observation_date"]


@admin.register(ArcTriggerEvent)
class ArcTriggerEventAdmin(admin.ModelAdmin):
    list_display = ["trigger_date", "status", "review_link", "triggered_admin_areas_count", "reviewed_by", "created_at"]
    list_filter = ["status"]
    ordering = ["-trigger_date"]

    @admin.display(description="Review")
    def review_link(self, obj: ArcTriggerEvent) -> str:
        if obj.status == TriggerEventStatus.PENDING_REVIEW:
            url = reverse("admin:pipeline_arctriggerevent_review", args=[obj.pk])
            return format_html(
                '<a href="{}">{} area(s) — Review</a>',
                url,
                obj.triggered_admin_areas_count,
            )
        return "—"

    @typing.override
    def get_urls(self) -> list:
        urls = super().get_urls()
        custom = [
            path(
                "<int:pk>/review/",
                self.admin_site.admin_view(self.review_view),
                name="pipeline_arctriggerevent_review",
            ),
        ]
        return custom + urls

    def review_view(self, request: HttpRequest, pk: int) -> TemplateResponse | HttpResponseRedirect:
        event = get_object_or_404(ArcTriggerEvent, pk=pk)
        changelist_url = reverse("admin:pipeline_arctriggerevent_changelist")
        is_actionable = event.status == TriggerEventStatus.PENDING_REVIEW

        affected = event.affected_admin_areas or []
        recipients = (
            NotificationRecipient.objects.filter(is_active=True, admin_area_ids__overlap=affected).order_by("name", "email")
            if affected
            else NotificationRecipient.objects.none()
        )
        observations = (
            ArcRainfallObservation.objects.filter(
                observation_date=event.trigger_date,
                admin_area_id__in=affected,
            )
            .select_related("admin_area")
            .order_by("admin_area__name")
            if affected
            else ArcRainfallObservation.objects.none()
        )

        if request.method == "POST":
            if not is_actionable:
                self.message_user(
                    request,
                    f"Trigger event {event.trigger_date} is not pending review and cannot be actioned.",
                    level=messages.WARNING,
                )
                return HttpResponseRedirect(changelist_url)

            serializer = ReviewTriggerEventSerializer(
                data={
                    "action": request.POST.get("action", ""),
                    "review_notes": request.POST.get("review_notes", ""),
                },
                context={"event": event, "request_user": request.user},
            )
            if serializer.is_valid():
                serializer.save()
                action_label = "confirmed" if serializer.validated_data["action"] == "confirm" else "rejected"  # type: ignore[reportAttributeAccessIssue]
                self.message_user(request, f"Trigger event {event.trigger_date} has been {action_label}.")
                return HttpResponseRedirect(changelist_url)

            error_text = "; ".join(f"{k}: {', '.join(v)}" for k, v in serializer.errors.items())
            self.message_user(request, f"Review failed: {error_text}", level=messages.ERROR)

        context = {
            **self.admin_site.each_context(request),
            "opts": ArcTriggerEvent._meta,
            "event": event,
            "recipients": recipients,
            "observations": observations,
            "is_actionable": is_actionable,
            "title": f"Review Trigger Event — {event.trigger_date}",
            "subtitle": str(event),
        }
        return TemplateResponse(request, "admin/pipeline/arctriggerevent/review.html", context)


@admin.register(HdxDataset)
class HdxDatasetAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    list_display = ["dataset_name", "file_type", "loaded_by", "loaded_at"]
    list_filter = ["file_type"]
    ordering = ["-loaded_at"]
