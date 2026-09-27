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
  file for secrets such as `JELLYFIN_API_KEY` or `JELLYFIN_PG_PASSWORD`. The
  CLI reads this file automatically; variables already present in the process
  environment take precedence. Use `--environment-file PATH` to select a
  different file.
- `/usr/share/jellyfin-hotcache/config.yml.example` — package-managed example.

Environment files use simple `NAME=value` entries and are never shell-executed.

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

## Playback history backends

Hotcache supports Jellyfin's core playback state on both database backends:

- `jellyfin_sqlite` — stock/default Jellyfin SQLite (`jellyfin.db`), using
  `UserData` and `BaseItems`. No Playback Reporting plugin is required.
- `postgresql` — Jellyfin PostgreSQL, using `UserData` and `BaseItems`.
- `playback_reporting_sqlite` — legacy Playback Reporting plugin SQLite event
  database. The older `sqlite` source name remains an alias for this mode.

Core SQLite and PostgreSQL use lifetime `PlayCount` with `LastPlayedDate`
inside the configured hot window. Legacy Playback Reporting SQLite counts event
rows inside the hot window.

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

Core Jellyfin SQLite is tested both with synthetic playback data and against a
database initialized by the official Jellyfin container. To run the container
integration test manually:

```bash
./tests/run-jellyfin-sqlite-integration.sh jellyfin/jellyfin:12.1
```

CI exercises Jellyfin 10.11.11 and 12.1 so schema compatibility is checked
across the final 10.11 release and the current 12.x line.
