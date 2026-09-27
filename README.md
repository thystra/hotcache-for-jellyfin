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

## Cache aging and demotion

`cache.hot_window_days` controls how recently an item must have been played to
continue qualifying as hot. While an already-cached item still qualifies, its
`last_seen_hot` timestamp is refreshed.

When `cache.enable_demotion` is true, `cache.demote_after_days_cold` is the
additional grace period after the item stops qualifying as hot. The shipped
example uses 14 days. With a 30-day hot window and a 14-day cold grace period,
an item normally remains cached for at most about 44 days after its last
playback.

The older `cache.demote_after_days_unwatched` setting remains accepted as a
compatibility alias. If both settings are present, `demote_after_days_cold`
wins. Reports and `--check` show whether demotion is enabled and the active
cold-cache grace period.

## Filesystem capacity reporting

Reports automatically inspect the filesystem that contains the cache root. On a
normal filesystem, Hotcache reports the filesystem source, mountpoint, and
writable space. On ZFS, if `zfs`/`zpool` are available, it additionally reports
the dataset and pool, `quota`, `refquota`, `used`, `referenced`, dataset
`available`, and pool free space.

For ZFS, dataset `available` is used as the writable-space figure because it
already reflects pool pressure, quotas, reservations, and other dataset limits.
Pool free space is informational and is not used as the promotion limit.

`Effective remaining` is the smaller of Hotcache's own remaining policy limit
and filesystem headroom after the configured `minimum_free_cache_space` reserve.
For dry-runs, projected promotions are also subtracted from filesystem headroom
so the report describes capacity after the proposed plan rather than current
free space alone.

No ZFS-specific configuration is required. If filesystem metadata tools are
unavailable, Hotcache falls back to the operating system free-space result and
reports a metadata warning instead of failing the run.

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


## Managed cache reconciliation

A playback item that is already cached is not a candidate and is not
treated as a failed promotion. Hotcache first checks for a manifest entry for
the Jellyfin-visible source path. If the manifest cache path, source symlink
target, cache file, and preserved original all agree, the item remains in the
promoted/cache state; mutable manifest metadata such as `last_seen_hot`,
`last_played`, title, play count, and actual cache size is refreshed.

Daily reports distinguish state from actions: `Promoted files` is the current
validated cache population, `Promoted this run` contains only new promotion
actions, and `Candidates` contains only eligible files that are not already
promoted.

The manifest remains the ownership boundary. Hotcache does **not** automatically
adopt an untracked source symlink or an existing untracked cache file merely
because its path resembles a configured cache path. Those states remain
operator-visible and are skipped until they are explicitly repaired or removed.
This prevents Hotcache from claiming files or symlinks it did not create.
