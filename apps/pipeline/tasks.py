import logging

from celery import shared_task
from django.utils import timezone

from apps.pipeline.extraction.arc.pipeline import ArcPipeline
from apps.pipeline.extraction.jba.pipeline import JBAPipeline
from apps.pipeline.models import ArcIngestionRun, IngestionStatus, JbaIngestionRun

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, retry_backoff=True)
def run_jba_pipeline(self, jba_ingestion_run_id: int) -> None:
    try:
        ingestion_run = JbaIngestionRun.objects.get(id=jba_ingestion_run_id)
    except JbaIngestionRun.DoesNotExist:
        logger.error("JbaIngestionRun %s not found, aborting", jba_ingestion_run_id)
        return

    ingestion_run.set_status(IngestionStatus.RUNNING)

    try:
        pipeline = JBAPipeline(jba_ingestion_run=ingestion_run)
        pipeline.run()
        ingestion_run.set_status(IngestionStatus.SUCCESS)
    except Exception as exc:
        logger.exception("Pipeline failed for run_id=%s", jba_ingestion_run_id)
        if self.request.retries >= self.max_retries:
            ingestion_run.set_status(IngestionStatus.FAILED)
            raise
        raise self.retry(exc=exc) from exc


@shared_task
def launch_jba_pipeline():
    jba_ingestion_run = JbaIngestionRun.objects.create(
        run_date=timezone.now(),
        status=IngestionStatus.PENDING,
    )
    run_jba_pipeline.delay(jba_ingestion_run.id)  # type: ignore[attr-defined]
    logger.info("Queued JBA pipeline. Run ID: %s", jba_ingestion_run.id)


MAX_RETRIES = 3
RETRY_BACKOFF = 60  # seconds; actual delay = RETRY_BACKOFF * 2^attempt


@shared_task(
    bind=True,
    max_retries=1,
    default_retry_delay=30,
    acks_late=True,
)
def launch_arc_pipeline(self) -> None:
    run = ArcIngestionRun.objects.create(
        status=ArcIngestionRun.Status.PENDING,
        run_date=timezone.now(),
    )
    run_arc_pipeline.delay(run.pk)  # type: ignore[attr-defined]
    logger.info("Queued ARC pipeline. Run ID: %s", run.pk)


@shared_task(
    bind=True,
    max_retries=MAX_RETRIES,
    default_retry_delay=RETRY_BACKOFF,
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_arc_pipeline(self, arc_ingestion_run_id: int) -> None:
    try:
        ingestion_run = ArcIngestionRun.objects.get(pk=arc_ingestion_run_id)
    except ArcIngestionRun.DoesNotExist:
        logger.error("ArcIngestionRun %s not found, aborting", arc_ingestion_run_id)
        return

    ingestion_run.set_status(ArcIngestionRun.Status.RUNNING)

    try:
        pipeline = ArcPipeline(arc_ingestion_run=ingestion_run)
        pipeline.run()
        ingestion_run.set_status(ArcIngestionRun.Status.SUCCESS)
    except Exception as exc:
        logger.exception("Pipeline failed for run_id=%s", arc_ingestion_run_id)
        if self.request.retries >= self.max_retries:
            ingestion_run.set_status(ArcIngestionRun.Status.FAILED)
            raise
        raise self.retry(exc=exc) from exc


@shared_task
def celery_queue_uptime_check(queue: str):
    """Check the availability of the Queue."""
    logger.info("Celery Queue %s is consuming tasks.", queue)
