import logging
import os
from logging.config import dictConfig

from banjo_utils.celery_health.worker import setup_worker_heartbeat
from celery import Celery, signals

from main.cronjobs import BEAT_SCHEDULES

logger = logging.getLogger(__name__)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")

app = Celery("main")

# banjo-utils worker heartbeat writer (read by banjo-celery-probe for k8s liveness).
setup_worker_heartbeat(app)

app.config_from_object("django.conf:settings", namespace="CELERY")

app.conf.task_default_queue = "default"

app.autodiscover_tasks()

app.conf.beat_schedule = BEAT_SCHEDULES


@signals.setup_logging.connect
def config_loggers(**_):
    from django.conf import settings  # noqa: PLC0415

    dictConfig(settings.LOGGING)
