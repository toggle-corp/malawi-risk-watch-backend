from django.contrib import admin

from .models import NotificationLog, NotificationRecipient


@admin.register(NotificationRecipient)
class NotificationRecipientAdmin(admin.ModelAdmin):
    list_display = ["email", "name", "organization", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["email", "name", "organization"]


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ["recipient_email", "trigger_event", "status", "sent_at"]
    list_filter = ["status"]
    ordering = ["-sent_at"]
