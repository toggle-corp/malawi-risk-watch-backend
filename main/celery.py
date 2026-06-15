import logging
import os
from logging.config import dictConfig

from celery import Celery, signals

from main.cronjobs import BEAT_SCHEDULES

logger = logging.getLogger(__name__)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")

app = Celery("main")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.conf.task_default_queue = "default"

app.autodiscover_tasks()

app.conf.beat_schedule = BEAT_SCHEDULES


@signals.setup_logging.connect
def config_loggers(**_):
    from django.conf import settings  # noqa: PLC0415

    dictConfig(settings.LOGGING)
