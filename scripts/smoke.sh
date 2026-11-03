#!/usr/bin/env bash
set -euo pipefail
docker compose run --rm --no-deps -v "$PWD/tests:/app/tests:ro" ui pytest -q tests
