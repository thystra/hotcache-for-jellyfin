#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUFFIX="$(date +%s)-$$-$RANDOM"
NETWORK="hotcache-pg-test-$SUFFIX"
PG_NAME="hotcache-pg-$SUFFIX"
TEST_NAME="hotcache-pg-client-$SUFFIX"

cleanup() {
    docker rm -f "$TEST_NAME" >/dev/null 2>&1 || true
    docker rm -f "$PG_NAME" >/dev/null 2>&1 || true
    docker network rm "$NETWORK" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker network create "$NETWORK" >/dev/null

docker run -d --rm \
    --name "$PG_NAME" \
    --network "$NETWORK" \
    -e POSTGRES_DB=hotcache_test \
    -e POSTGRES_USER=hotcache \
    -e POSTGRES_PASSWORD=hotcache-test-password \
    postgres:18 >/dev/null

for _ in $(seq 1 60); do
    if docker exec "$PG_NAME" pg_isready -U hotcache -d hotcache_test >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

docker exec "$PG_NAME" pg_isready -U hotcache -d hotcache_test >/dev/null

# Copy the repository through the Docker API so this works with both a local
# daemon and the Forgejo runners' isolated Docker-in-Docker daemon.
docker create \
    --name "$TEST_NAME" \
    --network "$NETWORK" \
    -w /src \
    -e "HOTCACHE_TEST_PG_DSN=host=$PG_NAME port=5432 dbname=hotcache_test user=hotcache password=hotcache-test-password sslmode=disable" \
    python:3.14-slim \
    sh -ec 'pip install --quiet pytest pyyaml "psycopg[binary]" && python -m pytest -v -p no:cacheprovider tests/test_postgresql.py' \
    >/dev/null

docker cp "$ROOT/." "$TEST_NAME:/src"
docker start -a "$TEST_NAME"
