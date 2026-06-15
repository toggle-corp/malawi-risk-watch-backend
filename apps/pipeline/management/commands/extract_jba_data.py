import typing
from typing import Any

from django.core.management.base import BaseCommand

from apps.pipeline.tasks import launch_jba_pipeline


class Command(BaseCommand):
    help = "Trigger JBA Pipeline"

    @typing.override
    def handle(self, *args: Any, **options: Any) -> None:
        launch_jba_pipeline.delay()  # type: ignore[attr-defined]

        self.stdout.write(
            self.style.SUCCESS(
                "Queued JBA extraction successfully.",
            ),
        )
