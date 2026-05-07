import strawberry


@strawberry.input
class ReviewTriggerEventInput:
    """Input for confirming or rejecting an ARC trigger event."""

    id: strawberry.ID
    action: str  # "confirm" | "reject"
    review_notes: str | None = None
