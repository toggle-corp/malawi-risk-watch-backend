#!/bin/bash -e

REDIS_HOST_PORT=$(echo $CELERY_REDIS_URL | sed 's|redis://\([^/]*\)/.*|\1|')

./manage.py wait_for_resources --db --cache --celery-broker

./manage.py run_celery_dev
