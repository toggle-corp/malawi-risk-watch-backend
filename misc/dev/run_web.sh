#!/bin/bash -e

./manage.py wait_for_resources --db --redis

./manage.py runserver 0.0.0.0:8000
