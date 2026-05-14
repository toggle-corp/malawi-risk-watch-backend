import typing

from django.contrib.postgres.fields import ArrayField
from django.db import models


class NotificationStatus(models.TextChoices):
    """Delivery status of a notification email send attempt."""

    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"
    BOUNCED = "bounced", "Bounced"


class NotificationRecipient(models.Model):
    """Email distribution list managed by MRCS staff via the admin panel.

    admin_area_ids stores the integer PKs of AdminArea rows this recipient
    is scoped to. updated_at is managed automatically by Django (auto_now=True).
    """

    email = models.EmailField()
    name = models.TextField(null=True, blank=True)
    organization = models.TextField(null=True, blank=True)
    admin_area_ids = ArrayField(models.IntegerField())
    is_active = models.BooleanField(default=True)
    added_by = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="added_recipients",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Notification Recipient"
        verbose_name_plural = "Notification Recipients"
        ordering = ["email"]

    @typing.override
    def __str__(self) -> str:
        return f"{self.name or self.email}"


class NotificationLog(models.Model):
    """Audit trail of every email send attempt.

    recipient_email snapshots the address at send time so the log is
    preserved even if the recipient row is later deleted.
    recipient FK is SET_NULL on delete for the same reason.
    """

    Status = NotificationStatus  # convenience alias

    trigger_event = models.ForeignKey(
        "pipeline.ArcTriggerEvent",
        on_delete=models.PROTECT,
        related_name="notification_logs",
    )
    recipient = models.ForeignKey(
        NotificationRecipient,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notification_logs",
    )
    recipient_email = models.EmailField()
    sent_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=NotificationStatus.choices)
    provider_message_id = models.TextField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Notification Log"
        verbose_name_plural = "Notification Logs"
        ordering = ["-sent_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["trigger_event", "recipient_email"],
                name="unique_notification_trigger_email",
            ),
        ]

    @typing.override
    def __str__(self) -> str:
        return f"Notification to {self.recipient_email} [{self.status}]"
