#!/bin/bash -x

./manage.py wait_for_resources --db

if [ "$CI" == "true" ]; then
    set -e

    py.test \
        --cov-config=.coveragerc \
        --cov \
        --cov-branch \
        --cov-report=xml \
        --junitxml=junit.xml \
        -o junit_family=legacy \
        --durations=10

    coverage report -i

    set +e
else
    py.test
fi
