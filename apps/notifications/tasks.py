import logging

from celery import shared_task
from django.template.loader import render_to_string
from django.utils import timezone

from apps.notifications.models import NotificationLog, NotificationRecipient
from apps.pipeline.models import ArcTriggerEvent, TriggerEventStatus
from utils.email.service import send_email

logger = logging.getLogger(__name__)


@shared_task
def send_arc_trigger_notifications(trigger_event_id: int) -> None:
    """Send notification emails to all recipients scoped to the affected admin areas.

    For each recipient whose admin_area_ids overlaps with the event's affected_admin_areas:
      - Render the HTML email template
      - Send the email
      - Log the result in NotificationLog (unique per trigger_event + recipient_email)

    After all sends, update the event status to SENT or SEND_FAILED.
    """
    logger.info("send_arc_trigger_notifications: starting for trigger_event_id=%s", trigger_event_id)

    try:
        event = ArcTriggerEvent.objects.select_related("reviewed_by").get(pk=trigger_event_id)
    except ArcTriggerEvent.DoesNotExist:
        logger.error("send_arc_trigger_notifications: ArcTriggerEvent %s not found", trigger_event_id)
        return

    affected_areas = event.affected_admin_areas or []

    recipients = NotificationRecipient.objects.filter(
        is_active=True,
        admin_area_ids__overlap=affected_areas,
    )

    if not recipients.exists():
        logger.info("No active recipients for trigger event %s — marking as sent", trigger_event_id)
        ArcTriggerEvent.objects.filter(pk=trigger_event_id).update(
            status=TriggerEventStatus.SENT,
            email_sent_at=timezone.now(),
        )
        return

    reviewed_by_name = (event.reviewed_by.name or event.reviewed_by.email) if event.reviewed_by else "MRCS Staff"
    reviewed_at_display = event.reviewed_at.strftime("%d %b %Y, %H:%M UTC") if event.reviewed_at else ""

    context = {
        "trigger_date": event.trigger_date.strftime("%d %b %Y"),
        "triggered_admin_areas_count": event.triggered_admin_areas_count,
        "reviewed_by": reviewed_by_name,
        "reviewed_at": reviewed_at_display,
        "review_notes": event.review_notes or "",
    }
    html = render_to_string("email/arc_trigger_notification.html", context)
    subject = f"ARC Parametric Trigger Alert — {event.trigger_date.strftime('%d %b %Y')}"

    any_failure = False

    for recipient in recipients:
        # Skip if already logged (idempotency — task may be retried)
        if NotificationLog.objects.filter(trigger_event=event, recipient_email=recipient.email).exists():
            continue

        status = NotificationLog.Status.SENT
        error_text = None

        try:
            send_email(subject=subject, to_email=[recipient.email], html=html)
        except Exception:
            logger.exception("Failed to send email to %s for trigger event %s", recipient.email, trigger_event_id)
            status = NotificationLog.Status.FAILED
            error_text = "Email send raised an exception"
            any_failure = True

        NotificationLog.objects.create(
            trigger_event=event,
            recipient=recipient,
            recipient_email=recipient.email,
            status=status,
            error=error_text,
        )

    event_status = TriggerEventStatus.SEND_FAILED if any_failure else TriggerEventStatus.SENT
    ArcTriggerEvent.objects.filter(pk=trigger_event_id).update(
        status=event_status,
        email_sent_at=timezone.now(),
    )
    logger.info(
        "Notifications for trigger event %s complete — status=%s",
        trigger_event_id,
        event_status,
    )
