import typing

from celery.schedules import crontab
from sentry_sdk.integrations.celery import beat as sentry_celery_beat


class CronJobOption(typing.TypedDict, total=False):
    """Cronjob options."""

    # https://docs.celeryq.dev/en/latest/reference/celery.app.task.html#celery.app.task.Task.apply_async

    expire_seconds: float
    """
    Seconds in the future for the task should expire.
    The task won't be executed after the expiration time.
    """

    time_limit: int
    soft_time_limit: int
    queue: str


class CeleryBeatSchedule(typing.TypedDict):
    task: str
    schedule: crontab
    options: CronJobOption
    args: tuple[typing.Any, ...] | None


class CronJobSentryConfig(typing.NamedTuple):
    """checkin_margin (min)
    max_runtime (min).
    """

    checkin_margin: int = 5  # In min grace period
    max_runtime: int = 30  # In min
    failure_issue_threshold: int = 1
    recovery_threshold: int = 1


class TimeConstants:
    """Time constants."""

    SECONDS_IN_A_HOUR = 60 * 60
    SECONDS_IN_A_WEEK = 7 * 24 * 60 * 60
    SECONDS_IN_A_MINUTE = 60
    SECONDS_IN_A_DAY = 24 * 60 * 60
    SECONDS_IN_HALF_DAY = 12 * 60 * 60
    SECONDS_IN_THREE_HOURS = 3 * 60 * 60


class CronJob(typing.NamedTuple):
    """CronJob handler."""

    task: str
    schedule: crontab
    args: tuple[typing.Any, ...] | None = None
    sentry_config: CronJobSentryConfig = CronJobSentryConfig()
    options: CronJobOption = {}


SCHEDULES: dict[str, CronJob] = {
    "ingest_jba_data": CronJob(
        task="apps.pipeline.tasks.launch_jba_pipeline",
        schedule=crontab(minute=0, hour=23),  # Trigger Time to be decided.
        options=CronJobOption(expire_seconds=TimeConstants.SECONDS_IN_A_DAY),
        sentry_config=CronJobSentryConfig(
            failure_issue_threshold=2,
            checkin_margin=10,
            max_runtime=12 * 60,
        ),
    ),
    "ingest_arc_data": CronJob(
        task="apps.pipeline.tasks.launch_arc_pipeline",
        schedule=crontab(minute=0, hour=23),  # Trigger Time to be decided.
        options=CronJobOption(expire_seconds=TimeConstants.SECONDS_IN_A_DAY),
        sentry_config=CronJobSentryConfig(
            failure_issue_threshold=2,
            checkin_margin=10,
            max_runtime=12 * 60,
        ),
    ),
    "celery_queue_uptime_default": CronJob(
        task="apps.pipeline.tasks.celery_queue_uptime_check",
        args=("default",),
        schedule=crontab(minute="0", hour="*"),
        options=CronJobOption(expire_seconds=TimeConstants.SECONDS_IN_A_HOUR),
        sentry_config=CronJobSentryConfig(
            failure_issue_threshold=2,
            checkin_margin=2,
            max_runtime=2,
        ),
    ),
}

BEAT_SCHEDULES: dict[str, CeleryBeatSchedule] = {
    name: {
        "task": config.task,
        "args": config.args,
        "schedule": config.schedule,
        "options": config.options,
    }
    for name, config in SCHEDULES.items()
}


_get_monitor_config = sentry_celery_beat._get_monitor_config  # type: ignore[attr-defined]


class SentryMonkeyPatch:
    @staticmethod
    def custom__get_monitor_config(celery_schedule, app, monitor_name):
        config = _get_monitor_config(celery_schedule, app, monitor_name)
        job_config = SCHEDULES.get(monitor_name)
        if job_config:
            # Adding additional custom configs
            config.update(
                {
                    "checkin_margin": job_config.sentry_config.checkin_margin,
                    "max_runtime": job_config.sentry_config.max_runtime,
                    "failure_issue_threshold": job_config.sentry_config.failure_issue_threshold,
                    "recovery_threshold": job_config.sentry_config.recovery_threshold,
                },
            )
        return config


sentry_celery_beat._get_monitor_config = SentryMonkeyPatch.custom__get_monitor_config  # type: ignore[attr-defined]
