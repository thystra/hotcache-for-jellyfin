#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JELLYFIN_IMAGE="${1:-${JELLYFIN_TEST_IMAGE:-jellyfin/jellyfin:12.1}}"
SUFFIX="$(date +%s)-$$-$RANDOM"
NAME="hotcache-jellyfin-sqlite-$SUFFIX"
TEST_NAME="hotcache-jellyfin-client-$SUFFIX"
CONFIG_VOLUME="hotcache-jellyfin-config-$SUFFIX"
CACHE_VOLUME="hotcache-jellyfin-cache-$SUFFIX"
MEDIA_VOLUME="hotcache-jellyfin-media-$SUFFIX"

cleanup() {
    docker rm -f "$TEST_NAME" >/dev/null 2>&1 || true
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    docker volume rm -f \
        "$CONFIG_VOLUME" \
        "$CACHE_VOLUME" \
        "$MEDIA_VOLUME" \
        >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker volume create "$CONFIG_VOLUME" >/dev/null
docker volume create "$CACHE_VOLUME" >/dev/null
docker volume create "$MEDIA_VOLUME" >/dev/null

# Named volumes live in the Docker daemon, so they work identically with local
# Docker and with the Forgejo runners' isolated Docker-in-Docker daemon.
docker run --rm \
    -v "$CONFIG_VOLUME:/config" \
    -v "$CACHE_VOLUME:/cache" \
    -v "$MEDIA_VOLUME:/media" \
    python:3.14-slim \
    sh -ec 'chmod 0777 /config /cache /media'

echo "Initializing Jellyfin SQLite schema with $JELLYFIN_IMAGE"
docker run -d \
    --name "$NAME" \
    -v "$CONFIG_VOLUME:/config" \
    -v "$CACHE_VOLUME:/cache" \
    -v "$MEDIA_VOLUME:/media" \
    "$JELLYFIN_IMAGE" >/dev/null

ready=0
for _ in $(seq 1 120); do
    if docker exec "$NAME" test -s /config/data/jellyfin.db >/dev/null 2>&1 \
        && docker logs "$NAME" 2>&1 | grep -q 'Startup complete'; then
        ready=1
        break
    fi

    if [ "$(docker inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null || true)" != "true" ]; then
        echo "Jellyfin container exited before completing SQLite initialization" >&2
        docker logs "$NAME" >&2 || true
        exit 1
    fi
    sleep 1
done

if [ "$ready" -ne 1 ]; then
    echo "Timed out waiting for Jellyfin SQLite initialization" >&2
    docker logs "$NAME" >&2 || true
    exit 1
fi

# Stop Jellyfin cleanly so WAL state is flushed before another container opens
# the database read-only.
docker stop "$NAME" >/dev/null

docker create \
    --name "$TEST_NAME" \
    -v "$CONFIG_VOLUME:/jellyfin-config" \
    -w /src \
    -e HOTCACHE_TEST_JELLYFIN_DB=/jellyfin-config/data/jellyfin.db \
    python:3.14-slim \
    sh -ec 'pip install --quiet pytest pyyaml && python -m pytest -v -p no:cacheprovider tests/test_jellyfin_sqlite.py' \
    >/dev/null

docker cp "$ROOT/." "$TEST_NAME:/src"
docker start -a "$TEST_NAME"
