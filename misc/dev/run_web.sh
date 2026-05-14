#!/bin/bash -e

./manage.py wait_for_resources --db
./manage.py migrate
./manage.py runserver 0.0.0.0:8000
