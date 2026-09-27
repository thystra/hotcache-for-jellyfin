#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUFFIX="$(date +%s)-$$-$RANDOM"
TEST_NAME="hotcache-fast-test-$SUFFIX"

cleanup() {
    docker rm -f "$TEST_NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# The Forgejo runners use a separate Docker-in-Docker daemon. Host bind paths
# from this job container do not exist in that daemon, so copy the source tree
# through the Docker API instead of bind-mounting it.
docker create \
    --name "$TEST_NAME" \
    -w /src \
    python:3.14-slim \
    sh -ec 'pip install --quiet pytest pyyaml && python -m pytest -q -p no:cacheprovider' \
    >/dev/null

docker cp "$ROOT/." "$TEST_NAME:/src"
docker start -a "$TEST_NAME"
