import typing

from django.utils import timezone
from rest_framework import serializers

from apps.notifications.tasks import send_arc_trigger_notifications
from apps.pipeline.models import ArcTriggerEvent, TriggerEventStatus


class ReviewTriggerEventSerializer(serializers.Serializer):
    """Validates a confirm or reject action on an ARC trigger event."""

    ACTION_CONFIRM = "confirm"
    ACTION_REJECT = "reject"
    ACTION_CHOICES = [
        (ACTION_CONFIRM, "Confirm"),
        (ACTION_REJECT, "Reject"),
    ]

    action = serializers.ChoiceField(choices=ACTION_CHOICES)
    review_notes = serializers.CharField(required=False, allow_blank=True, default="")

    @typing.override
    def validate(self, attrs: dict) -> dict:
        event: ArcTriggerEvent = self.context["event"]
        if event.status != TriggerEventStatus.PENDING_REVIEW:
            raise serializers.ValidationError(
                f"Trigger event is not pending review (current status: {event.status}).",
            )
        return attrs

    def save(self) -> ArcTriggerEvent:  # type: ignore[override]
        from django.db import transaction

        data: dict = self.validated_data  # type: ignore[reportAssignmentType]
        event: ArcTriggerEvent = self.context["event"]
        reviewer = self.context["request_user"]
        action = data["action"]
        review_notes = data.get("review_notes") or None

        new_status = TriggerEventStatus.CONFIRMED if action == self.ACTION_CONFIRM else TriggerEventStatus.REJECTED

        event.status = new_status
        event.reviewed_by = reviewer
        event.reviewed_at = timezone.now()
        event.review_notes = review_notes
        event.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_notes"])

        if new_status == TriggerEventStatus.CONFIRMED:
            transaction.on_commit(lambda: send_arc_trigger_notifications.delay(event.pk))  # type: ignore[reportFunctionMemberAccess]

        return event
