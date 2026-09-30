# Releasing Jellyfin Hotcache

The Forgejo `Release Build` workflow prepares the release artifact set. It does
not create tags, publish a Forgejo release, or modify repository contents.

## Release flow

1. Merge the release changes to `main` and confirm normal CI is green.
2. Optionally run **Actions → Release Build → Run workflow** from `main`.
   This is a rehearsal build. It validates the application and Debian package
   versions, builds the package, runs the Debian package tests and Lintian, and
   uploads an artifact set to the workflow run.
3. Inspect the rehearsal artifact before tagging.
4. Create a signed release tag on the qualified `main` commit:

   ```sh
   git switch main
   git pull --ff-only
   git tag -s v1.0.3 -m "Jellyfin Hotcache v1.0.3"
   git push origin v1.0.3
   ```

5. The tag push starts `Release Build` again. A tag build additionally requires
   the tag version, `HOTCACHE_VERSION`, and the upstream part of the Debian
   package version to match.
6. Download the release artifact set from the successful tagged workflow run.
7. Verify it before publishing:

   ```sh
   cd jellyfin-hotcache-1.0.3-1-release
   sha256sum -c jellyfin-hotcache-1.0.3-SHA256SUMS
   ```

8. Create the Forgejo release for the signed tag and attach the prepared files.

Do not publish artifacts from a manual rehearsal as the final release. The
tag-triggered build records the signed release ref in the release manifest.

## Expected artifacts

For version `1.0.3-1` on an amd64 build runner, the artifact set is:

```text
jellyfin-hotcache_1.0.3-1_all.deb
jellyfin-hotcache_1.0.3-1_amd64.buildinfo
jellyfin-hotcache_1.0.3-1_amd64.changes
jellyfin-hotcache-1.0.3-RELEASE-MANIFEST.txt
jellyfin-hotcache-1.0.3-SHA256SUMS
```

The `.deb` is architecture-independent. The `.buildinfo` and `.changes`
filenames identify the architecture of the system that performed the build.

## Workflow checks

The release workflow fails if any of the following is true:

- `jellyfin-hotcache --version` does not match the Debian upstream version.
- A release tag does not match the application version.
- `dpkg-buildpackage` or its test suite fails.
- Lintian reports an error.
- The expected `.deb`, `.buildinfo`, or `.changes` file is missing.
- The built Debian package reports an unexpected package name, version, or
  architecture.
- The packaged `/usr/sbin/jellyfin-hotcache --version` does not match the
  release version.

Forgejo workflow artifacts are staging artifacts, not the permanent release
distribution. Attach the verified files to the Forgejo release after the tagged
build succeeds.
