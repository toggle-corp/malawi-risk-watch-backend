import signal
import time
import typing
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from django.db import connections
from django.db.utils import OperationalError


def timeout_handler(*_):
    raise Exception("The command timed out.")


class Command(BaseCommand):
    help = "Wait for resources our application depends on"

    def wait_for_db(self):
        self.stdout.write("Waiting for DB...")
        db_conn = None
        start_time = time.time()
        while True:
            try:
                db_conn = connections["default"]
                db_conn.ensure_connection()
                break
            except OperationalError:
                ...
            self.stdout.write(self.style.WARNING("DB not available, waiting..."))
            time.sleep(1)

        self.stdout.write(self.style.SUCCESS(f"DB is available after {time.time() - start_time} seconds"))

    def wait_for_s3(self):
        """Wait for the S3-compatible blob storage endpoint to be reachable.

        Uses AWS_S3_CONFIG_OPTIONS.endpoint_url — set when AWS_S3_ENABLED=true.
        Polls the root of the endpoint; any HTTP response (including 403) means the
        service is up. Only used in environments where storage runs in-cluster
        (e.g. local MinIO in the alpha/dev helm environment).
        """
        self.stdout.write("Waiting for S3 storage...")
        aws_config = getattr(settings, "AWS_S3_CONFIG_OPTIONS", None) or {}
        endpoint_url = aws_config.get("endpoint_url")
        if endpoint_url is None:
            self.stdout.write(self.style.WARNING("No S3 endpoint_url configured. Skipping."))
            return

        start_time = time.time()
        while True:
            try:
                response = requests.get(urljoin(endpoint_url, "/minio/health/live"), timeout=5)
                if response.status_code == 200:
                    break
            except requests.exceptions.RequestException:
                ...
            self.stdout.write(self.style.WARNING("S3 storage not available, waiting..."))
            time.sleep(5)

        self.stdout.write(self.style.SUCCESS(f"S3 storage is available after {time.time() - start_time} seconds"))

    @typing.override
    def add_arguments(self, parser: CommandParser):
        parser.add_argument(
            "--timeout",
            type=int,
            default=600,
            help="Max seconds to wait before giving up (default: 600).",
        )
        parser.add_argument("--db", action="store_true", help="Wait for DB to be available")
        parser.add_argument("--s3", action="store_true", help="Wait for S3-compatible storage to be available")
        parser.add_argument("--all", action="store_true", help="Wait for all resources")

    @typing.override
    def handle(self, **kwargs: typing.Any):
        timeout = kwargs["timeout"]
        _all = kwargs["all"]

        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)

        try:
            if _all or kwargs["db"]:
                self.wait_for_db()
            if _all or kwargs["s3"]:
                self.wait_for_s3()
        finally:
            signal.alarm(0)
