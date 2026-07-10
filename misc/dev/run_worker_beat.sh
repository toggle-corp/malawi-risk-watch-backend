#!/bin/bash -e

./manage.py wait_for_resources --db --cache --celery-broker

celery -A main beat -l info
