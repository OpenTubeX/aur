# OpenTubeX AUR packages

This repository is the source of truth for the
[`opentubex`](https://aur.archlinux.org/packages/opentubex),
[`opentubex-bin`](https://aur.archlinux.org/packages/opentubex-bin),
[`opentubex-nightly-bin`](https://aur.archlinux.org/packages/opentubex-nightly-bin),
and [`opentubex-git`](https://aur.archlinux.org/packages/opentubex-git) AUR packages.

`opentubex-nightly-bin` follows the nightly channel for x86_64 and aarch64,
including stable releases when they are published. It replaces the stable
package and uses the same application data. Install it with
`paru -S opentubex-nightly-bin` once it is published.

`opentubex-git` builds from the application's current default branch using the
system Electron. Its recipe, launcher, desktop file, and `.SRCINFO` are maintained
here and copied to AUR by the publish workflow. Install it with
`paru -S opentubex-git`.

## How publishing works

After an OpenTubeX release finishes uploading its assets, the application
repository sends an `opentubex-release` repository dispatch containing the
release tag. Nightly releases send `opentubex-nightly` after both supported
DEB assets are publicly available. The publish workflow then:

1. starts with the package files tracked in this repository;
2. updates release packages' `pkgver`, resets `pkgrel` to 1 when the version
   changes, refreshes release checksums, and regenerates `.SRCINFO` files;
3. commits that release metadata back to this repository;
4. copies the resulting files to AUR and publishes each package when its
   files changed.

Stable releases publish all four packages, so nightly users receive the stable
release too. The `opentubex-git` recipe keeps its Git-derived version, package
release number, and checksums. Nightly releases update only `opentubex-nightly-bin`.

The nightly package uses epoch `1` and versions such as `0.36.0.nightly.2111`
for tag `v0.36.0-nightly-2111`, or `0.36.0` for tag `v0.36.0-beta`.
Nightlies are built after the release they are numbered after, so Arch sorts
`0.36.0.nightly.2111` between the `0.36.0` and `0.36.1` releases. Nightly users
receive each stable release and then the nightlies that follow it. The epoch
comes from an earlier version format and must stay.

This means package-specific changes, such as updating the system Electron
dependency and launcher in `opentubex`, can be developed here before a release.
The next release will retain those changes while refreshing its versioned
metadata.

The workflow can also be run manually with a beta or nightly release tag.
If no tag is given, it publishes the latest stable OpenTubeX release.

## Maintainer setup

Add the SSH private key authorized to publish all four AUR packages as the
`AUR_SSH_PRIVATE_KEY` repository secret. The OpenTubeX application repository's
`PUSH_TOKEN` must also have write access to this repository so it can send the
cross-repository dispatch.

The first nightly publish creates the AUR package if the key's account can
register `opentubex-nightly-bin`. If it already exists, that account must be
its maintainer or co-maintainer.
