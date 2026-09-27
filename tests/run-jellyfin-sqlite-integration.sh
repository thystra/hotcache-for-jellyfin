#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JELLYFIN_IMAGE="${1:-${JELLYFIN_TEST_IMAGE:-jellyfin/jellyfin:12.1}}"
NAME="hotcache-jellyfin-sqlite-$$"
WORK="$(mktemp -d)"
CONFIG_DIR="$WORK/config"
CACHE_DIR="$WORK/cache"
MEDIA_DIR="$WORK/media"
DB_PATH="$CONFIG_DIR/data/jellyfin.db"

cleanup() {
    docker rm -f "$NAME" >/dev/null 2>&1 || true

    # Jellyfin may create bind-mounted files owned by its container UID.
    # Remove the contents from a root container before removing the host
    # temporary directory.
    if [ -d "$WORK" ]; then
        docker run --rm             -v "$WORK:/cleanup"             python:3.14-slim             sh -c 'rm -rf /cleanup/* /cleanup/.[!.]* /cleanup/..?*'             >/dev/null 2>&1 || true
        rmdir "$WORK" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

mkdir -p "$CONFIG_DIR" "$CACHE_DIR" "$MEDIA_DIR"
chmod 0755 "$WORK"
chmod 0777 "$CONFIG_DIR" "$CACHE_DIR" "$MEDIA_DIR"

echo "Initializing Jellyfin SQLite schema with $JELLYFIN_IMAGE"
docker run -d \
    --name "$NAME" \
    -v "$CONFIG_DIR:/config" \
    -v "$CACHE_DIR:/cache" \
    -v "$MEDIA_DIR:/media" \
    "$JELLYFIN_IMAGE" >/dev/null

ready=0
for _ in $(seq 1 120); do
    if [ -s "$DB_PATH" ]; then
        ready=1
        break
    fi
    if [ "$(docker inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null || true)" != "true" ]; then
        echo "Jellyfin container exited before creating jellyfin.db" >&2
        docker logs "$NAME" >&2 || true
        exit 1
    fi
    sleep 1
done

if [ "$ready" -ne 1 ]; then
    echo "Timed out waiting for $DB_PATH" >&2
    docker logs "$NAME" >&2 || true
    exit 1
fi

# Stop Jellyfin cleanly so WAL state is flushed before another container opens
# the database read-only.
docker stop "$NAME" >/dev/null

docker run --rm \
    -v "$ROOT:/src:ro" \
    -v "$CONFIG_DIR:/jellyfin-config:ro" \
    -w /src \
    -e HOTCACHE_TEST_JELLYFIN_DB=/jellyfin-config/data/jellyfin.db \
    python:3.14-slim \
    sh -ec 'pip install --quiet pytest pyyaml && python -m pytest -v -p no:cacheprovider tests/test_jellyfin_sqlite.py'
