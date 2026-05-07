import typing

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django_stubs_ext.db.models.manager import RelatedManager

from .managers import UserManager


class UserRole(models.TextChoices):
    """Role-based access level for MRCS staff."""

    ADMIN = "admin", "Admin"
    REVIEWER = "reviewer", "Reviewer"
    VIEWER = "viewer", "Viewer"


class User(AbstractBaseUser, PermissionsMixin):
    """MRCS staff identity.

    Local Django auth for now; go_user_id will be populated when IFRC Go
    JWT integration is wired up. Password storage is intentional for the
    local-auth phase only — it will be removed once Go auth is live.
    """

    Role = UserRole  # convenience alias: User.Role.ADMIN

    # go_user_id is nullable during local-auth phase; will become NOT NULL
    # once IFRC Go integration is enabled.
    go_user_id = models.TextField(unique=True, null=True, blank=True)
    email = models.EmailField(unique=True)
    name = models.TextField(null=True, blank=True)
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.VIEWER)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Django admin access
    created_at = models.DateTimeField(auto_now_add=True)
    # last_login is provided by AbstractBaseUser

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    # reverse relation type hints
    reviewed_trigger_events: typing.ClassVar[RelatedManager["apps.pipeline.models.ArcTriggerEvent"]]  # type: ignore[name-defined]  # noqa: F821
    loaded_datasets: typing.ClassVar[RelatedManager["apps.pipeline.models.HdxDataset"]]  # type: ignore[name-defined]  # noqa: F821
    added_recipients: typing.ClassVar[RelatedManager["apps.notifications.models.NotificationRecipient"]]  # type: ignore[name-defined]  # noqa: F821

    class Meta:  # type: ignore[reportIncompatibleVariableOverride]
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["email"]

    @typing.override
    def __str__(self) -> str:
        return f"{self.name or self.email}"
