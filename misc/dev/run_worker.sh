#!/usr/bin/env bash
set -euo pipefail

# Run the Celery worker for local development.
# Requires Redis to be running (e.g. via docker-compose up redis).
# Usage: bash misc/dev/run_worker.sh

exec uv run celery -A main worker --loglevel=info
