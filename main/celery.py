import logging
import os

from celery import Celery

logger = logging.getLogger(__name__)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")

app = Celery("main")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.conf.task_default_queue = "default"

app.autodiscover_tasks()
