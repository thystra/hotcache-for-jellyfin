# Jellyfin Hotcache

Jellyfin Hotcache promotes selected media files from slower storage to a local
cache while keeping Jellyfin's original media path stable with a symlink. The
NAS-resident original is preserved beside the symlink with a configurable
suffix (default `.cached`) so demotion or recovery does not depend on copying
back from the cache.

## Configuration

The packaged configuration layout is intended to be:

- `/etc/jellyfin-hotcache/config.yml` — operator-owned configuration; never
  overwritten by package upgrades.
- `/etc/jellyfin-hotcache/environment` — optional operator-owned environment
  file for secrets such as `JELLYFIN_API_KEY` or `JELLYFIN_PG_PASSWORD`.
- `/usr/share/jellyfin-hotcache/config.yml.example` — package-managed example.

The repository example is `config/config.yml.example`. It ships with
`cache.dry_run: true`.

## Read-only preflight

Before enabling mutations, run:

```bash
sudo jellyfin-hotcache \
  --config /etc/jellyfin-hotcache/config.yml \
  --check
```

`--check` is read-only. It does not create the cache root or lock file, does not
promote/demote/restore files, and does not save the manifest or write reports.
It checks Jellyfin `/Sessions`, playback database connectivity/schema, library
paths, the cache root and free-space limits, run-lock availability, manifest
entries, cache containment, symlink targets, preserved originals, and orphaned
cache files.

Exit status:

- `0` — no FAIL checks.
- `1` — one or more operational FAIL checks.
- `2` — configuration/command setup error.

Normal mutating runs fail closed if active streams or playback history cannot
be checked. A missing configured cache root is also fatal; Hotcache will not
create it because that could hide a missing cache mount.

## Tests

Fast regression suite:

```bash
python3 -m pytest -v
```

The PostgreSQL test is skipped unless a test DSN is supplied. To run it against
a disposable PostgreSQL 18 container:

```bash
./tests/run-postgresql-integration.sh
```

The PostgreSQL regression test verifies that multiple Jellyfin `UserData` rows
for one item/user under different `CustomDataKey` values are collapsed to one
per-user play state before household play counts are summed.
