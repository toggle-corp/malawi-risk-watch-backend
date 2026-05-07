import strawberry
from strawberry.types import Info

from apps.pipeline.models import ArcTriggerEvent
from apps.pipeline.serializers import ReviewTriggerEventSerializer
from main.graphql.permissions import IsReviewerOrAbove

from .inputs import ReviewTriggerEventInput
from .types import ArcTriggerEventType


@strawberry.type
class Mutation:
    @strawberry.mutation(permission_classes=[IsReviewerOrAbove])
    def review_trigger_event(self, info: Info, input: ReviewTriggerEventInput) -> ArcTriggerEventType:
        """Confirm or reject an ARC parametric trigger event.

        On confirm, notification emails are dispatched asynchronously to all
        active recipients scoped to the affected admin areas.
        """
        try:
            event = ArcTriggerEvent.objects.select_related("reviewed_by").get(pk=input.id)
        except ArcTriggerEvent.DoesNotExist as err:
            raise ValueError(f"ArcTriggerEvent with id={input.id} does not exist.") from err

        serializer = ReviewTriggerEventSerializer(
            data={"action": input.action, "review_notes": input.review_notes},
            context={
                "event": event,
                "request_user": info.context.request.user,
            },
        )
        serializer.is_valid(raise_exception=True)
        return serializer.save()  # type: ignore[return-value]
