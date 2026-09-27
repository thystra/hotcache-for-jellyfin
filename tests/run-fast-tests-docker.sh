#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

docker run --rm \
    -v "$ROOT:/src:ro" \
    -w /src \
    python:3.14-slim \
    sh -ec 'pip install --quiet pytest pyyaml && python -m pytest -q -p no:cacheprovider'
